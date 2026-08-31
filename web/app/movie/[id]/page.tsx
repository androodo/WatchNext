"use client";

import Link from "next/link";
import { useParams, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useMemo, useState } from "react";
import Poster, { usePoster } from "@/components/Poster";
import WatchLinks from "@/components/WatchLinks";
import {
  actedFromFeatures,
  ApiError,
  friendlySaveError,
  getFeatures,
  getItem,
  notifyTicketChanged,
  postEvent,
  waitForFeatureUpdate,
  type MovieItem,
  type UserFeatures,
} from "@/lib/api";
import { formatCategories, parseMovieTitle } from "@/lib/titles";
import { usePageTitle } from "@/lib/usePageTitle";
import { useUserId } from "@/lib/useUserId";
import { explainPlacement, recWhyLine } from "@/lib/why";

function MovieInner() {
  const params = useParams<{ id: string }>();
  const search = useSearchParams();
  const from = search.get("from");
  const itemId = decodeURIComponent(params.id || "");
  const { userId } = useUserId();
  const [item, setItem] = useState<MovieItem | null>(null);
  const [error, setError] = useState<Error | null>(null);
  const [acted, setActed] = useState<"like" | "skip" | undefined>();
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState<string | null>(null);
  const [reasons, setReasons] = useState<string[]>([]);
  const [feats, setFeats] = useState<UserFeatures | null>(null);
  const parsed = parseMovieTitle(item?.title);
  usePageTitle(item ? `${parsed.display} · Watch Next` : "Title · Watch Next");
  const year = item?.year ?? parsed.year;
  const { extract, wikiTitle } = usePoster(item?.title);
  const cats = formatCategories(item?.categories);

  useEffect(() => {
    if (!itemId) return;
    setError(null);
    getItem(itemId)
      .then(setItem)
      .catch((err) => setError(err instanceof Error ? err : new Error(String(err))));
  }, [itemId]);

  useEffect(() => {
    if (!userId || !item) return;
    getFeatures(userId)
      .then((next) => {
        setFeats(next);
        setActed(actedFromFeatures(next)[item.item_id]);
        setReasons(explainPlacement(item, next, from));
      })
      .catch(() => {
        setFeats(null);
        setReasons(explainPlacement(item, null, from));
      });
  }, [userId, item, from]);

  const wikiHref = useMemo(() => {
    if (!wikiTitle) return null;
    return `https://en.wikipedia.org/wiki/${encodeURIComponent(wikiTitle.replaceAll(" ", "_"))}`;
  }, [wikiTitle]);

  async function act(eventType: "like" | "skip") {
    if (busy || !userId || !item) return;
    setBusy(true);
    setActed(eventType);
    try {
      let beforeTs: number | null | undefined;
      try {
        beforeTs = (await getFeatures(userId)).feature_updated_at;
      } catch {
        beforeTs = undefined;
      }
      await postEvent(userId, item.item_id, eventType, item.title, item.categories);
      const updated = await waitForFeatureUpdate(userId, beforeTs);
      if (!updated) throw new Error("Redis never updated. Is the feature consumer running?");
      notifyTicketChanged();
      setActed(actedFromFeatures(updated)[item.item_id]);
      setFeats(updated);
      setReasons(explainPlacement(item, updated, from));
      setStatus(eventType === "like" ? "On your ticket. Open Watch next for tonight’s bill." : "Skipped.");
    } catch (err) {
      setStatus(`Could not save that ${eventType}: ${friendlySaveError(err)}`);
      setActed(undefined);
    } finally {
      setBusy(false);
    }
  }

  if (error) {
    const missing = error instanceof ApiError && error.status === 404;
    return (
      <main className="page">
        <p className="page-kicker">
          <Link href="/">Now showing</Link>
          {" · "}
          <Link href="/browse">Find a movie</Link>
        </p>
        <h1>{missing ? "We don’t have that title" : "Couldn’t open this title"}</h1>
        <p className="lede">
          {missing
            ? "It isn’t on these shelves. Search the house or go back to the lobby."
            : "The booth couldn’t load it. Try again, or pick another poster."}
        </p>
        <div className="toolbar">
          <Link className="btn like" href="/browse">
            Find a movie
          </Link>
          <Link className="btn" href="/">
            Now showing
          </Link>
        </div>
      </main>
    );
  }
  if (!item) {
    return (
      <main className="page">
        <p className="lede">Pulling the title…</p>
        <div className="hero movie-hero">
          <div className="poster is-loading" style={{ aspectRatio: "2 / 3", maxWidth: 220 }} />
        </div>
      </main>
    );
  }

  return (
    <main className="page movie-page">
      <p className="page-kicker">
        <Link href="/">Now showing</Link>
        {" · "}
        <Link href="/browse">Find a movie</Link>
      </p>
      <section className="hero movie-hero">
        <Poster title={item.title} />
        <div className="hero-copy">
          <h1>{parsed.display}</h1>
          <div className="pills">
            {year ? <span className="pill">{year}</span> : null}
            {item.rating && !item.item_id.startsWith("tt") ? (
              <span className="pill">{item.rating.toFixed(1)} / 5 house rating</span>
            ) : null}
            {cats.map((label, i) => (
              <Link className="pill-btn" href={`/browse?genre=${encodeURIComponent(item.categories![i])}`} key={label}>
                {label}
              </Link>
            ))}
          </div>
          {extract ? <p className="hero-extract movie-extract">{extract}</p> : null}
          {wikiHref ? (
            <p className="lede">
              <a href={wikiHref} target="_blank" rel="noopener noreferrer">
                Wikipedia
              </a>
            </p>
          ) : null}
          {status ? (
            <div className="status-banner ok" role="status">
              {status}
            </div>
          ) : null}
          <div className="actions">
            <button className="btn like" type="button" disabled={busy} onClick={() => act("like")}>
              {acted === "like" ? "On your ticket" : "I’d watch this"}
            </button>
            <button className="btn skip" type="button" disabled={busy} onClick={() => act("skip")}>
              {acted === "skip" ? "Skipped" : "Not for me"}
            </button>
            <Link className="btn ghost" href="/debug">
              Watch next
            </Link>
          </div>
        </div>
      </section>
      <WatchLinks title={item.title} year={year} itemId={item.item_id} />
      <section className="why-panel">
        <h2>Why this showed up</h2>
        <p className="lede">{recWhyLine(item, feats)}</p>
        {reasons.length ? (
          <details className="howto">
            <summary>More detail</summary>
            <ul>
              {reasons.map((reason) => (
                <li key={reason}>{reason}</li>
              ))}
            </ul>
          </details>
        ) : null}
        <p>
          Change your mind with I’d watch or Not for me.{" "}
          <Link href="/debug">Watch next</Link> is tonight’s bill.
        </p>
      </section>
    </main>
  );
}

export default function MoviePage() {
  return (
    <Suspense
      fallback={
        <main className="page">
          <p className="lede">Pulling the title…</p>
        </main>
      }
    >
      <MovieInner />
    </Suspense>
  );
}
