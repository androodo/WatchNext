import { NextRequest, NextResponse } from "next/server";
import { parseMovieTitle } from "@/lib/titles";

export const runtime = "nodejs";

type PosterPayload = {
  url: string | null;
  extract: string | null;
  wikiTitle: string | null;
};

const cache = new Map<string, PosterPayload>();
const WIKI_UA = "WatchNext/0.1 (https://localhost:3000; educational recommender demo)";

async function wikiJson(url: string): Promise<unknown> {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), 8000);
  try {
    const res = await fetch(url, {
      headers: { "User-Agent": WIKI_UA, Accept: "application/json" },
      signal: ctrl.signal,
      next: { revalidate: 86400 },
    });
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  } finally {
    clearTimeout(timer);
  }
}

function imageFromSummary(data: unknown): PosterPayload | null {
  if (!data || typeof data !== "object") return null;
  const row = data as Record<string, unknown>;
  if (row.type === "disambiguation") return null;
  const original = row.originalimage as { source?: string } | undefined;
  const thumb = row.thumbnail as { source?: string } | undefined;
  const url = original?.source || thumb?.source || null;
  if (!url) return null;
  const extract = typeof row.extract === "string" ? row.extract : null;
  const wikiTitle = typeof row.title === "string" ? row.title : null;
  return { url, extract, wikiTitle };
}

async function wikiSummary(title: string): Promise<PosterPayload | null> {
  const url = `https://en.wikipedia.org/api/rest_v1/page/summary/${encodeURIComponent(title)}`;
  return imageFromSummary(await wikiJson(url));
}

async function wikiOpenSearch(query: string): Promise<string[]> {
  const url =
    "https://en.wikipedia.org/w/api.php?action=opensearch&limit=5&namespace=0&format=json" +
    `&search=${encodeURIComponent(query)}`;
  const data = await wikiJson(url);
  if (!data || !Array.isArray(data)) return [];
  const titles = data[1];
  return Array.isArray(titles) ? titles.map(String) : [];
}

async function findPoster(rawTitle: string): Promise<PosterPayload> {
  const parsed = parseMovieTitle(rawTitle);
  const year = parsed.year;
  const tries: string[] = [];
  for (const name of parsed.searchNames) {
    if (year) {
      tries.push(`${name} (${year} film)`);
      tries.push(`${name} (${year})`);
    }
    tries.push(`${name} (film)`);
    tries.push(name);
  }

  for (const title of tries) {
    const hit = await wikiSummary(title);
    if (hit) return hit;
  }

  const searchQueries = parsed.searchNames.flatMap((name) =>
    year ? [`${name} ${year} film`, `${name} ${year}`] : [`${name} film`, name],
  );
  for (const q of searchQueries) {
    const titles = await wikiOpenSearch(q);
    for (const t of titles) {
      const hit = await wikiSummary(t);
      if (hit) return hit;
    }
  }

  return { url: null, extract: null, wikiTitle: null };
}

export async function GET(req: NextRequest) {
  const title = req.nextUrl.searchParams.get("title")?.trim();
  if (!title) {
    return NextResponse.json({ error: "title required" }, { status: 400 });
  }
  const cached = cache.get(title);
  if (cached) {
    return NextResponse.json(cached, { headers: { "Cache-Control": "public, max-age=86400" } });
  }
  const payload = await findPoster(title);
  cache.set(title, payload);
  return NextResponse.json(payload, { headers: { "Cache-Control": "public, max-age=86400" } });
}
