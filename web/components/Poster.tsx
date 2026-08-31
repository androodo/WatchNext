"use client";

import { useEffect, useState } from "react";
import { parseMovieTitle } from "@/lib/titles";

type PosterInfo = { url: string | null; extract: string | null; wikiTitle: string | null };

const memory = new Map<string, PosterInfo>();

export function usePoster(title?: string) {
  const key = title || "";
  const [info, setInfo] = useState<PosterInfo | null>(() => memory.get(key) || null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    if (!key) return;
    const cached = memory.get(key);
    if (cached) {
      setInfo(cached);
      setFailed(false);
      return;
    }
    let cancelled = false;
    setFailed(false);
    fetch(`/api/poster?title=${encodeURIComponent(key)}`)
      .then((res) => (res.ok ? res.json() : { url: null, extract: null, wikiTitle: null }))
      .then((data: PosterInfo) => {
        if (cancelled) return;
        memory.set(key, data);
        setInfo(data);
      })
      .catch(() => {
        if (!cancelled) setInfo({ url: null, extract: null, wikiTitle: null });
      });
    return () => {
      cancelled = true;
    };
  }, [key]);

  return { ...info, failed, setFailed, loading: !key ? false : info === null };
}

function hashHue(title: string): number {
  let h = 0;
  for (let i = 0; i < title.length; i++) h = (h * 31 + title.charCodeAt(i)) >>> 0;
  return h % 360;
}

type PosterProps = {
  title?: string;
  className?: string;
  hideFallbackTitle?: boolean;
};

export default function Poster({ title, className, hideFallbackTitle }: PosterProps) {
  const parsed = parseMovieTitle(title);
  const { url, failed, setFailed, loading } = usePoster(title);
  const hue = hashHue(parsed.display);
  const showImage = Boolean(url) && !failed;

  return (
    <div
      className={`poster ${className || ""} ${loading ? "is-loading" : ""}`}
      style={{ ["--poster-hue" as string]: hue }}
    >
      {showImage ? (
        // Wikimedia posters; referrerPolicy avoids hotlink blocks.
        // eslint-disable-next-line @next/next/no-img-element
        <img src={url!} alt={parsed.display} referrerPolicy="no-referrer" onError={() => setFailed(true)} />
      ) : loading ? null : hideFallbackTitle ? (
        <div className="poster-fallback poster-fallback-quiet" aria-hidden="true" />
      ) : (
        <div className="poster-fallback">
          <span className="poster-kicker">{parsed.year || "Film"}</span>
          <span className="poster-title">{parsed.display}</span>
        </div>
      )}
    </div>
  );
}
