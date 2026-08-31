import { formatCategories } from "@/lib/titles";
import type { MovieItem, UserFeatures } from "@/lib/api";

const NOW_YEAR = new Date().getFullYear();

export function sourceWhy(source?: string): string {
  if (source === "als") {
    return "People with similar tickets also sat through this.";
  }
  if (source === "imdb") {
    return "This is from the live catalog (titles after 2000), mixed in so the bill isn’t stuck in the ’90s.";
  }
  if (source === "popularity" || source === "catalog") {
    return "A lot of people in this house have already watched this.";
  }
  return "It scored high enough to make the shortlist.";
}

export function explainPlacement(
  item: Pick<MovieItem, "item_id" | "categories" | "year" | "source" | "popularity" | "title">,
  feats: UserFeatures | null | undefined,
  from?: string | null,
): string[] {
  const reasons: string[] = [];
  const year = item.year;
  if (from === "marquee" || (year != null && year >= NOW_YEAR - 1)) {
    reasons.push(`It’s a ${year ?? "current"} title, so it sits on this year’s marquee — not the old training pile.`);
  } else if (from === "recent" || (year != null && year >= NOW_YEAR - 8)) {
    reasons.push(`${year} is recent enough to show under Recent hits.`);
  }
  if (from === "foryou") {
    reasons.push("This row is the model’s “because you liked a few,” using genre taste plus recency.");
  }
  const aff = feats?.affinities || {};
  const hits = (item.categories || [])
    .filter((c) => (aff[c] || 0) > 0.05)
    .sort((a, b) => (aff[b] || 0) - (aff[a] || 0));
  if (hits.length) {
    const labels = formatCategories(hits.slice(0, 2));
    reasons.push(
      `Your ticket leans ${labels.join(" and ")}, and this film is tagged that way, so it gets a bump.`,
    );
  }
  reasons.push(sourceWhy(item.source));
  if ((item.popularity || 0) > 0.45) {
    reasons.push("It’s one of the more-watched titles in this house.");
  }
  if (feats?.liked_items?.includes(item.item_id)) {
    reasons.push("You already liked this — it’s on your ticket.");
  }
  if (!reasons.length) {
    reasons.push("It’s in the catalog. Like or skip to teach the bill what you want next.");
  }
  return [...new Set(reasons)];
}

export function recWhyLine(
  item: Pick<MovieItem, "item_id" | "categories" | "year" | "source" | "popularity" | "title">,
  feats: UserFeatures | null | undefined,
): string {
  const reasons = explainPlacement(item, feats, "foryou");
  const taste = reasons.find((row) => row.includes("leans"));
  if (taste) return taste;
  const rest = reasons.find(
    (row) =>
      !row.includes("already liked") &&
      !row.includes("because you liked") &&
      !row.includes("catalog"),
  );
  return rest || "Picked from the movies you marked I’d watch.";
}

export function rankingPlainTalk(row: {
  source?: string;
  retrieval_score?: number;
  ranker_score?: number;
}): { pull: string; rank: string } {
  return {
    pull: sourceWhy(row.source),
    rank:
      row.ranker_score != null
        ? "The ranker then scored it for your ticket (genre likes, recency, and how people like you rated similar films). Higher is “show this sooner,” not stars out of 5."
        : "Tonight this user is in the control bucket, so order is mostly the retrieval score — no extra ranker pass.",
  };
}
