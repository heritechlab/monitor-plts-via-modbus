from datetime import UTC, datetime, timedelta

import pytest

from app.db.models import InverterTelemetry
from app.services.register_analysis import analyze_register_rows, pearson_correlation


def test_pearson_correlation_handles_positive_and_constant_series() -> None:
    assert pearson_correlation([1, 2, 3], [2, 4, 6]) == pytest.approx(1)
    assert pearson_correlation([1, 1, 1], [2, 3, 4]) is None


def test_register_analysis_separates_known_candidate_and_unknown() -> None:
    start = datetime(2026, 8, 3, tzinfo=UTC)
    rows = []
    for index in range(20):
        raw = {f"0x{0x3000 + offset:04X}": 0 for offset in range(32)}
        raw["0x3004"] = index
        raw["0x3006"] = index * 2
        raw["0x3007"] = 5
        rows.append(
            InverterTelemetry(
                recorded_at=start + timedelta(seconds=index * 5),
                raw_registers=raw,
                load_percent=float(index),
                quality_flags=[],
                quality_details={},
            )
        )

    result = {item["address"]: item for item in analyze_register_rows(rows)}

    assert result["0x3004"]["status"] == "known"
    assert result["0x3004"]["decoded_value"] == 19
    assert result["0x3006"]["status"] == "candidate"
    assert result["0x3006"]["strongest_correlation"]["metric"] == "load_percent"
    assert result["0x3007"]["status"] == "unknown"
    assert result["0x3007"]["activity"] == "stable"
