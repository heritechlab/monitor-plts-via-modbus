import argparse
import asyncio
import sys

from sqlalchemy import select

from app.core.config import settings
from app.core.security import api_key_prefix, generate_api_key, hash_api_key, verify_api_key
from app.db.models import Device, DeviceApiKey
from app.db.session import SessionLocal


async def ensure_device(
    slug: str, name: str, supplied_key: str | None, device_type: str = "inverter"
) -> None:
    async with SessionLocal() as session:
        device = await session.scalar(select(Device).where(Device.slug == slug))
        created = device is None
        if device is None:
            device = Device(
                slug=slug,
                name=name,
                device_type=device_type,
                timezone=settings.app_timezone,
                inverter_model="PRIME LFT10224-H40" if device_type == "inverter" else None,
                inverter_rated_w=1000,
                pv_rated_wp=1170,
                battery_nominal_v=24,
                battery_capacity_ah=100,
                tariff_idr_per_kwh=settings.tariff_idr_per_kwh,
            )
            session.add(device)
            await session.flush()

        active_keys = list(
            (
                await session.scalars(
                    select(DeviceApiKey).where(
                        DeviceApiKey.device_id == device.id,
                        DeviceApiKey.revoked_at.is_(None),
                    )
                )
            ).all()
        )
        generated = False
        api_key = supplied_key
        key_registered = bool(api_key) and any(
            verify_api_key(api_key, candidate.key_hash) for candidate in active_keys
        )
        if not active_keys and not api_key:
            api_key = generate_api_key()
            generated = True
        if api_key and not key_registered:
            session.add(
                DeviceApiKey(
                    device_id=device.id,
                    key_prefix=api_key_prefix(api_key),
                    key_hash=hash_api_key(api_key),
                )
            )
        await session.commit()

    print(f"Device {'dibuat' if created else 'sudah ada'}: {slug}")
    if generated:
        print("Simpan API key ini sekarang; nilai tidak akan ditampilkan lagi:")
        print(api_key)
    elif api_key and not key_registered:
        print("API key dari konfigurasi berhasil didaftarkan.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Administrasi PLTS Monitor")
    sub = parser.add_subparsers(dest="command", required=True)
    ensure = sub.add_parser("ensure-device")
    ensure.add_argument("--slug", default=settings.device_slug)
    ensure.add_argument("--name", default=settings.device_name)
    ensure.add_argument("--api-key", default=settings.device_api_key)
    ensure.add_argument("--device-type", default="inverter", choices=["inverter", "bms"])
    args = parser.parse_args()
    if args.command == "ensure-device":
        asyncio.run(ensure_device(args.slug, args.name, args.api_key, args.device_type))
    else:
        sys.exit(2)


if __name__ == "__main__":
    main()
