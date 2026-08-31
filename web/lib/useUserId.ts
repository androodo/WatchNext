"use client";

import { createContext, createElement, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";

const KEY = "watchnext_user_id";

export function newGuestId(): string {
  return `guest-${Math.random().toString(36).slice(2, 8)}`;
}

export function isPreloadedUser(userId: string): boolean {
  return /^\d+$/.test(userId.trim());
}

type UserContextValue = {
  userId: string;
  draft: string;
  setDraft: (value: string) => void;
  commit: (next?: string) => string;
  startFresh: () => string;
  requestFresh: () => void;
  confirmFresh: () => string;
  cancelFresh: () => void;
  freshOpen: boolean;
};

const UserContext = createContext<UserContextValue | null>(null);

export function UserProvider({ children }: { children: ReactNode }) {
  const [userId, setUserId] = useState("");
  const [draft, setDraft] = useState("");
  const [freshOpen, setFreshOpen] = useState(false);

  useEffect(() => {
    const stored = window.localStorage.getItem(KEY)?.trim();
    const initial = stored || newGuestId();
    if (!stored) window.localStorage.setItem(KEY, initial);
    setUserId(initial);
    setDraft(initial);
  }, []);

  const commit = useCallback((next?: string) => {
    const value = (next ?? draft).trim() || newGuestId();
    setDraft(value);
    setUserId(value);
    window.localStorage.setItem(KEY, value);
    return value;
  }, [draft]);

  const startFresh = useCallback(() => commit(newGuestId()), [commit]);
  const requestFresh = useCallback(() => setFreshOpen(true), []);
  const cancelFresh = useCallback(() => setFreshOpen(false), []);
  const confirmFresh = useCallback(() => {
    setFreshOpen(false);
    return commit(newGuestId());
  }, [commit]);

  const value = useMemo(
    () => ({
      userId,
      draft,
      setDraft,
      commit,
      startFresh,
      requestFresh,
      confirmFresh,
      cancelFresh,
      freshOpen,
    }),
    [userId, draft, commit, startFresh, requestFresh, confirmFresh, cancelFresh, freshOpen],
  );

  return createElement(UserContext.Provider, { value }, children);
}

export function useUserId(): UserContextValue {
  const ctx = useContext(UserContext);
  if (!ctx) {
    throw new Error("useUserId must be used within UserProvider");
  }
  return ctx;
}
