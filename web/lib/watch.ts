import { parseMovieTitle } from "@/lib/titles";

export type WatchLink = {
  href: string;
  label: string;
  hint: string;
};

export function moviePath(itemId: string, from?: string): string {
  const path = `/movie/${encodeURIComponent(itemId)}`;
  return from ? `${path}?from=${encodeURIComponent(from)}` : path;
}

export function watchQuery(title?: string, year?: number | null): string {
  const parsed = parseMovieTitle(title);
  return [parsed.display, year ?? parsed.year].filter(Boolean).join(" ");
}

export function watchLinks(title?: string, year?: number | null, itemId?: string): WatchLink[] {
  const q = watchQuery(title, year);
  const encoded = encodeURIComponent(q);
  const links: WatchLink[] = [
    {
      href: `https://www.justwatch.com/us/search?q=${encoded}`,
      label: "Where to watch",
      hint: "Compares streaming, rent, and buy so you can pick the cheap option",
    },
    {
      href: `https://www.google.com/search?q=${encodeURIComponent(`watch ${q} streaming cheap OR free`)}`,
      label: "Cheap / free search",
      hint: "Google for free with ads, library apps, or a cheap rental",
    },
    {
      href: `https://www.youtube.com/results?search_query=${encoded}+trailer`,
      label: "Trailer",
      hint: "Official trailers, and sometimes a full movie on YouTube",
    },
  ];
  if (itemId?.startsWith("tt")) {
    links.push({
      href: `https://www.imdb.com/title/${itemId}/`,
      label: "IMDb",
      hint: "Ratings, cast, and more reviews",
    });
  } else {
    links.push({
      href: `https://www.imdb.com/find/?q=${encoded}`,
      label: "IMDb",
      hint: "Ratings, cast, and more reviews",
    });
  }
  return links;
}

export function justWatchUrl(title?: string, year?: number | null): string {
  return `https://www.justwatch.com/us/search?q=${encodeURIComponent(watchQuery(title, year))}`;
}
