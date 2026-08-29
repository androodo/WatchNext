"use client";

import { useCallback, useEffect, useState } from "react";
import Poster, { usePoster } from "@/components/Poster";
import UserSwitcher from "@/components/UserSwitcher";
import {
  actedFromFeatures,
  api,
  getFeatures,
  postEvent,
  waitForFeatureUpdate,
  type UserFeatures,
} from "@/lib/api";
import { formatCategories, parseMovieTitle } from "@/lib/titles";
import { isPreloadedUser, useUserId } from "@/lib/useUserId";

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
  user_features?: UserFeatures;
};

type Act = "like" | "skip";

type Status = {
  kind: "info" | "busy" | "ok" | "error";
  text: string;
} | null;

function sourceLabel(source?: string) {
  if (!source) return "";
  if (source === "als") return "ALS";
  if (source === "popularity") return "Popular";
  return source;
}

function describeReorder(prev: Item[], next: Item[], likedCount: number): string {
  const prevIds = prev.map((i) => i.item_id);
  const nextIds = next.map((i) => i.item_id);
  const saved = `Saved. You have ${likedCount} liked movie${likedCount === 1 ? "" : "s"}.`;
  if (!prevIds.length) return saved;
  if (prevIds.join() === nextIds.join()) {
    return `${saved} The order can stay similar — likes boost genres inside the same candidate pool.`;
  }
  const changed = nextIds.filter((id, i) => prevIds[i] !== id).length;
  return `${saved} ${changed} title${changed === 1 ? "" : "s"} moved. Open Liked to see the list.`;
}

function rankMoves(prev: Item[], next: Item[]): Record<string, number> {
  const prevPos = new Map(prev.map((item, i) => [item.item_id, i]));
  const moves: Record<string, number> = {};
  next.forEach((item, i) => {
    const from = prevPos.get(item.item_id);
    if (from == null) moves[item.item_id] = 99;
    else if (from !== i) moves[item.item_id] = from - i;
  });
  return moves;
}

function MovieCard({
  item,
  acted,
  move,
  busy,
  onAct,
}: {
  item: Item;
  acted?: Act;
  move?: number;
  busy: boolean;
  onAct: (id: string, type: Act) => void;
}) {
  const parsed = parseMovieTitle(item.title);
  return (
    <figure className={`movie-card ${acted ? `is-${acted}` : ""}`}>
      <Poster title={item.title} />
      {move != null && move !== 0 && (
        <span className={`rank-delta ${move > 0 ? "up" : "down"}`}>
          {move === 99 ? "new" : move > 0 ? `↑${move}` : `↓${Math.abs(move)}`}
        </span>
      )}
      {acted === "like" ? <span className="stamp like">Liked</span> : null}
      {acted === "skip" ? <span className="stamp skip">Skipped</span> : null}
      <figcaption>
        <h3>{parsed.display}</h3>
        <div className="caption-meta">{[parsed.year, sourceLabel(item.source)].filter(Boolean).join(" · ")}</div>
        <div className="card-actions">
          <button
            className="icon-btn like"
            type="button"
            disabled={busy || acted === "like"}
            onClick={() => onAct(item.item_id, "like")}
          >
            {acted === "like" ? "Liked" : "Like"}
          </button>
          <button
            className="icon-btn"
            type="button"
            disabled={busy || acted === "skip"}
            onClick={() => onAct(item.item_id, "skip")}
          >
            {acted === "skip" ? "Skipped" : "Skip"}
          </button>
        </div>
      </figcaption>
    </figure>
  );
}

function Hero({
  item,
  onAct,
  acted,
  busy,
}: {
  item: Item;
  onAct: (id: string, type: Act) => void;
  acted?: Act;
  busy: boolean;
}) {
  const parsed = parseMovieTitle(item.title);
  const { extract } = usePoster(item.title);
  const cats = formatCategories(item.categories);
  return (
    <section className="hero">
      <Poster title={item.title} />
      <div className="hero-copy">
        <p className="page-kicker">Now showing</p>
        <h2>{parsed.display}</h2>
        <div className="pills">
          {parsed.year ? <span className="pill">{parsed.year}</span> : null}
          {cats.map((c) => (
            <span className="pill" key={c}>
              {c}
            </span>
          ))}
          {item.source ? <span className="pill">{sourceLabel(item.source)}</span> : null}
        </div>
        {extract ? <p className="hero-extract">{extract}</p> : null}
        <div className="actions">
          <button
            className="btn like"
            type="button"
            disabled={busy || acted === "like"}
            onClick={() => onAct(item.item_id, "like")}
          >
            {acted === "like" ? "Liked" : "Like"}
          </button>
          <button
            className="btn skip"
            type="button"
            disabled={busy || acted === "skip"}
            onClick={() => onAct(item.item_id, "skip")}
          >
            {acted === "skip" ? "Skipped" : "Skip"}
          </button>
        </div>
      </div>
    </section>
  );
}

