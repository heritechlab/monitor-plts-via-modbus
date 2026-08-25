from typing import Any

import httpx


class ApiClientError(RuntimeError):
    def __init__(self, message: str, *, retryable: bool = True) -> None:
        super().__init__(message)
        self.retryable = retryable


class ApiClient:
    def __init__(
        self, base_url: str, api_key: str, timeout: float, verify_tls: bool
    ) -> None:
        self._client = httpx.Client(
            base_url=base_url,
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=timeout,
            verify=verify_tls,
        )

    def close(self) -> None:
        self._client.close()

    def send_batch(self, samples: list[dict]) -> dict[str, Any]:
        try:
            response = self._client.post(
                "/api/v1/ingest/bms-telemetry/batch", json={"samples": samples}
            )
        except httpx.HTTPError as exc:
            raise ApiClientError(str(exc)) from exc
        if response.status_code in {401, 403}:
            raise ApiClientError("API key ditolak oleh server", retryable=False)
        if response.status_code == 429 or response.status_code >= 500:
            raise ApiClientError(f"Server sementara gagal: HTTP {response.status_code}")
        if response.is_error:
            raise ApiClientError(
                f"Request ditolak: HTTP {response.status_code} {response.text[:300]}",
                retryable=False,
            )
        return response.json()

    def heartbeat(self, payload: dict) -> None:
        try:
            response = self._client.post("/api/v1/ingest/heartbeat", json=payload)
        except httpx.HTTPError as exc:
            raise ApiClientError(str(exc)) from exc
        if response.status_code in {401, 403}:
            raise ApiClientError("API key heartbeat ditolak", retryable=False)
        if response.status_code == 429 or response.status_code >= 500:
            raise ApiClientError(f"Heartbeat gagal: HTTP {response.status_code}")
        if response.is_error:
            raise ApiClientError(
                f"Heartbeat ditolak: HTTP {response.status_code}", retryable=False
            )
