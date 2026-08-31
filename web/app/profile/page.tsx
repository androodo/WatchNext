"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import Poster from "@/components/Poster";
import {
  friendlySaveError,
  getFeatures,
  notifyTicketChanged,
  postEvent,
  uniqueLikedRows,
  uniqueSkippedRows,
  waitForFeatureUpdate,
  type UserFeatures,
} from "@/lib/api";
import { formatCategories, parseMovieTitle } from "@/lib/titles";
import { isPreloadedUser, useUserId } from "@/lib/useUserId";
import { usePageTitle } from "@/lib/usePageTitle";
import { moviePath } from "@/lib/watch";

export default function ProfilePage() {
  const { userId, requestFresh } = useUserId();
  const [features, setFeatures] = useState<UserFeatures | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);

  async function load() {
    if (!userId) return;
    setError(null);
    setLoading(true);
    try {
      setFeatures(await getFeatures(userId));
    } catch (err) {
      setError(friendlySaveError(err));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, [userId]);

  async function act(itemId: string, title: string, eventType: "like" | "skip") {
    if (busy || !userId) return;
    const label = parseMovieTitle(title).display;
    setBusy(true);
    setStatus(eventType === "like" ? `Putting ${label} back on your ticket…` : `Taking ${label} off your ticket…`);
    try {
      let beforeTs: number | null | undefined;
      try {
        beforeTs = (await getFeatures(userId)).feature_updated_at;
      } catch {
        beforeTs = undefined;
      }
      await postEvent(userId, itemId, eventType, title);
      const updated = await waitForFeatureUpdate(userId, beforeTs);
      if (!updated) throw new Error("Redis never updated. Is the feature consumer running?");
      notifyTicketChanged();
      setFeatures(updated);
      setStatus(eventType === "like" ? `${label} is back on your ticket.` : `Skipped ${label}.`);
    } catch (err) {
      setStatus(`Could not save that: ${friendlySaveError(err)}`);
    } finally {
      setBusy(false);
    }
  }

  const affinities = Object.entries(features?.affinities || {}).sort((a, b) => b[1] - a[1]);
  const maxAff = Math.max(0.0001, ...affinities.map(([, v]) => v));
  const liked = uniqueLikedRows(features);
  const skipped = uniqueSkippedRows(features);
  const preloaded = isPreloadedUser(userId);
  usePageTitle("Your likes · Watch Next");

  return (
    <main className="page">
      <p className="page-kicker">Your ticket</p>
      <h1>Movies you’d watch</h1>
      <p className="lede">
        Titles you marked I’d watch. Change your mind here — skip takes a title off the ticket, I’d watch puts a skip
        back on. Tonight’s bill is on{" "}
        <Link href="/debug">Watch next</Link>.
      </p>
      <div className="toolbar">
        <button className="btn" type="button" onClick={load} disabled={loading || !userId}>
          Reload
        </button>
        <Link className="btn like" href="/debug">
          Watch next
        </Link>
        <button className="btn skip" type="button" onClick={() => requestFresh()}>
          Start over
        </button>
      </div>
      {preloaded && (
        <div className="status-banner error">
          This seat already has a long history, so the counters won’t match taps from this session.{" "}
          <button className="btn compact" type="button" onClick={() => requestFresh()}>
            Start over
          </button>
        </div>
      )}
      {error && <p className="error">{error}</p>}
      {status && <p className="lede">{status}</p>}
      {loading && !features ? (
        <div className="liked-row" aria-busy="true" aria-label="Loading your ticket">
          {Array.from({ length: 6 }, (_, i) => (
            <div className="liked-card liked-card-skel" key={i} />
          ))}
        </div>
      ) : null}
      {features && (
        <>
          <div className="stats">
            <div className="stat">
              <b>{liked.length}</b>
              <span>{liked.length === 1 ? "movie you’d watch" : "movies you’d watch"}</span>
            </div>
            <div className="stat">
              <b>{skipped.length}</b>
              <span>{skipped.length === 1 ? "movie you skipped" : "movies you skipped"}</span>
            </div>
          </div>
          <section className="panel" style={{ marginBottom: 18 }}>
            <h2 style={{ margin: "0 0 8px", letterSpacing: "-0.03em" }}>On your ticket</h2>
            {liked.length === 0 ? (
              <p className="lede">
                None yet.{" "}
                <Link href="/browse">Find a movie</Link> and tap I’d watch — it shows up here.
              </p>
            ) : (
              <div className="liked-row">
                {liked.map((row) => (
                  <article className="liked-card" key={row.item_id}>
                    <Link href={moviePath(row.item_id)}>
                      <Poster title={row.title} hideFallbackTitle />
                      <strong>{parseMovieTitle(row.title).display}</strong>
                    </Link>
                    <button
                      className="btn compact"
                      type="button"
                      disabled={busy}
                      onClick={() => act(row.item_id, row.title, "skip")}
                    >
                      Not for me
                    </button>
                  </article>
                ))}
              </div>
            )}
          </section>
          <section className="panel">
            <h2 style={{ margin: "0 0 8px", letterSpacing: "-0.03em" }}>Genre taste</h2>
            {affinities.length === 0 || liked.length === 0 ? (
              <p className="lede">
                {liked.length
                  ? "These bars fill from the genres of movies you marked I’d watch. Reload after the next like if they’re still empty."
                  : "Mark I’d watch on a few titles and the genres you lean toward show up here."}
              </p>
            ) : (
              affinities.slice(0, 12).map(([k, v]) => (
                <div className="affinity" key={k}>
                  <span>{formatCategories([k])[0]}</span>
                  <div className="bar">
                    <i style={{ width: `${Math.max(6, (v / maxAff) * 100)}%` }} />
                  </div>
                  <span className="affinity-value">{Math.round((v / maxAff) * 100)}%</span>
                </div>
              ))
            )}
          </section>
          <section className="panel" style={{ marginTop: 18 }}>
            <h2 style={{ margin: "0 0 8px", letterSpacing: "-0.03em" }}>Skipped</h2>
            {skipped.length === 0 ? (
              <p className="lede">Nothing skipped yet. Not for me on a poster keeps it off Watch next.</p>
            ) : (
              <>
                <p className="lede">We try not to put these on Watch next. I’d watch puts one back on your ticket.</p>
                <div className="liked-row">
                  {skipped.map((row) => (
                    <article className="liked-card" key={row.item_id}>
                      <Link href={moviePath(row.item_id)}>
                        <Poster title={row.title} hideFallbackTitle />
                        <strong>{parseMovieTitle(row.title).display}</strong>
                      </Link>
                      <button
                        className="btn like compact"
                        type="button"
                        disabled={busy}
                        onClick={() => act(row.item_id, row.title, "like")}
                      >
                        I’d watch
                      </button>
                    </article>
                  ))}
                </div>
              </>
            )}
          </section>
        </>
      )}
    </main>
  );
}
