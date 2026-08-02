from pathlib import Path

from offline_queue import OfflineQueue


def test_queue_ack_and_dead_letter(tmp_path: Path) -> None:
    queue = OfflineQueue(tmp_path / "queue.sqlite3")
    queue.enqueue({"sample_id": "one", "value": 1})
    queue.enqueue({"sample_id": "two", "value": 2})
    assert queue.depth() == 2
    queue.acknowledge(
        [
            {"sample_id": "one", "status": "accepted", "retryable": False},
            {
                "sample_id": "two",
                "status": "rejected",
                "retryable": False,
                "code": "invalid_payload",
            },
        ]
    )
    assert queue.depth() == 0
    assert queue.dead_letter_depth() == 1


def test_sequence_survives_instances(tmp_path: Path) -> None:
    path = tmp_path / "queue.sqlite3"
    assert OfflineQueue(path).next_sequence() == 1
    assert OfflineQueue(path).next_sequence() == 2
