"use client";

import Link from "next/link";
import { useUserId } from "@/lib/useUserId";

export default function TicketStrip({ likedCount }: { likedCount: number }) {
  const { requestFresh } = useUserId();
  const started = likedCount > 0;
  const ready = likedCount >= 3;
  return (
    <section className="ticket-card" aria-label="How Watch Next works">
      <div>
        <p className="page-kicker">Watch Next</p>
        <h1>Pick a few. We’ll pick what to watch next.</h1>
        <p className="lede ticket-lede">
          {ready
            ? "Your taste is on the ticket. Keep tapping — the next bill gets sharper."
            : "Tap I’d watch on movies you’d actually sit through. Skip the rest. That’s the whole site."}
        </p>
        <ol className="play-steps">
          <li className={started ? "is-done" : "is-now"}>I’d watch</li>
          <li className={ready ? "is-done" : started ? "is-now" : ""}>Ticket learns</li>
          <li className={ready ? "is-now" : ""}>We recommend</li>
        </ol>
      </div>
      <div className="ticket-card-actions">
        <Link className="ticket-stamp" href="/debug">
          <strong>{likedCount}</strong>
          <span>{ready ? "on your ticket" : "of 3 to start"}</span>
        </Link>
        <Link className="btn" href="/debug">
          Watch next
        </Link>
        <button className="btn skip" type="button" onClick={() => requestFresh()}>
          Start over
        </button>
      </div>
    </section>
  );
}
