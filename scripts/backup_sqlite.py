import argparse
import sqlite3
from datetime import datetime
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Backup konsisten database SQLite lokal"
    )
    parser.add_argument(
        "--source", type=Path, default=Path("apps/api/data/plts.sqlite3")
    )
    parser.add_argument("--destination", type=Path, default=Path("backups"))
    args = parser.parse_args()
    if not args.source.exists():
        raise SystemExit(f"Database tidak ditemukan: {args.source}")
    args.destination.mkdir(parents=True, exist_ok=True)
    target = (
        args.destination / f"plts_{datetime.now().astimezone():%Y%m%d_%H%M%S}.sqlite3"
    )
    with sqlite3.connect(args.source) as source, sqlite3.connect(target) as destination:
        source.backup(destination)
    print(f"Backup berhasil: {target}")


if __name__ == "__main__":
    main()
