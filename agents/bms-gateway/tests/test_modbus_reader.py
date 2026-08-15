from types import SimpleNamespace

import pytest
from modbus_reader import ModbusError, resolve_serial_port


def port(
    device: str,
    description: str = "",
    vid: int | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        device=device,
        description=description,
        manufacturer="",
        product="",
        hwid="",
        vid=vid,
    )


def test_configured_port_wins_when_present() -> None:
    detected = [port("COM3", "USB-SERIAL CH340"), port("COM4", "Other")]
    assert resolve_serial_port("COM4", detected) == "COM4"


def test_missing_configured_port_falls_back_to_single_ch340() -> None:
    detected = [port("COM3", "USB-SERIAL CH340", 0x1A86)]
    assert resolve_serial_port("COM4", detected) == "COM3"


def test_auto_uses_single_serial_adapter() -> None:
    detected = [port("COM7", "Generic USB serial")]
    assert resolve_serial_port("auto", detected) == "COM7"


def test_multiple_ch340_adapters_require_explicit_port() -> None:
    detected = [
        port("COM3", "USB-SERIAL CH340"),
        port("COM4", "USB-SERIAL CH340"),
    ]
    with pytest.raises(ModbusError, match="Lebih dari satu"):
        resolve_serial_port("auto", detected)


def test_missing_adapter_has_actionable_error() -> None:
    with pytest.raises(ModbusError, match="belum terdeteksi"):
        resolve_serial_port("auto", [])
