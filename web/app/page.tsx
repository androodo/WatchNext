"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import GenreBar from "@/components/GenreBar";
import MovieCard from "@/components/MovieCard";
import Poster, { usePoster } from "@/components/Poster";
import TicketStrip from "@/components/TicketStrip";
import {
  actedFromFeatures,
  api,
  friendlySaveError,
  getCatalog,
  getFeatures,
  notifyTicketChanged,
  postEvent,
  waitForFeatureUpdate,
  type MovieItem,
  type RecResponse,
} from "@/lib/api";
import { formatCategories, parseMovieTitle } from "@/lib/titles";
import { mixTonightBill, uniqueById } from "@/lib/bill";
import { useGenres } from "@/lib/useGenres";
import { usePageTitle } from "@/lib/usePageTitle";
import { isPreloadedUser, useUserId } from "@/lib/useUserId";
import { justWatchUrl, moviePath } from "@/lib/watch";

type Item = MovieItem & { score?: number };

type Act = "like" | "skip";

const NOW_YEAR = new Date().getFullYear();

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
  const href = moviePath(item.item_id, "marquee");
  return (
    <section className="hero">
      <Link className="hero-poster-link" href={href} aria-label={`Details for ${parsed.display}`}>
        <Poster title={item.title} />
      </Link>
      <div className="hero-copy">
        <p className="page-kicker">On the marquee</p>
        <h2>
          <Link href={href}>{parsed.display}</Link>
        </h2>
        <div className="pills">
          {parsed.year ? <span className="pill">{parsed.year}</span> : null}
          {(item.categories || []).slice(0, 3).map((raw, i) => (
            <Link className="pill-btn" href={`/browse?genre=${encodeURIComponent(raw)}`} key={raw}>
              {cats[i]}
            </Link>
          ))}
        </div>
        {extract ? <p className="hero-extract">{extract}</p> : null}
        <p className="hero-hint">I’d watch = you’d sit through it. Poster opens details.</p>
        <div className="actions">
          <button
            className="btn like"
            type="button"
            disabled={busy}
            onClick={() => onAct(item.item_id, "like")}
          >
            {acted === "like" ? "On your ticket" : "I’d watch this"}
          </button>
          <button
            className="btn skip"
            type="button"
            disabled={busy}
            onClick={() => onAct(item.item_id, "skip")}
          >
            {acted === "skip" ? "Skipped" : "Not for me"}
          </button>
          <Link className="btn ghost" href={href}>
            Details
          </Link>
          <a className="btn ghost" href={justWatchUrl(item.title, parsed.year)} target="_blank" rel="noopener noreferrer">
            Watch cheap
          </a>
        </div>
      </div>
    </section>
  );
}

function FindMovie() {
  return (
    <form className="find-movie" action="/browse">
      <label className="field search-field find-field">
        <span>Know a title?</span>
        <input name="q" placeholder="Spiderman, Barbie, Fargo…" aria-label="Search the catalog" data-watchnext-search />
      </label>
      <button className="btn" type="submit">
        Search
      </button>
      <Link className="btn ghost" href="/browse">
        Browse everything
      </Link>
    </form>
  );
}

function Shelf({
  title,
  hint,
  href,
  items,
  acted,
  busy,
  onAct,
  from,
}: {
  title: string;
  hint?: string;
  href?: string;
  items: MovieItem[];
  acted: Record<string, Act>;
  busy: boolean;
  onAct: (id: string, type: Act) => void;
  from?: string;
}) {
  if (!items.length) return null;
  return (
    <section className="shelf">
      <div className="section-head">
        <div>
          <h2>{title}</h2>
          {hint ? <p>{hint}</p> : null}
        </div>
        {href ? (
          <Link className="section-more" href={href}>
            See more
          </Link>
        ) : null}
      </div>
      <div className="poster-grid">
        {items.map((item) => (
          <MovieCard
            key={item.item_id}
            item={item}
            acted={acted[item.item_id]}
            busy={busy}
            onAct={onAct}
            from={from}
          />
        ))}
      </div>
    </section>
  );
}

