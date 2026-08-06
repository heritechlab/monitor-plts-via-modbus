export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
  ) {
    super(message);
  }
}

export interface ApiGetOptions {
  signal?: AbortSignal;
  cacheTtlSeconds?: number;
}

interface CacheEntry {
  data: unknown;
  expiresAt: number;
}

const cache = new Map<string, CacheEntry>();

export async function apiGet<T>(path: string, options: ApiGetOptions = {}): Promise<T> {
  const { signal, cacheTtlSeconds } = options;
  const key = path;
  const now = Date.now();

  if (cacheTtlSeconds && cacheTtlSeconds > 0) {
    const entry = cache.get(key);
    if (entry && entry.expiresAt > now) {
      return entry.data as T;
    }
  }

  const response = await fetch(`/api/backend${path}`, { cache: "no-store", signal });
  if (!response.ok) {
    let message = `API gagal (${response.status})`;
    try {
      const body = await response.json();
      message = body.detail ?? message;
    } catch {}
    throw new ApiError(message, response.status);
  }

  const data = (await response.json()) as T;
  if (cacheTtlSeconds && cacheTtlSeconds > 0) {
    cache.set(key, { data, expiresAt: now + cacheTtlSeconds * 1000 });
  }
  return data;
}

export function clearApiCache(): void {
  cache.clear();
}

