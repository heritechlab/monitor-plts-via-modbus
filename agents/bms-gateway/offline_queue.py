import json
import sqlite3
import threading
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path


@dataclass(frozen=True)
class QueueItem:
    sample_id: str
    payload: dict
    attempt_count: int


class OfflineQueue:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA synchronous=FULL")
        connection.execute("PRAGMA busy_timeout=10000")
        return connection

    def _initialize(self) -> None:
        with self._lock, self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS queue (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    sample_id TEXT NOT NULL UNIQUE,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    attempt_count INTEGER NOT NULL DEFAULT 0,
                    last_attempt_at TEXT,
                    last_error TEXT
                );
                CREATE TABLE IF NOT EXISTS dead_letter (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    sample_id TEXT NOT NULL UNIQUE,
                    payload_json TEXT NOT NULL,
                    failed_at TEXT NOT NULL,
                    error_code TEXT,
                    error_message TEXT
                );
                CREATE TABLE IF NOT EXISTS metadata (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                """
            )

    def next_sequence(self) -> int:
        with self._lock, self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT value FROM metadata WHERE key='sequence'"
            ).fetchone()
            value = int(row["value"]) + 1 if row else 1
            connection.execute(
                "INSERT INTO metadata(key, value) VALUES('sequence', ?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (str(value),),
            )
            connection.commit()
            return value

    def enqueue(self, payload: dict) -> None:
        sample_id = str(payload["sample_id"])
        serialized = json.dumps(payload, separators=(",", ":"), ensure_ascii=False)
        with self._lock, self._connect() as connection:
            connection.execute(
                "INSERT OR IGNORE INTO queue(sample_id, payload_json, created_at) VALUES (?, ?, ?)",
                (sample_id, serialized, datetime.now(UTC).isoformat()),
            )

    def oldest(self, limit: int) -> list[QueueItem]:
        with self._lock, self._connect() as connection:
            rows = connection.execute(
                "SELECT sample_id, payload_json, attempt_count FROM queue ORDER BY id LIMIT ?",
                (limit,),
            ).fetchall()
        return [
            QueueItem(
                row["sample_id"], json.loads(row["payload_json"]), row["attempt_count"]
            )
            for row in rows
        ]

    def acknowledge(self, results: list[dict]) -> None:
        now = datetime.now(UTC).isoformat()
        with self._lock, self._connect() as connection:
            for result in results:
                sample_id = str(result.get("sample_id", ""))
                status = result.get("status")
                if status in {"accepted", "duplicate"}:
                    connection.execute(
                        "DELETE FROM queue WHERE sample_id=?", (sample_id,)
                    )
                elif status == "rejected" and not result.get("retryable", False):
                    row = connection.execute(
                        "SELECT payload_json FROM queue WHERE sample_id=?", (sample_id,)
                    ).fetchone()
                    if row:
                        connection.execute(
                            """
                            INSERT OR REPLACE INTO dead_letter(
                                sample_id, payload_json, failed_at, error_code, error_message
                            ) VALUES (?, ?, ?, ?, ?)
                            """,
                            (
                                sample_id,
                                row["payload_json"],
                                now,
                                result.get("code"),
                                result.get("message"),
                            ),
                        )
                        connection.execute(
                            "DELETE FROM queue WHERE sample_id=?", (sample_id,)
                        )
                else:
                    self._mark_attempt_connection(
                        connection, sample_id, result.get("message", "retryable")
                    )

    def mark_attempt(self, sample_ids: list[str], error: str) -> None:
        with self._lock, self._connect() as connection:
            for sample_id in sample_ids:
                self._mark_attempt_connection(connection, sample_id, error)

    @staticmethod
    def _mark_attempt_connection(
        connection: sqlite3.Connection, sample_id: str, error: str
    ) -> None:
        connection.execute(
            """
            UPDATE queue
            SET attempt_count=attempt_count+1, last_attempt_at=?, last_error=?
            WHERE sample_id=?
            """,
            (datetime.now(UTC).isoformat(), error[:500], sample_id),
        )

    def depth(self) -> int:
        with self._lock, self._connect() as connection:
            return int(connection.execute("SELECT COUNT(*) FROM queue").fetchone()[0])

    def dead_letter_depth(self) -> int:
        with self._lock, self._connect() as connection:
            return int(
                connection.execute("SELECT COUNT(*) FROM dead_letter").fetchone()[0]
            )
