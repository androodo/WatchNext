/** MovieLens titles look like "Princess Bride, The (1987)" or "Run Lola Run (Lola rennt) (1998)". */

export type ParsedTitle = {
  display: string;
  year: number | null;
  searchNames: string[];
};

const ARTICLES = ["The", "A", "An"] as const;

function flipArticle(name: string): string {
  for (const article of ARTICLES) {
    const suffix = `, ${article}`;
    if (name.endsWith(suffix)) {
      return `${article} ${name.slice(0, -suffix.length)}`;
    }
  }
  return name;
}

function stripArticle(name: string): string {
  for (const article of ARTICLES) {
    const suffix = `, ${article}`;
    if (name.endsWith(suffix)) return name.slice(0, -suffix.length);
    if (name.startsWith(`${article} `)) return name.slice(article.length + 1);
  }
  return name;
}

export function parseMovieTitle(raw: string | undefined | null): ParsedTitle {
  let title = (raw || "").trim();
  if (!title) return { display: "Unknown title", year: null, searchNames: [] };

  let year: number | null = null;
  const yearMatch = title.match(/\((\d{4})\)\s*$/);
  if (yearMatch) {
    year = Number(yearMatch[1]);
    title = title.slice(0, yearMatch.index).trim();
  }
  title = title.replace(/\s*\([^)]*\)\s*$/, "").trim();

  const flipped = flipArticle(title);
  const stripped = stripArticle(title);
  const searchNames = [...new Set([flipped, stripped, title].filter(Boolean))];
  return { display: flipped, year, searchNames };
}

const GENRE_LABELS: Record<string, string> = {
  childrens: "Family",
  sci_fi: "Sci-fi",
  film_noir: "Noir",
};

export function formatCategories(categories: string[] | undefined): string[] {
  return (categories || []).map((raw) => {
    const key = raw.trim().toLowerCase().replaceAll(" ", "_");
    if (GENRE_LABELS[key]) return GENRE_LABELS[key];
    return key.replaceAll("_", " ");
  });
}
