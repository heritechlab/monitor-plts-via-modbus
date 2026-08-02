from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import verify_api_key
from app.db.models import Device, DeviceApiKey


async def authenticate_device(
    session: AsyncSession, device_slug: str, api_key: str | None
) -> Device:
    if not api_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="API key diperlukan")

    device = await session.scalar(
        select(Device).where(Device.slug == device_slug, Device.is_active.is_(True))
    )
    if device is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Kredensial tidak valid"
        )

    now = datetime.now(UTC)
    keys = (
        await session.scalars(
            select(DeviceApiKey).where(
                DeviceApiKey.device_id == device.id,
                DeviceApiKey.revoked_at.is_(None),
            )
        )
    ).all()
    matched = None
    for candidate in keys:
        if candidate.expires_at is not None and _as_utc(candidate.expires_at) <= now:
            continue
        if verify_api_key(api_key, candidate.key_hash):
            matched = candidate

    if matched is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Kredensial tidak valid"
        )

    matched.last_used_at = now
    return device


def bearer_token(authorization: str | None) -> str | None:
    if not authorization:
        return None
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        return None
    return token.strip()


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
