"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import GenreBar from "@/components/GenreBar";
import { API, friendlySaveError, getGenres, refreshCatalog, type GenreCount } from "@/lib/api";
import { usePageTitle } from "@/lib/usePageTitle";

type HouseInfo = {
  genres: GenreCount[];
  total_items: number;
  live_items?: number;
  year_min?: number | null;
  year_max?: number | null;
  updated_at?: string | null;
};

function formatStamp(iso: string | null | undefined): string {
  if (!iso) return "this session";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return date.toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
}

export default function SystemPage() {
  const [house, setHouse] = useState<HouseInfo | null>(null);
  usePageTitle("House · Watch Next");
  const [open, setOpen] = useState<boolean | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [catalogNote, setCatalogNote] = useState<string | null>(null);
  const [catalogOk, setCatalogOk] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  async function load() {
    setError(null);
    try {
      const [healthRes, readyRes, catalog] = await Promise.all([
        fetch(`${API}/health`),
        fetch(`${API}/ready`),
        getGenres(),
      ]);
      const health = healthRes.ok ? await healthRes.json() : {};
      const ready = readyRes.ok ? await readyRes.json() : {};
      setOpen(health.status === "ok" && ready.status === "ready");
      setHouse(catalog);
    } catch (err) {
      setError(friendlySaveError(err));
      setOpen(false);
    }
  }

  async function updateHouse() {
    setRefreshing(true);
    setCatalogOk(true);
    setCatalogNote("Pulling a fresher title list. This can take a minute.");
    try {
      const body = await refreshCatalog();
      setHouse(body);
      const years = body.year_min && body.year_max ? ` · ${body.year_min}–${body.year_max}` : "";
      const live = body.live_items ? ` · ${body.live_items.toLocaleString()} from 2001 on` : "";
      setCatalogOk(true);
      setCatalogNote(
        `House updated: ${(body.total_items || 0).toLocaleString()} titles${years}${live}. Now showing will pick from this.`,
      );
    } catch (err) {
      setCatalogOk(false);
      setCatalogNote(`Could not refresh the house: ${friendlySaveError(err)}`);
    } finally {
      setRefreshing(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  const genres = [...(house?.genres || [])].sort((a, b) => b.count - a.count);
  const years =
    house?.year_min && house?.year_max ? `${house.year_min}–${house.year_max}` : "—";

  return (
    <main className="page">
      <p className="page-kicker">Projection booth</p>
      <h1>What’s in the house</h1>
      <p className="lede">
        This is the library, not tonight’s recs. See how many titles are on the shelves, how recent they go, and pull a
        fresher set if the bill looks stuck. Jump a genre to{" "}
        <Link href="/browse">Find a movie</Link>.
      </p>
      <div className="toolbar">
        <button className="btn" type="button" onClick={load}>
          Reload
        </button>
        <button className="btn like" type="button" onClick={updateHouse} disabled={refreshing}>
          {refreshing ? "Updating titles…" : "Pull newer titles"}
        </button>
      </div>
      {catalogNote ? (
        <div className={`status-banner ${catalogOk ? "ok" : "error"}`} role="status">
          {catalogNote}
        </div>
      ) : null}
      {error ? (
        <section className="next-empty" aria-label="House unavailable">
          <h2>The booth is dark</h2>
          <p>{error} Hit Reload once the house is running again.</p>
        </section>
      ) : null}
      <div className="stats">
        <div className="stat">
          <b>{open == null ? "…" : open ? "Open" : "Dark"}</b>
          <span>recommender</span>
        </div>
        <div className="stat">
          <b>{house ? house.total_items.toLocaleString() : "…"}</b>
          <span>titles on the shelves</span>
        </div>
        <div className="stat">
          <b>{house?.live_items != null ? house.live_items.toLocaleString() : "…"}</b>
          <span>from 2001 on</span>
        </div>
        <div className="stat">
          <b>{years}</b>
          <span>years in the house</span>
        </div>
      </div>
      <p className="catalog-meta">Last pulled {formatStamp(house?.updated_at)}</p>
      {genres.length ? (
        <section className="shelf" style={{ marginTop: 8 }}>
          <div className="section-head">
            <div>
              <h2>Browse a genre</h2>
              <p>Same shelves as Find a movie — this is just a quicker hop.</p>
            </div>
          </div>
          <GenreBar
            genres={genres}
            value=""
            showAll={false}
            hrefFor={(genre) => `/browse?genre=${encodeURIComponent(genre)}`}
          />
        </section>
      ) : null}
    </main>
  );
}
