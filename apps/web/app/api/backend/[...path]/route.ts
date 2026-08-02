import { NextRequest, NextResponse } from "next/server";

export const dynamic = "force-dynamic";

export async function GET(
  request: NextRequest,
  context: { params: Promise<{ path: string[] }> },
) {
  const { path } = await context.params;
  const baseUrl = process.env.INTERNAL_API_BASE_URL ?? "http://127.0.0.1:8000";
  const url = new URL(`/${path.join("/")}`, baseUrl);
  url.search = request.nextUrl.search;
  try {
    const upstream = await fetch(url, {
      cache: "no-store",
      headers: { Accept: request.headers.get("accept") ?? "application/json" },
    });
    const body = await upstream.arrayBuffer();
    return new NextResponse(body, {
      status: upstream.status,
      headers: { "content-type": upstream.headers.get("content-type") ?? "application/json" },
    });
  } catch {
    return NextResponse.json(
      { detail: "Backend lokal tidak dapat dihubungi" },
      { status: 502 },
    );
  }
}

