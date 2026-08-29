export const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8080";

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
): Promise<void> {
  await api("/v1/events", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      schema_version: 1,
      user_id: userId,
      item_id: itemId,
      event_type: eventType,
      timestamp: new Date().toISOString(),
      metadata: title ? { title } : {},
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

export function actedFromFeatures(feats: UserFeatures | null | undefined): Record<string, "like" | "skip"> {
  const out: Record<string, "like" | "skip"> = {};
  for (const id of feats?.liked_items || []) out[id] = "like";
  for (const id of feats?.disliked_items || []) out[id] = "skip";
  return out;
}
