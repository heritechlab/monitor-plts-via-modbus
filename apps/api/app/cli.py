import argparse
import asyncio
import sys
from datetime import UTC, datetime, timedelta

from sqlalchemy import String, cast, func, select, text, update

from app.core.config import settings
from app.core.security import api_key_prefix, generate_api_key, hash_api_key, verify_api_key
from app.db.models import BmsTelemetry, Device, DeviceApiKey, InverterTelemetry
from app.db.session import SessionLocal, engine

# Tabel telemetry yang menyimpan dump register mentah. Kolom itu hanya dibaca
# halaman Register (maksimal 24 jam ke belakang) dan endpoint /latest, jadi
# salinan lamanya aman dikosongkan.
RAW_REGISTER_TABLES = (InverterTelemetry, BmsTelemetry)


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


async def prune_raw_registers(days: int, run_vacuum: bool) -> None:
    """Kosongkan raw_registers untuk sampel lama, lalu rapikan file DB.

    Metrik hasil decode (PV, beban, tegangan, suhu, sel baterai) tidak disentuh,
    jadi seluruh halaman analitik, grafik, dan riwayat tetap utuh. Yang hilang
    hanya kemampuan membedah register mentah untuk tanggal di luar rentang simpan.
    """
    cutoff = datetime.now(UTC) - timedelta(days=days)
    total = 0
    async with SessionLocal() as session:
        for model in RAW_REGISTER_TABLES:
            result = await session.execute(
                update(model)
                .where(
                    model.recorded_at < cutoff,
                    # Lewati baris yang sudah kosong supaya menjalankan perintah ini
                    # berulang kali tidak menulis ulang seluruh tabel.
                    func.length(cast(model.raw_registers, String)) > 2,
                )
                .values(raw_registers={})
            )
            print(f"{model.__tablename__}: {result.rowcount:,} baris dikosongkan")
            total += result.rowcount
        await session.commit()

    print(f"Total {total:,} baris lebih tua dari {days} hari dibersihkan.")
    if not run_vacuum:
        return
    if total == 0:
        print("Tidak ada perubahan, VACUUM dilewati.")
        return
    print("Menjalankan VACUUM untuk merebut kembali ruang disk...")
    # VACUUM tidak boleh berada di dalam transaksi.
    async with engine.connect() as connection:
        await connection.execution_options(isolation_level="AUTOCOMMIT")
        await connection.execute(text("VACUUM"))
    print("VACUUM selesai.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Administrasi PLTS Monitor")
    sub = parser.add_subparsers(dest="command", required=True)
    ensure = sub.add_parser("ensure-device")
    ensure.add_argument("--slug", default=settings.device_slug)
    ensure.add_argument("--name", default=settings.device_name)
    ensure.add_argument("--api-key", default=settings.device_api_key)
    ensure.add_argument("--device-type", default="inverter", choices=["inverter", "bms"])

    prune = sub.add_parser("prune-raw", help="Kosongkan raw_registers sampel lama")
    prune.add_argument("--days", type=int, default=7, help="Umur simpan register mentah")
    prune.add_argument("--no-vacuum", action="store_true", help="Lewati VACUUM")

    args = parser.parse_args()
    if args.command == "ensure-device":
        asyncio.run(ensure_device(args.slug, args.name, args.api_key, args.device_type))
    elif args.command == "prune-raw":
        asyncio.run(prune_raw_registers(args.days, not args.no_vacuum))
    else:
        sys.exit(2)


if __name__ == "__main__":
    main()
