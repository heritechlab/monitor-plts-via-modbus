from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Header, HTTPException, Response, status
from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.telemetry import (
    BatchIngestResponse,
    BatchItemResult,
    BatchTelemetryPayload,
    BmsTelemetryPayload,
    HeartbeatPayload,
    IngestResponse,
    TelemetryPayload,
)
from app.services.auth import authenticate_device, bearer_token
from app.services.ingest import store_bms_telemetry, store_heartbeat, store_telemetry

router = APIRouter(prefix="/ingest", tags=["ingest"])


@router.post("/telemetry", response_model=IngestResponse)
async def ingest_telemetry(
    payload: TelemetryPayload,
    response: Response,
    authorization: str | None = Header(default=None),
    session: AsyncSession = Depends(get_db),
) -> IngestResponse:
    device = await authenticate_device(session, payload.device_slug, bearer_token(authorization))
    stored = await store_telemetry(session, device, payload)
    await session.commit()
    response.status_code = status.HTTP_200_OK if stored.duplicate else status.HTTP_201_CREATED
    return IngestResponse(
        status="duplicate" if stored.duplicate else "accepted",
        sample_id=stored.telemetry.sample_id,
        duplicate=stored.duplicate,
        received_at=stored.telemetry.received_at,
        quality_flags=stored.telemetry.quality_flags,
    )


@router.post("/telemetry/batch", response_model=BatchIngestResponse)
async def ingest_batch(
    batch: BatchTelemetryPayload,
    authorization: str | None = Header(default=None),
    session: AsyncSession = Depends(get_db),
) -> BatchIngestResponse:
    first_slug = next(
        (str(item.get("device_slug")) for item in batch.samples if item.get("device_slug")), None
    )
    if first_slug is None:
        raise HTTPException(status_code=422, detail="device_slug tidak ditemukan dalam batch")
    device = await authenticate_device(session, first_slug, bearer_token(authorization))
    await session.commit()

    results: list[BatchItemResult] = []
    for raw_sample in batch.samples:
        raw_id = str(raw_sample.get("sample_id", "unknown"))
        try:
            payload = TelemetryPayload.model_validate(raw_sample)
            if payload.device_slug != device.slug:
                results.append(
                    BatchItemResult(
                        sample_id=raw_id,
                        status="rejected",
                        code="device_mismatch",
                        message="device_slug tidak sesuai dengan API key",
                    )
                )
                continue
            stored = await store_telemetry(session, device, payload)
            await session.commit()
            results.append(
                BatchItemResult(
                    sample_id=str(payload.sample_id),
                    status="duplicate" if stored.duplicate else "accepted",
                )
            )
        except ValidationError as exc:
            await session.rollback()
            results.append(
                BatchItemResult(
                    sample_id=raw_id,
                    status="rejected",
                    code="invalid_payload",
                    message=str(exc.errors(include_url=False)[:3]),
                )
            )
        except SQLAlchemyError:
            await session.rollback()
            results.append(
                BatchItemResult(
                    sample_id=raw_id,
                    status="rejected",
                    retryable=True,
                    code="database_error",
                    message="Kesalahan sementara saat menyimpan sampel",
                )
            )

    return BatchIngestResponse(
        accepted=sum(item.status == "accepted" for item in results),
        duplicates=sum(item.status == "duplicate" for item in results),
        rejected=sum(item.status == "rejected" for item in results),
        results=results,
    )


@router.post("/bms-telemetry", response_model=IngestResponse)
async def ingest_bms_telemetry(
    payload: BmsTelemetryPayload,
    response: Response,
    authorization: str | None = Header(default=None),
    session: AsyncSession = Depends(get_db),
) -> IngestResponse:
    device = await authenticate_device(session, payload.device_slug, bearer_token(authorization))
    stored = await store_bms_telemetry(session, device, payload)
    await session.commit()
    response.status_code = status.HTTP_200_OK if stored.duplicate else status.HTTP_201_CREATED
    return IngestResponse(
        status="duplicate" if stored.duplicate else "accepted",
        sample_id=stored.telemetry.sample_id,
        duplicate=stored.duplicate,
        received_at=stored.telemetry.received_at,
        quality_flags=stored.telemetry.quality_flags,
    )


@router.post("/bms-telemetry/batch", response_model=BatchIngestResponse)
async def ingest_bms_batch(
    batch: BatchTelemetryPayload,
    authorization: str | None = Header(default=None),
    session: AsyncSession = Depends(get_db),
) -> BatchIngestResponse:
    first_slug = next(
        (str(item.get("device_slug")) for item in batch.samples if item.get("device_slug")), None
    )
    if first_slug is None:
        raise HTTPException(status_code=422, detail="device_slug tidak ditemukan dalam batch")
    device = await authenticate_device(session, first_slug, bearer_token(authorization))
    await session.commit()

    results: list[BatchItemResult] = []
    for raw_sample in batch.samples:
        raw_id = str(raw_sample.get("sample_id", "unknown"))
        try:
            payload = BmsTelemetryPayload.model_validate(raw_sample)
            if payload.device_slug != device.slug:
                results.append(
                    BatchItemResult(
                        sample_id=raw_id,
                        status="rejected",
                        code="device_mismatch",
                        message="device_slug tidak sesuai dengan API key",
                    )
                )
                continue
            stored = await store_bms_telemetry(session, device, payload)
            await session.commit()
            results.append(
                BatchItemResult(
                    sample_id=str(payload.sample_id),
                    status="duplicate" if stored.duplicate else "accepted",
                )
            )
        except ValidationError as exc:
            await session.rollback()
            results.append(
                BatchItemResult(
                    sample_id=raw_id,
                    status="rejected",
                    code="invalid_payload",
                    message=str(exc.errors(include_url=False)[:3]),
                )
            )
        except SQLAlchemyError:
            await session.rollback()
            results.append(
                BatchItemResult(
                    sample_id=raw_id,
                    status="rejected",
                    retryable=True,
                    code="database_error",
                    message="Kesalahan sementara saat menyimpan sampel",
                )
            )

    return BatchIngestResponse(
        accepted=sum(item.status == "accepted" for item in results),
        duplicates=sum(item.status == "duplicate" for item in results),
        rejected=sum(item.status == "rejected" for item in results),
        results=results,
    )


@router.post("/heartbeat")
async def ingest_heartbeat(
    payload: HeartbeatPayload,
    authorization: str | None = Header(default=None),
    session: AsyncSession = Depends(get_db),
) -> dict:
    device = await authenticate_device(session, payload.device_slug, bearer_token(authorization))
    await store_heartbeat(session, device, payload)
    await session.commit()
    return {"status": "accepted", "received_at": datetime.now(UTC)}
