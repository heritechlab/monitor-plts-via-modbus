# API v1

Base URL lokal: `http://127.0.0.1:8000`. Dokumentasi interaktif tersedia di
`/docs` pada mode lokal.

Endpoint ingest memerlukan `Authorization: Bearer <DEVICE_API_KEY>`:

- `POST /api/v1/ingest/telemetry`
- `POST /api/v1/ingest/telemetry/batch` (maksimal 100 sampel)
- `POST /api/v1/ingest/heartbeat`

Endpoint baca:

- `GET /api/v1/devices/{slug}`
- `GET /api/v1/devices/{slug}/latest`
- `GET /api/v1/devices/{slug}/telemetry`
- `GET /api/v1/devices/{slug}/analytics/daily`
- `GET /api/v1/devices/{slug}/analytics/monthly`
- `GET /api/v1/devices/{slug}/data-quality`
- `GET /api/v1/devices/{slug}/export.csv`

Batch selalu mengembalikan status per `sample_id`. Gateway hanya menghapus
`accepted` dan `duplicate`; penolakan permanen masuk dead-letter.