export default function FeedPage() {
  const { userId, requestFresh } = useUserId();
  const { genres } = useGenres();
  const [marquee, setMarquee] = useState<MovieItem[]>([]);
  const [recent, setRecent] = useState<MovieItem[]>([]);
  const [forYou, setForYou] = useState<MovieItem[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [acted, setActed] = useState<Record<string, Act>>({});
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState<string | null>(null);
  const preloaded = isPreloadedUser(userId);
  const likedCount = Object.values(acted).filter((v) => v === "like").length;
  usePageTitle("Watch Next");

  const loadLobby = useCallback(async () => {
    setError(null);
    setLoading(true);
    try {
      let nowPlaying = (
        await getCatalog({ sort: "year", yearMin: NOW_YEAR - 1, yearMax: NOW_YEAR, limit: 12 })
      ).items;
      if (nowPlaying.length < 8) {
        nowPlaying = (await getCatalog({ sort: "year", yearMin: NOW_YEAR - 2, yearMax: NOW_YEAR, limit: 12 })).items;
      }
      const recentHits = (
        await getCatalog({ sort: "popular", yearMin: NOW_YEAR - 8, yearMax: NOW_YEAR - 1, limit: 16 })
      ).items;
      const shown = new Set(nowPlaying.map((row) => row.item_id));
      setMarquee(uniqueById(nowPlaying));
      setRecent(uniqueById(recentHits).filter((row) => !shown.has(row.item_id)).slice(0, 10));
    } catch (err) {
      setError(friendlySaveError(err));
    } finally {
      setLoading(false);
    }
  }, []);

  const loadForYou = useCallback(async () => {
    if (!userId) return;
    try {
      const data = await api<RecResponse>(`/v1/recommendations/${userId}?limit=36`);
      setActed(actedFromFeatures(data.user_features));
      const banned = new Set([...marquee, ...recent].map((row) => row.item_id));
      const liked = new Set(data.user_features?.liked_items || []);
      const skipped = new Set(data.user_features?.disliked_items || []);
      const picks = (data.recommendations || []).filter(
        (row) => !banned.has(row.item_id) && !liked.has(row.item_id) && !skipped.has(row.item_id),
      );
      const popular = (
        await getCatalog({ sort: "popular", yearMin: NOW_YEAR - 8, yearMax: NOW_YEAR, limit: 24 })
      ).items.filter((row) => !banned.has(row.item_id) && !liked.has(row.item_id) && !skipped.has(row.item_id));
      setForYou(mixTonightBill(picks, popular, liked.size, 10));
    } catch {
      setForYou([]);
    }
  }, [userId, marquee, recent]);

  useEffect(() => {
    loadLobby();
  }, [loadLobby]);

  useEffect(() => {
    if (!userId) return;
    getFeatures(userId)
      .then((feats) => setActed(actedFromFeatures(feats)))
      .catch(() => undefined);
  }, [userId]);

  useEffect(() => {
    if (!userId || loading) return;
    loadForYou();
  }, [userId, loading, loadForYou]);

  async function act(itemId: string, eventType: Act) {
    if (busy || !userId) return;
    const item = [...marquee, ...recent, ...forYou].find((row) => row.item_id === itemId);
    const label = parseMovieTitle(item?.title).display;
    setBusy(true);
    setActed((prev) => ({ ...prev, [itemId]: eventType }));
    if (eventType === "skip") {
      const drop = (rows: MovieItem[]) => rows.filter((row) => row.item_id !== itemId);
      setMarquee(drop);
      setRecent(drop);
      setForYou(drop);
    }
    try {
      let beforeTs: number | null | undefined;
      try {
        beforeTs = (await getFeatures(userId)).feature_updated_at;
      } catch {
        beforeTs = undefined;
      }
      await postEvent(userId, itemId, eventType, item?.title, item?.categories);
      const updated = await waitForFeatureUpdate(userId, beforeTs);
      if (!updated) {
        throw new Error("the like was accepted but Redis never updated. Is the feature consumer running?");
      }
      notifyTicketChanged();
      setActed(actedFromFeatures(updated));
      const liked = (updated.liked_items || []).length;
      setStatus(
        eventType === "like"
          ? liked < 3
            ? `${label} is on your ticket. ${3 - liked} more, then tap Watch next.`
            : `${label} is in. Tap Watch next (bottom right) — that’s the list to pick from tonight.`
          : `Not for you. We’ll show fewer like ${label}.`,
      );
      await loadForYou();
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

  const featured = marquee[0];
  const alsoMarquee = marquee.slice(1, 11);
  const popularGenres = useMemo(
    () => [...genres].sort((a, b) => b.count - a.count).slice(0, 10),
    [genres],
  );

  if (!userId) {
    return (
      <main className="page">
        <p className="lede">Starting your ticket…</p>
      </main>
    );
  }

  return (
    <main className="page">
      {preloaded && (
        <div className="status-banner error">
          Ticket {userId} already has a huge history, so new likes will barely move it.{" "}
          <button className="btn compact" type="button" onClick={() => requestFresh()}>
            Start over
          </button>
        </div>
      )}
      {status ? (
        <div className="status-banner ok" role="status">
          {status}
        </div>
      ) : null}
      {error ? <p className="error">{error}</p> : null}
      <TicketStrip likedCount={likedCount} />
      {loading && !featured ? (
        <div className="poster-grid">
          {Array.from({ length: 10 }).map((_, i) => (
            <div className="poster is-loading" key={i} style={{ aspectRatio: "2 / 3" }} />
          ))}
        </div>
      ) : null}
      {featured ? (
        <Hero item={featured} onAct={act} acted={acted[featured.item_id]} busy={busy} />
      ) : null}
      {likedCount && forYou.length ? (
        <Shelf
          title="What to watch next"
          hint="Known hits mixed with guesses from your ticket — tap Watch next for the full bill"
          href="/debug"
          items={forYou}
          acted={acted}
          busy={busy}
          onAct={act}
          from="foryou"
        />
      ) : null}
      <Shelf
        title="Also on screens"
        hint="New and coming soon — tap I’d watch if you’d sit through it"
        href="/browse"
        items={alsoMarquee}
        acted={acted}
        busy={busy}
        onAct={act}
        from="marquee"
      />
      <FindMovie />
      <Shelf
        title="Recent hits"
        hint="Popular from the last few years"
        href="/browse"
        items={recent}
        acted={acted}
        busy={busy}
        onAct={act}
        from="recent"
      />
      {popularGenres.length ? (
        <section className="shelf">
          <div className="section-head">
            <div>
              <h2>Pick a mood</h2>
              <p>Jump into that genre</p>
            </div>
            <Link className="section-more" href="/browse">
              See all genres
            </Link>
          </div>
          <GenreBar
            genres={popularGenres}
            value=""
            showAll={false}
            hrefFor={(genre) => (genre ? `/browse?genre=${encodeURIComponent(genre)}` : "/browse")}
          />
        </section>
      ) : null}
    </main>
  );
}
