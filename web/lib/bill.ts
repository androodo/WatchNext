import type { MovieItem } from "@/lib/api";

/** Titles people actually recognize — not just “came out this year.” */
const NOTABLE_POPULARITY = 0.36;

export function uniqueById(rows: MovieItem[]): MovieItem[] {
  const seen = new Set<string>();
  const out: MovieItem[] = [];
  for (const row of rows) {
    if (!row.item_id || seen.has(row.item_id)) continue;
    seen.add(row.item_id);
    out.push(row);
  }
  return out;
}

export function isNotable(row: MovieItem): boolean {
  return (row.popularity ?? 0) >= NOTABLE_POPULARITY;
}

export function mixTonightBill(
  ranked: MovieItem[],
  popular: MovieItem[],
  likedCount: number,
  limit = 24,
): MovieItem[] {
  const pool = uniqueById(popular);
  if (likedCount <= 0) return pool.slice(0, limit);
  const popById = new Map(pool.map((row) => [row.item_id, row.popularity ?? 0]));
  const hydrated = ranked.map((row) => {
    if ((row.popularity ?? 0) > 0) return row;
    const pop = popById.get(row.item_id);
    return pop ? { ...row, popularity: pop } : row;
  });
  const notables = uniqueById(hydrated.filter(isNotable));
  if (likedCount >= 3 && notables.length >= Math.min(8, limit)) {
    return notables.slice(0, limit);
  }
  const guesses = notables;
  if (!guesses.length) return pool.slice(0, limit);
  const out: MovieItem[] = [];
  const seen = new Set<string>();
  const push = (row?: MovieItem) => {
    if (!row || seen.has(row.item_id)) return;
    seen.add(row.item_id);
    out.push(row);
  };
  let g = 0;
  let p = 0;
  while (out.length < limit && (g < guesses.length || p < pool.length)) {
    // Sparse ticket: known hits first, then a guess from the model.
    if (out.length % 2 === 0) push(pool[p++] ?? guesses[g++]);
    else push(guesses[g++] ?? pool[p++]);
  }
  return out;
}
