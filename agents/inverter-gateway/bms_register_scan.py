"""Sweep alamat register Holding (FC03) untuk BMS di COM6 — lanjutan bms_scan.py.

Sudah dikonfirmasi via bms_scan.py: BMS merespons Modbus RTU FC03 di baud 115200,
slave id 1, tapi alamat 0x0000 di luar jangkauan (Illegal Data Address). Script ini
menyapu rentang alamat untuk menemukan blok yang valid.

Pemakaian:
    python bms_register_scan.py --port COM6 --start 0 --end 200
    python bms_register_scan.py --port COM6 --start 0 --end 4096 --count 4
"""

import argparse
import sys
import time

import serial

from crc import append_crc, validate_crc


def read_holding(ser: serial.Serial, slave: int, address: int, count: int) -> bytes:
    request = append_crc(bytes([slave, 0x03]) + address.to_bytes(2, "big") + count.to_bytes(2, "big"))
    ser.reset_input_buffer()
    ser.write(request)
    ser.flush()
    time.sleep(0.03)
    return bytes(ser.read(5 + count * 2))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", required=True)
    parser.add_argument("--baud", type=int, default=115200)
    parser.add_argument("--slave", type=int, default=1)
    parser.add_argument("--start", type=int, default=0)
    parser.add_argument("--end", type=int, default=200, help="Eksklusif")
    parser.add_argument("--count", type=int, default=1, help="Register per request")
    args = parser.parse_args()

    valid = []
    exceptions = {}

    with serial.Serial(
        port=args.port,
        baudrate=args.baud,
        bytesize=serial.EIGHTBITS,
        parity=serial.PARITY_NONE,
        stopbits=serial.STOPBITS_ONE,
        timeout=0.3,
        write_timeout=0.3,
    ) as ser:
        address = args.start
        while address < args.end:
            response = read_holding(ser, args.slave, address, args.count)
            if len(response) >= 3 and response[1] == 0x83:
                code = response[2] if len(response) >= 3 else None
                exceptions[code] = exceptions.get(code, 0) + 1
            elif (
                len(response) == 5 + args.count * 2
                and response[0] == args.slave
                and response[1] == 0x03
                and response[2] == args.count * 2
                and validate_crc(response)
            ):
                values = [
                    int.from_bytes(response[3 + 2 * i : 5 + 2 * i], "big")
                    for i in range(args.count)
                ]
                valid.append((address, values))
                print(f"0x{address:04X} ({address}): {values}")
            address += args.count

    print("\n=== Ringkasan ===")
    print(f"Alamat valid: {len(valid)} dari {args.end - args.start} dicoba")
    if exceptions:
        print(f"Exception codes: {exceptions}")
    if valid:
        first = valid[0][0]
        last = valid[-1][0]
        print(f"Rentang valid: 0x{first:04X} .. 0x{last:04X}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
