"use client";

import { useEffect, useRef } from "react";
import { useUserId } from "@/lib/useUserId";

export default function TicketResetDialog() {
  const { freshOpen, confirmFresh, cancelFresh } = useUserId();
  const ref = useRef<HTMLDialogElement>(null);
  const keepRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!freshOpen) return;
    const node = ref.current;
    if (!node) return;
    if (!node.open) node.showModal();
    keepRef.current?.focus();
  }, [freshOpen]);

  if (!freshOpen) return null;

  return (
    <dialog
      ref={ref}
      className="ticket-dialog"
      aria-labelledby="ticket-reset-title"
      onCancel={(e) => {
        e.preventDefault();
        cancelFresh();
      }}
      onClick={(e) => {
        if (e.target === ref.current) cancelFresh();
      }}
    >
      <form
        method="dialog"
        className="ticket-dialog-card"
        onSubmit={(e) => {
          e.preventDefault();
          confirmFresh();
        }}
      >
        <p className="page-kicker">Ticket</p>
        <h2 id="ticket-reset-title">Start a new ticket?</h2>
        <p>
          This throws out this ticket’s likes, skips, and ranking. You get a blank taste and a new bill. You cannot undo
          it.
        </p>
        <div className="actions">
          <button className="btn ghost" type="button" ref={keepRef} onClick={() => cancelFresh()}>
            Keep this ticket
          </button>
          <button className="btn like" type="submit">
            Start over
          </button>
        </div>
      </form>
    </dialog>
  );
}
