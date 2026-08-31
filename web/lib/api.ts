export const API =
  process.env.NEXT_PUBLIC_API_URL === undefined ? "http://localhost:8080" : process.env.NEXT_PUBLIC_API_URL;

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API}${path}`, init);
  if (!res.ok) {
    let message = `${res.status} ${path}`;
    try {
      const body = (await res.json()) as { error?: string };
      if (body.error) message = body.error;
    } catch {
      /* ignore */
    }
    throw new ApiError(message, res.status);
  }
  return res.json() as Promise<T>;
}

export async function postEvent(
  userId: string,
  itemId: string,
  eventType: string,
  title?: string,
  categories?: string[],
): Promise<void> {
  const metadata: Record<string, unknown> = {};
  if (title) metadata.title = title;
  if (categories?.length) metadata.categories = categories;
  await api("/v1/events", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      schema_version: 1,
      user_id: userId,
      item_id: itemId,
      event_type: eventType,
      timestamp: new Date().toISOString(),
      metadata,
    }),
  });
}

export type RecentAction = {
  event_type: string;
  item_id: string;
  title?: string;
  timestamp?: number;
};

export type UserFeatures = {
  views_24h?: number;
  likes_24h?: number;
  skips_24h?: number;
  watches_24h?: number;
  interaction_count?: number;
  avg_engagement?: number;
  affinities?: Record<string, number>;
  feature_updated_at?: number | null;
  disliked_items?: string[];
  liked_items?: string[];
  interacted_items?: string[];
  recent_actions?: RecentAction[];
};

export async function getFeatures(userId: string): Promise<UserFeatures> {
  const body = await api<{ features: UserFeatures | null }>(`/v1/users/${userId}/features`);
  return body.features || {};
}

export function notifyTicketChanged(): void {
  if (typeof window !== "undefined") {
    window.dispatchEvent(new Event("watchnext-ticket-changed"));
  }
}

export function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

export async function waitForFeatureUpdate(
  userId: string,
  before: number | null | undefined,
  timeoutMs = 8000,
): Promise<UserFeatures | null> {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    await sleep(300);
    try {
      const feats = await getFeatures(userId);
      const ts = feats.feature_updated_at;
      if (typeof ts === "number" && (before == null || ts > before)) {
        return feats;
      }
    } catch {
      /* keep polling */
    }
  }
  return null;
}

export type MovieItem = {
  item_id: string;
  score?: number;
  title?: string;
  categories?: string[];
  year?: number | null;
  source?: string;
  popularity?: number;
  rating?: number;
};

export async function getItem(itemId: string): Promise<MovieItem> {
  return api<MovieItem>(`/v1/items/${encodeURIComponent(itemId)}`);
}

export type CatalogPage = {
  items: MovieItem[];
  total: number;
  offset: number;
  limit: number;
  query: string;
  genre: string;
  sort: string;
};

export type GenreCount = {
  name: string;
  count: number;
};

export async function getCatalog(opts: {
  q?: string;
  genre?: string;
  sort?: string;
  limit?: number;
  offset?: number;
  yearMin?: number;
  yearMax?: number;
}): Promise<CatalogPage> {
  const params = new URLSearchParams();
  if (opts.q) params.set("q", opts.q);
  if (opts.genre) params.set("genre", opts.genre);
  if (opts.sort) params.set("sort", opts.sort);
  if (opts.yearMin) params.set("year_min", String(opts.yearMin));
  if (opts.yearMax) params.set("year_max", String(opts.yearMax));
  params.set("limit", String(opts.limit ?? 48));
  params.set("offset", String(opts.offset ?? 0));
  return api<CatalogPage>(`/v1/catalog?${params.toString()}`);
}

export async function getGenres(): Promise<{
  genres: GenreCount[];
  total_items: number;
  live_items?: number;
  year_min?: number | null;
  year_max?: number | null;
  updated_at?: string | null;
}> {
  return api(`/v1/genres`);
}

export async function refreshCatalog(): Promise<{
  genres: GenreCount[];
  total_items: number;
  live_items?: number;
  year_min?: number | null;
  year_max?: number | null;
  updated_at?: string | null;
}> {
  return api(`/v1/catalog/refresh`, { method: "POST" });
}

export function friendlySaveError(err: unknown): string {
  const text = String(err).replace(/^Error:\s*/i, "");
  if (/redis|consumer|feature update/i.test(text)) {
    return "Couldn’t save that just now. Try again in a second.";
  }
  if (/failed to fetch|networkerror|load failed/i.test(text)) {
    return "Couldn’t reach the house. Try again in a moment.";
  }
  if (/\b502\b|\b503\b|\b504\b/.test(text)) {
    return "The booth is busy. Try again in a moment.";
  }
  if (/\b404\b/.test(text)) {
    return "We don’t have that title.";
  }
  return text;
}

export function actedFromFeatures(feats: UserFeatures | null | undefined): Record<string, "like" | "skip"> {
  const out: Record<string, "like" | "skip"> = {};
  for (const id of feats?.liked_items || []) out[id] = "like";
  for (const id of feats?.disliked_items || []) out[id] = "skip";
  return out;
}

export type RecResponse = {
  recommendations: MovieItem[];
  user_features?: UserFeatures;
  experiment?: string;
  fallback_used?: boolean;
  model_version?: string;
  debug?: Array<{
    item_id: string;
    source: string;
    retrieval_score?: number;
    source_rank?: number;
    ranker_score?: number;
    title?: string;
    categories?: string[];
    year?: number | null;
  }>;
};

export async function getRecommendations(
  userId: string,
  opts?: { limit?: number; debug?: boolean },
): Promise<RecResponse> {
  const limit = opts?.limit ?? 24;
  const path = opts?.debug
    ? `/v1/recommendations/${encodeURIComponent(userId)}/debug?limit=${limit}`
    : `/v1/recommendations/${encodeURIComponent(userId)}?limit=${limit}`;
  return api<RecResponse>(path);
}

export function uniqueActionRows(
  feats: UserFeatures | null | undefined,
  eventType: "like" | "skip",
  currentIds?: string[],
): { item_id: string; title: string }[] {
  const allowed = new Set(currentIds || []);
  const titles = new Map<string, string>();
  for (const row of feats?.recent_actions || []) {
    if (row.item_id && row.title && !titles.has(row.item_id)) titles.set(row.item_id, row.title);
  }
  const seen = new Set<string>();
  const out: { item_id: string; title: string }[] = [];
  const actions = [...(feats?.recent_actions || [])].reverse();
  for (const row of actions) {
    if (row.event_type !== eventType || !row.item_id || seen.has(row.item_id)) continue;
    if (currentIds && !allowed.has(row.item_id)) continue;
    seen.add(row.item_id);
    out.push({ item_id: row.item_id, title: row.title || titles.get(row.item_id) || row.item_id });
  }
  for (const id of currentIds || []) {
    if (seen.has(id)) continue;
    seen.add(id);
    out.push({ item_id: id, title: titles.get(id) || id });
  }
  return out;
}

export function uniqueLikedRows(feats: UserFeatures | null | undefined): { item_id: string; title: string }[] {
  return uniqueActionRows(feats, "like", feats?.liked_items);
}

export function uniqueSkippedRows(feats: UserFeatures | null | undefined): { item_id: string; title: string }[] {
  return uniqueActionRows(feats, "skip", feats?.disliked_items);
}
