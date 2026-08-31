"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import MovieCard from "@/components/MovieCard";
import {
  actedFromFeatures,
  friendlySaveError,
  getCatalog,
  getRecommendations,
  notifyTicketChanged,
  postEvent,
  waitForFeatureUpdate,
  type MovieItem,
  type RecResponse,
  type UserFeatures,
} from "@/lib/api";
import { parseMovieTitle } from "@/lib/titles";
import { mixTonightBill } from "@/lib/bill";
import { usePageTitle } from "@/lib/usePageTitle";
import { useUserId } from "@/lib/useUserId";
import { recWhyLine } from "@/lib/why";

const NOW_YEAR = new Date().getFullYear();

export default function WatchNextPage() {
  const { userId, requestFresh } = useUserId();
  const [data, setData] = useState<RecResponse | null>(null);
  const [starter, setStarter] = useState<MovieItem[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState<string | null>(null);
  const [acted, setActed] = useState<Record<string, "like" | "skip">>({});
  const [showMath, setShowMath] = useState(false);
  usePageTitle("Watch next · Watch Next");

  const load = useCallback(async () => {
    if (!userId) return;
    setError(null);
    try {
      const next = await getRecommendations(userId, { limit: 24, debug: true });
      setData(next);
      setActed(actedFromFeatures(next.user_features));
      const skipped = new Set(next.user_features?.disliked_items || []);
      const liked = new Set(next.user_features?.liked_items || []);
      const page = await getCatalog({
        sort: "popular",
        yearMin: NOW_YEAR - 8,
        yearMax: NOW_YEAR,
        limit: 24,
      });
      setStarter(page.items.filter((row) => !skipped.has(row.item_id) && !liked.has(row.item_id)));
    } catch (err) {
      setError(friendlySaveError(err));
    } finally {
      setLoading(false);
    }
  }, [userId]);

  useEffect(() => {
    setLoading(true);
    load();
  }, [load]);

  useEffect(() => {
    const onFocus = () => load();
    window.addEventListener("focus", onFocus);
    window.addEventListener("watchnext-ticket-changed", onFocus);
    return () => {
      window.removeEventListener("focus", onFocus);
      window.removeEventListener("watchnext-ticket-changed", onFocus);
    };
  }, [load]);

  const feats: UserFeatures = data?.user_features || {};
  const likedCount = (feats.liked_items || []).length;
  const ranked = (data?.recommendations || []).filter((row) => !acted[row.item_id]);
  const popular = starter.filter((row) => !acted[row.item_id]);
  const bill = mixTonightBill(ranked, popular, likedCount, 24);
  const rankedIds = new Set(ranked.map((row) => row.item_id));
  const usingStarter = likedCount === 0 && bill.length > 0;

  async function act(itemId: string, eventType: "like" | "skip") {
    if (busy || !userId) return;
    const item = bill.find((row) => row.item_id === itemId);
    const label = parseMovieTitle(item?.title).display;
    setBusy(true);
    setActed((prev) => ({ ...prev, [itemId]: eventType }));
    try {
      let beforeTs: number | null | undefined;
      try {
        beforeTs = feats.feature_updated_at;
      } catch {
        beforeTs = undefined;
      }
      await postEvent(userId, itemId, eventType, item?.title, item?.categories);
      const updated = await waitForFeatureUpdate(userId, beforeTs);
      if (!updated) throw new Error("Redis never updated. Is the feature consumer running?");
      notifyTicketChanged();
      setStatus(eventType === "like" ? `${label} is on your ticket. Here’s a fresh bill.` : `Skipped ${label}.`);
      await load();
    } catch (err) {
      setStatus(`Could not save that ${eventType}: ${friendlySaveError(err)}`);
      setActed((prev) => {
        const next = { ...prev };
        delete next[itemId];
        return next;
      });
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="page">
      <p className="page-kicker">Tonight’s bill</p>
      <h1>Watch next</h1>
      <p className="lede">
        {usingStarter
          ? "A starter bill from what’s been popular lately. Mark I’d watch on a few and this list becomes yours."
          : likedCount < 3
            ? "We’re mixing titles people know with guesses from your ticket. A couple more I’d watch and this list gets sharper."
            : "These are movies to actually watch, ranked from the titles you marked I’d watch. It is not a list of movies you already picked — those live on "}
        {usingStarter || likedCount < 3 ? null : <Link href="/profile">Your likes</Link>}
        {usingStarter || likedCount < 3 ? null : "."}
      </p>
      <div className="toolbar">
        <button className="btn" type="button" onClick={load} disabled={loading || !userId}>
          Reload
        </button>
        <Link className="btn" href="/browse">
          Find more to like
        </Link>
        <button className="btn skip" type="button" onClick={() => requestFresh()}>
          Start over
        </button>
      </div>
      {status ? (
        <div className="status-banner ok" role="status">
          {status}
        </div>
      ) : null}
      {error ? <p className="error">{error}</p> : null}
      {!likedCount && !loading && !bill.length ? (
        <section className="next-empty" aria-label="Need likes first">
          <h2>Mark a few I’d watch first</h2>
          <p>
            Go to <Link href="/">Now showing</Link> or <Link href="/browse">Find a movie</Link>, tap I’d watch on
            titles you’d sit through, then come back. This page fills from that ticket.
          </p>
        </section>
      ) : null}
      {loading && !bill.length ? (
        <div className="poster-grid watch-next-grid" aria-hidden="true">
          {Array.from({ length: 8 }).map((_, i) => (
            <div className="poster is-loading" key={i} style={{ aspectRatio: "2 / 3" }} />
          ))}
        </div>
      ) : null}
      {likedCount > 0 && !loading && bill.length === 0 ? (
        <section className="next-empty">
          <h2>We’ve run out of new titles in this pass</h2>
          <p>
            Like or skip a couple more on <Link href="/browse">Find a movie</Link> and hit Reload.
          </p>
        </section>
      ) : null}
      {bill.length ? (
        <div className="poster-grid watch-next-grid">
          {bill.map((item: MovieItem) => (
            <MovieCard
              key={item.item_id}
              item={item}
              acted={acted[item.item_id]}
              busy={busy}
              onAct={act}
              from="foryou"
              note={
                likedCount === 0 || !rankedIds.has(item.item_id) ? "Popular lately" : recWhyLine(item, feats)
              }
            />
          ))}
        </div>
      ) : null}
      {data?.debug?.length && !usingStarter ? (
        <details
          className="howto"
          style={{ marginTop: 36 }}
          onToggle={(event) => setShowMath((event.target as HTMLDetailsElement).open)}
        >
          <summary>How we ordered this</summary>
          {showMath ? (
            <>
              <p>
                First we retrieve a shortlist, then genre taste from your likes can reshuffle it. The numbers mean
                “show this sooner,” not stars.
              </p>
              <ol className="rank-explain compact">
                {data.debug.slice(0, 8).map((row, i) => (
                  <li key={row.item_id}>
                    #{i + 1} {parseMovieTitle(row.title).display}
                    {" · "}
                    retrieval {(row.retrieval_score ?? 0).toFixed(2)}
                    {row.ranker_score != null ? ` · ranker ${row.ranker_score.toFixed(2)}` : ""}
                  </li>
                ))}
              </ol>
            </>
          ) : null}
        </details>
      ) : null}
    </main>
  );
}
