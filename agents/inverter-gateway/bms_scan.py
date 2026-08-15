"""Diagnostic scanner untuk dongle RS485 baru (BMS JIKONG) — bukan bagian dari gateway.

Dijalankan manual di laptop server untuk mencari tahu protokol yang dipakai BMS
di COM port tertentu: dengar dulu apakah BMS broadcast sendiri, lalu coba probe
Modbus RTU FC03/FC04 di beberapa kombinasi baudrate & slave id.

Pemakaian:
    python bms_scan.py --port COM6
    python bms_scan.py --port COM6 --baud 9600,19200,115200 --slaves 0,1,2,3,4,5
"""

import argparse
import sys
import time

import serial

from crc import append_crc, validate_crc

DEFAULT_BAUDS = [9600, 19200, 38400, 115200]
DEFAULT_SLAVES = [0, 1, 2, 3, 4, 5]
FUNCTION_CODES = [0x03, 0x04]


def hexdump(data: bytes) -> str:
    return " ".join(f"{b:02X}" for b in data) if data else "(kosong)"


def listen_passive(port: str, baud: int, seconds: float) -> bytes:
    with serial.Serial(
        port=port,
        baudrate=baud,
        bytesize=serial.EIGHTBITS,
        parity=serial.PARITY_NONE,
        stopbits=serial.STOPBITS_ONE,
        timeout=0.2,
    ) as ser:
        ser.reset_input_buffer()
        deadline = time.monotonic() + seconds
        buffer = bytearray()
        while time.monotonic() < deadline:
            chunk = ser.read(256)
            if chunk:
                buffer.extend(chunk)
        return bytes(buffer)


def probe_modbus(port: str, baud: int, slave: int, function: int) -> bytes:
    with serial.Serial(
        port=port,
        baudrate=baud,
        bytesize=serial.EIGHTBITS,
        parity=serial.PARITY_NONE,
        stopbits=serial.STOPBITS_ONE,
        timeout=0.8,
        write_timeout=0.8,
    ) as ser:
        ser.reset_input_buffer()
        request = append_crc(bytes([slave, function, 0x00, 0x00, 0x00, 0x02]))
        ser.write(request)
        ser.flush()
        time.sleep(0.15)
        return bytes(ser.read(256))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", required=True, help="Contoh: COM6")
    parser.add_argument(
        "--baud",
        default=",".join(str(b) for b in DEFAULT_BAUDS),
        help="Daftar baudrate dipisah koma",
    )
    parser.add_argument(
        "--slaves",
        default=",".join(str(s) for s in DEFAULT_SLAVES),
        help="Daftar slave id dipisah koma",
    )
    parser.add_argument("--listen-seconds", type=float, default=3.0)
    args = parser.parse_args()

    bauds = [int(b) for b in args.baud.split(",")]
    slaves = [int(s) for s in args.slaves.split(",")]

    findings = []

    for baud in bauds:
        print(f"\n=== Baud {baud} ===")
        try:
            print(f"[dengar pasif {args.listen_seconds}s]")
            passive = listen_passive(args.port, baud, args.listen_seconds)
            if passive:
                print(f"  DATA MASUK ({len(passive)} byte): {hexdump(passive)}")
                findings.append((baud, "passive", None, None, passive))
            else:
                print("  tidak ada broadcast")
        except serial.SerialException as exc:
            print(f"  gagal buka port: {exc}")
            return 1

        for slave in slaves:
            for fc in FUNCTION_CODES:
                try:
                    response = probe_modbus(args.port, baud, slave, fc)
                except serial.SerialException as exc:
                    print(f"  slave={slave} fc=0x{fc:02X}: gagal buka port: {exc}")
                    continue
                if response:
                    valid = validate_crc(response) if len(response) >= 4 else False
                    tag = "CRC OK" if valid else "CRC gagal/parsial"
                    print(
                        f"  slave={slave} fc=0x{fc:02X}: {len(response)} byte "
                        f"[{tag}] -> {hexdump(response)}"
                    )
                    findings.append((baud, "modbus", slave, fc, response))

    print("\n=== Ringkasan ===")
    if not findings:
        print("Tidak ada respons sama sekali di semua kombinasi yang dicoba.")
        print("Kemungkinan: BMS pakai protokol UART proprietary (bukan Modbus RTU),")
        print("atau butuh dikirim command khusus dulu sebelum BMS mau balas.")
    else:
        for baud, kind, slave, fc, data in findings:
            if kind == "passive":
                print(f"- baud={baud}: broadcast pasif, {len(data)} byte")
            else:
                print(f"- baud={baud} slave={slave} fc=0x{fc:02X}: {len(data)} byte")

    return 0


if __name__ == "__main__":
    sys.exit(main())
