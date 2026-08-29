"use client";

import { useCallback, useEffect, useState } from "react";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8080";

type Item = {
  item_id: string;
  score: number;
  title?: string;
  categories?: string[];
  source?: string;
};

type RecResponse = {
  request_id: string;
  user_id: string;
  model_version: string;
  experiment: string;
  fallback_used: boolean;
  fallback_reason?: string;
  recommendations: Item[];
};

async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API}${path}`, init);
  if (!res.ok) throw new Error(`${res.status} ${path}`);
  return res.json();
}

export default function FeedPage() {
  const [userId, setUserId] = useState("1001");
  const [feed, setFeed] = useState<RecResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      const data = await api<RecResponse>(`/v1/recommendations/${userId}?limit=10`);
      setFeed(data);
    } catch (err) {
      setError(String(err));
    }
  }, [userId]);

  useEffect(() => {
    load();
  }, [load]);

  async function act(itemId: string, eventType: string) {
    await api("/v1/events", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        schema_version: 1,
        user_id: userId,
        item_id: itemId,
        event_type: eventType,
        timestamp: new Date().toISOString(),
      }),
    });
  }

  return (
    <main className="page">
      <h1>Feed</h1>
      <p className="meta">Like or skip items, wait a moment, then refresh. Online features should move the next ranking.</p>
      <div className="row">
        <input value={userId} onChange={(e) => setUserId(e.target.value)} />
        <button onClick={load}>Refresh feed</button>
      </div>
      {feed && (
        <p className="meta">
          request {feed.request_id} · {feed.experiment} · {feed.model_version}
          {feed.fallback_used ? ` · fallback ${feed.fallback_reason}` : ""}
        </p>
      )}
      {error && <p className="meta">{error}</p>}
      <div className="grid">
        {(feed?.recommendations || []).map((item) => (
          <article className="card" key={item.item_id}>
            <h3>{item.title || `Item ${item.item_id}`}</h3>
            <div className="meta">score {item.score.toFixed(3)} · {item.source}</div>
            <div>{(item.categories || []).map((c) => <span className="pill" key={c}>{c}</span>)}</div>
            <div className="row">
              <button onClick={() => act(item.item_id, "like")}>Like</button>
              <button className="secondary" onClick={() => act(item.item_id, "view")}>View</button>
              <button className="danger" onClick={() => act(item.item_id, "skip")}>Skip</button>
            </div>
          </article>
        ))}
      </div>
    </main>
  );
}
