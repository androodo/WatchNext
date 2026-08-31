"use client";

import Link from "next/link";
import { formatCategories } from "@/lib/titles";
import type { GenreCount } from "@/lib/api";

export default function GenreBar({
  genres,
  value,
  onChange,
  hrefFor,
  showAll = true,
}: {
  genres: GenreCount[];
  value: string;
  onChange?: (genre: string) => void;
  hrefFor?: (genre: string) => string;
  showAll?: boolean;
}) {
  const allHref = hrefFor?.("");
  return (
    <div className="genre-bar" role="toolbar" aria-label="Browse by genre">
      {showAll ? (
        allHref ? (
          <Link href={allHref} className={!value ? "active" : undefined}>
            All
          </Link>
        ) : (
          <button type="button" className={!value ? "active" : undefined} onClick={() => onChange?.("")}>
            All
          </button>
        )
      ) : null}
      {genres.map((g) => {
        const href = hrefFor?.(g.name);
        const label = formatCategories([g.name])[0];
        const active = value === g.name;
        if (href) {
          return (
            <Link key={g.name} href={href} className={active ? "active" : undefined}>
              {label}
            </Link>
          );
        }
        return (
          <button
            key={g.name}
            type="button"
            className={active ? "active" : undefined}
            onClick={() => onChange?.(value === g.name ? "" : g.name)}
          >
            {label}
          </button>
        );
      })}
    </div>
  );
}
