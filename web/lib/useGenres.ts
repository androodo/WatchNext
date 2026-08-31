"use client";

import { useEffect, useState } from "react";
import { getGenres, type GenreCount } from "@/lib/api";

export function useGenres() {
  const [genres, setGenres] = useState<GenreCount[]>([]);
  const [totalItems, setTotalItems] = useState(0);
  const [liveItems, setLiveItems] = useState(0);
  const [yearMin, setYearMin] = useState<number | null>(null);
  const [yearMax, setYearMax] = useState<number | null>(null);
  const [updatedAt, setUpdatedAt] = useState<string | null>(null);

  useEffect(() => {
    getGenres()
      .then((body) => {
        setGenres(body.genres || []);
        setTotalItems(body.total_items || 0);
        setLiveItems(body.live_items || 0);
        setYearMin(body.year_min ?? null);
        setYearMax(body.year_max ?? null);
        setUpdatedAt(body.updated_at || null);
      })
      .catch(() => {
        setGenres([]);
      });
  }, []);

  return { genres, totalItems, liveItems, yearMin, yearMax, updatedAt };
}
