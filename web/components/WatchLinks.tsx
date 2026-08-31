"use client";

import { watchLinks, justWatchUrl } from "@/lib/watch";

export default function WatchLinks({
  title,
  year,
  itemId,
  compact = false,
}: {
  title?: string;
  year?: number | null;
  itemId?: string;
  compact?: boolean;
}) {
  if (compact) {
    return (
      <a
        className="watch-cheap"
        href={justWatchUrl(title, year)}
        target="_blank"
        rel="noopener noreferrer"
      >
        Watch cheap
      </a>
    );
  }
  const links = watchLinks(title, year, itemId);
  return (
    <div className="watch-panel">
      <h2>Where to watch it cheap</h2>
      <p>
        We don’t pretend to know if Netflix has it tonight. These open a comparison and a cheap-search so you can pick
        a rental, a free-with-ads stream, or a library app.
      </p>
      <div className="watch-links">
        {links.map((link) => (
          <a key={link.href} className="watch-card" href={link.href} target="_blank" rel="noopener noreferrer">
            <strong>{link.label}</strong>
            <span>{link.hint}</span>
          </a>
        ))}
      </div>
    </div>
  );
}
