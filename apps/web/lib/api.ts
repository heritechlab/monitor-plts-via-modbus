export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
  ) {
    super(message);
  }
}

export async function apiGet<T>(path: string, signal?: AbortSignal): Promise<T> {
  const response = await fetch(`/api/backend${path}`, { cache: "no-store", signal });
  if (!response.ok) {
    let message = `API gagal (${response.status})`;
    try {
      const body = await response.json();
      message = body.detail ?? message;
    } catch {}
    throw new ApiError(message, response.status);
  }
  return response.json() as Promise<T>;
}

