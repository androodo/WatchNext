"use client";

import { Suspense, useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import GenreBar from "@/components/GenreBar";
import MovieCard from "@/components/MovieCard";
import {
  actedFromFeatures,
  friendlySaveError,
  getCatalog,
  getFeatures,
  notifyTicketChanged,
  postEvent,
  waitForFeatureUpdate,
  type MovieItem,
} from "@/lib/api";
import { formatCategories, parseMovieTitle } from "@/lib/titles";
import { useGenres } from "@/lib/useGenres";
import { usePageTitle } from "@/lib/usePageTitle";
import { useUserId } from "@/lib/useUserId";

const PAGE = 48;
const NOW_YEAR = new Date().getFullYear();

type Era = "now" | "recent" | "live" | "classics" | "any";

function eraYears(era: Era): { yearMin?: number; yearMax?: number } {
  if (era === "now") return { yearMin: NOW_YEAR - 1, yearMax: NOW_YEAR };
  if (era === "recent") return { yearMin: NOW_YEAR - 8, yearMax: NOW_YEAR };
  if (era === "live") return { yearMin: 2001 };
  if (era === "classics") return { yearMax: 2000 };
  return {};
}

function parseEra(raw: string | null, searching: boolean): Era {
  if (raw === "now" || raw === "recent" || raw === "live" || raw === "classics" || raw === "any") return raw;
  return searching ? "any" : "recent";
}

function browseQuery(q: string, genre: string, sort: string, when: Era): string {
  const params = new URLSearchParams();
  if (q) params.set("q", q);
  if (genre) params.set("genre", genre);
  if (sort && sort !== "year") params.set("sort", sort);
  const implicit: Era = q ? "any" : "recent";
  if (when !== implicit) params.set("when", when);
  const qs = params.toString();
  return qs ? `/browse?${qs}` : "/browse";
}

export default function BrowsePage() {
  return (
    <Suspense
      fallback={
        <main className="page">
          <p className="lede">Looking through the house…</p>
        </main>
      }
    >
      <BrowseInner />
    </Suspense>
  );
}

function BrowseInner() {
  const { userId } = useUserId();
  const { genres } = useGenres();
  const router = useRouter();
  const searchParams = useSearchParams();
  const urlQ = (searchParams.get("q") || "").trim();
  const urlGenre = searchParams.get("genre") || "";
  const urlSort = searchParams.get("sort") || "year";
  const urlWhen = parseEra(searchParams.get("when"), Boolean(urlQ));
  const [q, setQ] = useState(urlQ);
  const [draft, setDraft] = useState(urlQ);
  const [genre, setGenre] = useState(urlGenre);
  const [sort, setSort] = useState(urlSort);
  const [when, setWhen] = useState<Era>(urlWhen);
  const [items, setItems] = useState<MovieItem[]>([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [acted, setActed] = useState<Record<string, "like" | "skip">>({});
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState<string | null>(null);
  const [hidePicked, setHidePicked] = useState(true);

  usePageTitle(q ? `“${q}” · Find a movie` : "Find a movie · Watch Next");

  useEffect(() => {
    setGenre(urlGenre);
    setDraft(urlQ);
    setQ(urlQ);
    setSort(urlSort);
    setWhen(urlWhen);
  }, [urlQ, urlGenre, urlSort, urlWhen]);

  useEffect(() => {
    const t = window.setTimeout(() => setQ(draft.trim()), 250);
    return () => window.clearTimeout(t);
  }, [draft]);

  useEffect(() => {
    const next = browseQuery(q, genre, sort, when);
    if (`${window.location.pathname}${window.location.search}` !== next) {
      router.replace(next, { scroll: false });
    }
  }, [q, genre, sort, when, router]);

  const load = useCallback(
    async (nextOffset: number, append: boolean) => {
      setError(null);
      if (!append) {
        setLoading(true);
        setItems([]);
        setTotal(0);
      }
      try {
        const years = q ? {} : eraYears(when);
        const page = await getCatalog({ q, genre, sort, limit: PAGE, offset: nextOffset, ...years });
        setItems((prev) => (append ? [...prev, ...page.items] : page.items));
        setTotal(page.total);
        setOffset(nextOffset);
      } catch (err) {
        setError(friendlySaveError(err));
      } finally {
        setLoading(false);
      }
    },
    [q, genre, sort, when],
  );

  useEffect(() => {
    load(0, false);
  }, [load]);

  useEffect(() => {
    if (!userId) return;
    getFeatures(userId)
      .then((feats) => setActed(actedFromFeatures(feats)))
      .catch(() => undefined);
  }, [userId]);

  async function act(itemId: string, eventType: "like" | "skip") {
    if (busy || !userId) return;
    const item = items.find((row) => row.item_id === itemId);
    const label = parseMovieTitle(item?.title).display;
    setBusy(true);
    setActed((prev) => ({ ...prev, [itemId]: eventType }));
    setStatus(eventType === "like" ? `Saving like for ${label}…` : `Saving skip for ${label}…`);
    try {
      let beforeTs: number | null | undefined;
      try {
        beforeTs = (await getFeatures(userId)).feature_updated_at;
      } catch {
        beforeTs = undefined;
      }
      await postEvent(userId, itemId, eventType, item?.title, item?.categories);
      const updated = await waitForFeatureUpdate(userId, beforeTs);
      if (!updated) throw new Error("Redis never updated. Is the feature consumer running?");
      notifyTicketChanged();
      setActed(actedFromFeatures(updated));
      setStatus(
        eventType === "like"
          ? `Liked ${label}. Tap Watch next (bottom right) when you want tonight’s bill.`
          : `Skipped ${label}.`,
      );
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

  const label = genre ? formatCategories([genre])[0] : "every genre";
  const visible = hidePicked ? items.filter((row) => !acted[row.item_id]) : items;
  const hidden = items.length - visible.length;

  return (
    <main className="page">
      <p className="page-kicker">The house</p>
      <h1>Find a movie</h1>
      <p className="lede">
        Search or skim the newest titles, tap I’d watch, then hit{" "}
        <Link href="/debug">Watch next</Link> when you want a list to pick from.
      </p>
      <div className="toolbar">
        <form
          className="field search-field"
          onSubmit={(e) => {
            e.preventDefault();
            setQ(draft.trim());
          }}
        >
          <span>Search</span>
          <input
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            placeholder="Spiderman, Matrix, Barbie…"
            aria-label="Search movies"
            data-watchnext-search
          />
        </form>
        <label className="field">
          <span>When</span>
          <select value={when} onChange={(e) => setWhen(e.target.value as Era)} aria-label="Year range">
            <option value="now">This year</option>
            <option value="recent">Last few years</option>
            <option value="live">2001 on</option>
            <option value="classics">Before 2001</option>
            <option value="any">Any year</option>
          </select>
        </label>
        <label className="field">
          <span>Sort</span>
          <select value={sort} onChange={(e) => setSort(e.target.value)} aria-label="Sort movies">
            <option value="year">Newest</option>
            <option value="popular">Most watched</option>
            <option value="title">Title</option>
          </select>
        </label>
        <label className="chip-toggle">
          <input type="checkbox" checked={hidePicked} onChange={(e) => setHidePicked(e.target.checked)} />
          Hide ones I already picked
        </label>
      </div>
      <GenreBar genres={genres} value={genre} onChange={setGenre} />
      <p className="catalog-meta" aria-live="polite">
        {loading && !items.length
          ? "Looking through the house…"
          : `${total.toLocaleString()} title${total === 1 ? "" : "s"}${genre ? ` in ${label}` : ""}${
              q
                ? ` matching “${q}”`
                : when === "now"
                  ? ` from ${NOW_YEAR - 1}–${NOW_YEAR}`
                  : when === "recent"
                    ? ` from ${NOW_YEAR - 8}–${NOW_YEAR}`
                    : when === "live"
                      ? " from 2001 on"
                      : when === "classics"
                        ? " before 2001"
                        : ""
            }${hidden ? ` · hiding ${hidden} you already voted on` : ""}`}
      </p>
      {status ? (
        <div className="status-banner ok" role="status">
          {status}
        </div>
      ) : null}
      {error ? <p className="error">{error}</p> : null}
      {loading && items.length === 0 ? (
        <div className="poster-grid">
          {Array.from({ length: 15 }).map((_, i) => (
            <div className="poster is-loading" key={i} style={{ aspectRatio: "2 / 3" }} />
          ))}
        </div>
      ) : visible.length === 0 ? (
        <section className="next-empty">
          <h2>{q ? `Nothing matching “${q}”` : "Nothing left in this aisle"}</h2>
          <p>
            {hidePicked && hidden
              ? "You’ve already voted on everything on this page. Uncheck “Hide ones I already picked,” or try another genre."
              : "Try a shorter search, another year range, or sort by Most watched."}
          </p>
        </section>
      ) : (
        <div className="poster-grid">
          {visible.map((item) => (
            <MovieCard
              key={item.item_id}
              item={item}
              acted={acted[item.item_id]}
              busy={busy || !userId}
              onAct={act}
            />
          ))}
        </div>
      )}
      {items.length < total ? (
        <div className="toolbar" style={{ marginTop: 28 }}>
          <button className="btn" type="button" disabled={loading} onClick={() => load(offset + PAGE, true)}>
            Load more
          </button>
          <span className="chip ok">
            {items.length} of {total}
          </span>
        </div>
      ) : null}
    </main>
  );
}