export default function FeedPage() {
  const { userId, startFresh } = useUserId();
  const [feed, setFeed] = useState<RecResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [acted, setActed] = useState<Record<string, Act>>({});
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState<Status>(null);
  const [moves, setMoves] = useState<Record<string, number>>({});
  const preloaded = isPreloadedUser(userId);
  const likedCount = Object.values(acted).filter((v) => v === "like").length;

  const load = useCallback(
    async (opts?: { silent?: boolean; previous?: Item[] }) => {
      if (!userId) return null;
      setError(null);
      if (!opts?.silent) {
        setLoading(true);
        setMoves({});
      }
      try {
        const data = await api<RecResponse>(`/v1/recommendations/${userId}?limit=10`);
        if (opts?.previous) {
          setMoves(rankMoves(opts.previous, data.recommendations));
        }
        setFeed(data);
        setActed(actedFromFeatures(data.user_features));
        return data;
      } catch (err) {
        setError(String(err));
        return null;
      } finally {
        setLoading(false);
      }
    },
    [userId],
  );

  useEffect(() => {
    if (!userId) return;
    load();
  }, [load, userId]);

  async function act(itemId: string, eventType: Act) {
    if (busy || !userId) return;
    const item = feed?.recommendations.find((r) => r.item_id === itemId);
    const label = parseMovieTitle(item?.title).display;
    const previous = feed?.recommendations || [];
    setBusy(true);
    setActed((prev) => ({ ...prev, [itemId]: eventType }));
    setStatus({
      kind: "busy",
      text:
        eventType === "like"
          ? `Saving your like for ${label}…`
          : `Saving your skip for ${label}…`,
    });

    if (eventType === "skip") {
      setFeed((prev) =>
        prev
          ? { ...prev, recommendations: prev.recommendations.filter((row) => row.item_id !== itemId) }
          : prev,
      );
    }

    try {
      let beforeTs: number | null | undefined;
      try {
        beforeTs = (await getFeatures(userId)).feature_updated_at;
      } catch {
        beforeTs = undefined;
      }
      await postEvent(userId, itemId, eventType, item?.title);
      const updated = await waitForFeatureUpdate(userId, beforeTs);
      if (!updated) {
        throw new Error("the like was accepted but Redis never updated. Is the feature consumer running?");
      }
      const next = await load({ silent: true, previous });
      const liked = (updated.liked_items || next?.user_features?.liked_items || []).length;
      setStatus({
        kind: "ok",
        text: describeReorder(previous, next?.recommendations || [], liked),
      });
    } catch (err) {
      setStatus({ kind: "error", text: `Could not save that ${eventType}: ${String(err)}` });
      setActed((prev) => {
        const next = { ...prev };
        delete next[itemId];
        return next;
      });
    } finally {
      setBusy(false);
    }
  }

  const items = feed?.recommendations || [];
  const featured = items[0];
  const rest = items.slice(1);

  if (!userId) {
    return (
      <main className="page">
        <p className="lede">Starting your profile…</p>
      </main>
    );
  }

  return (
    <main className="page">
      {preloaded && (
        <div className="status-banner error">
          Ticket {userId} already has a huge MovieLens history, so three new likes will not show as “3 likes”.{" "}
          <button className="btn compact" type="button" onClick={() => startFresh()}>
            New ticket
          </button>
        </div>
      )}
      {status && (
        <div className={`status-banner ${status.kind}`} role="status">
          {status.text}
        </div>
      )}
      {error && <p className="error">{error}</p>}
      <h1 className="sr-only">Now showing</h1>
      {loading && !featured ? (
        <div className="poster-grid">
          {Array.from({ length: 10 }).map((_, i) => (
            <div className="poster is-loading" key={i} style={{ aspectRatio: "2 / 3" }} />
          ))}
        </div>
      ) : null}
      {featured ? <Hero item={featured} onAct={act} acted={acted[featured.item_id]} busy={busy} /> : null}
      {rest.length > 0 && (
        <>
          <div className="section-head">
            <h2>Also playing</h2>
            <p>Like or skip. The next bill is cut from what you pick.</p>
          </div>
          <div className="poster-grid">
            {rest.map((item) => (
              <MovieCard
                key={item.item_id}
                item={item}
                acted={acted[item.item_id]}
                move={moves[item.item_id]}
                busy={busy}
                onAct={act}
              />
            ))}
          </div>
        </>
      )}
      <footer className="page-foot">
        <div className="toolbar">
          <UserSwitcher />
          <button className="btn ghost" type="button" onClick={() => load()} disabled={busy || loading}>
            Refresh
          </button>
          <span className="chip ok">{likedCount} liked</span>
        </div>
        <details className="howto">
          <summary>First time here?</summary>
          <ol>
            <li>
              Click <strong>New ticket</strong> so you start with an empty taste.
            </li>
            <li>
              Like <strong>3 movies</strong>. They should stay marked after a refresh.
            </li>
            <li>
              Open <strong>Liked</strong> — those 3 titles should be there.
            </li>
            <li>
              <strong>Ranking</strong> is the model’s math, not a like counter.
            </li>
          </ol>
        </details>
      </footer>
    </main>
  );
}
