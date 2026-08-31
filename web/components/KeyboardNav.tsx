"use client";

import { useEffect } from "react";

function typingInField(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  return Boolean(target.closest("input, textarea, select, [contenteditable='true']"));
}

export default function KeyboardNav() {
  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (event.key !== "/") return;
      if (event.metaKey || event.ctrlKey || event.altKey) return;
      if (typingInField(event.target)) return;
      const search = document.querySelector<HTMLInputElement>("[data-watchnext-search]");
      if (!search) return;
      event.preventDefault();
      search.focus();
      search.select();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  return (
    <a className="skip-link" href="/debug">
      Skip to Watch next
    </a>
  );
}
