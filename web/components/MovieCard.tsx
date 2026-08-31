"use client";

import Link from "next/link";
import Poster from "@/components/Poster";
import WatchLinks from "@/components/WatchLinks";
import { parseMovieTitle } from "@/lib/titles";
import type { MovieItem } from "@/lib/api";
import { moviePath } from "@/lib/watch";

export default function MovieCard({
  item,
  acted,
  move,
  busy,
  onAct,
  from,
  note,
}: {
  item: MovieItem;
  acted?: "like" | "skip";
  move?: number;
  busy: boolean;
  onAct: (id: string, type: "like" | "skip") => void;
  from?: string;
  note?: string;
}) {
  const parsed = parseMovieTitle(item.title);
  const year = item.year ?? parsed.year;
  const href = moviePath(item.item_id, from);
  return (
    <figure className={`movie-card ${acted ? `is-${acted}` : ""}`}>
      <Link className="movie-hit" href={href} aria-label={`Details for ${parsed.display}`}>
        <Poster title={item.title} />
        {move != null && move !== 0 && (
          <span className={`rank-delta ${move > 0 ? "up" : "down"}`}>
            {move === 99 ? "new" : move > 0 ? `↑${move}` : `↓${Math.abs(move)}`}
          </span>
        )}
        {acted === "like" ? <span className="stamp like">On ticket</span> : null}
        {acted === "skip" ? <span className="stamp skip">Skipped</span> : null}
      </Link>
      <figcaption>
        <h3>
          <Link href={href}>{parsed.display}</Link>
        </h3>
        {note ? <p className="rec-why">{note}</p> : null}
        <div className="caption-meta">
          {[year, item.rating && !item.item_id.startsWith("tt") ? `${item.rating.toFixed(1)}★` : null]
            .filter(Boolean)
            .join(" · ")}
          {" · "}
          <WatchLinks title={item.title} year={year} itemId={item.item_id} compact />
        </div>
        <div className="card-actions">
          <button
            className="icon-btn like"
            type="button"
            disabled={busy}
            onClick={() => onAct(item.item_id, "like")}
          >
            {acted === "like" ? "On ticket" : "I’d watch"}
          </button>
          <button
            className="icon-btn"
            type="button"
            disabled={busy}
            onClick={() => onAct(item.item_id, "skip")}
          >
            {acted === "skip" ? "Skipped" : "Not for me"}
          </button>
        </div>
      </figcaption>
    </figure>
  );
}
