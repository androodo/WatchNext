"use client";

import { FormEvent } from "react";
import { useUserId } from "@/lib/useUserId";

export default function UserSwitcher() {
  const { draft, setDraft, commit, userId, startFresh } = useUserId();
  const dirty = draft.trim() !== userId;

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    commit();
  }

  return (
    <div className="toolbar-group">
      <form className="field" onSubmit={onSubmit}>
        <span>Ticket</span>
        <input
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          aria-label="User id"
        />
        <button className="btn ghost compact" type="submit" disabled={!dirty}>
          Load
        </button>
      </form>
      <button className="btn ghost" type="button" onClick={() => startFresh()}>
        New ticket
      </button>
    </div>
  );
}
