"use client";

import { useEffect, useState } from "react";
import Poster from "@/components/Poster";
import UserSwitcher from "@/components/UserSwitcher";
import { getFeatures, type UserFeatures } from "@/lib/api";
import { formatCategories, parseMovieTitle } from "@/lib/titles";
import { isPreloadedUser, useUserId } from "@/lib/useUserId";

export default function ProfilePage() {
  const { userId, startFresh } = useUserId();
  const [features, setFeatures] = useState<UserFeatures | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  async function load() {
    if (!userId) return;
    setError(null);
    setLoading(true);
    try {
      setFeatures(await getFeatures(userId));
    } catch (err) {
      setError(String(err));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, [userId]);

  const affinities = Object.entries(features?.affinities || {}).sort((a, b) => b[1] - a[1]);
  const maxAff = Math.max(0.0001, ...affinities.map(([, v]) => v));
  const liked = (features?.recent_actions || []).filter((row) => row.event_type === "like").reverse();
  const uniqueLiked = features?.liked_items || [];
  const preloaded = isPreloadedUser(userId);

  return (
    <main className="page">
      <p className="page-kicker">Your stub</p>
      <h1>Movies you liked</h1>
      <p className="lede">
        Like three posters under Now showing, then they should show up here — titles and all.
      </p>
      <div className="toolbar">
        <UserSwitcher />
        <button className="btn" type="button" onClick={load} disabled={loading || !userId}>
          Reload
        </button>
      </div>
      {preloaded && (
        <div className="status-banner error">
          User {userId} already has a huge MovieLens history, so the counters will not equal “how many times I clicked
          just now”.{" "}
          <button className="btn compact" type="button" onClick={() => startFresh()}>
            New ticket
          </button>
        </div>
      )}
      {error && <p className="error">{error}</p>}
      {loading && !features ? <p className="lede">Loading profile…</p> : null}
      {features && (
        <>
          <div className="stats">
            <div className="stat">
              <b>{uniqueLiked.length}</b>
              <span>movies you liked</span>
            </div>
            <div className="stat">
              <b>{features.likes_24h ?? 0}</b>
              <span>like events · last 24h</span>
            </div>
            <div className="stat">
              <b>{(features.disliked_items || []).length}</b>
              <span>movies you skipped</span>
            </div>
            <div className="stat">
              <b>{features.interaction_count ?? 0}</b>
              <span>all-time events</span>
            </div>
          </div>
          <section className="panel" style={{ marginBottom: 18 }}>
            <h2 style={{ margin: "0 0 8px", letterSpacing: "-0.03em" }}>Liked movies</h2>
            {liked.length === 0 && uniqueLiked.length === 0 ? (
              <p className="lede">None yet. Go to Now showing, like 3 posters, then hit Reload.</p>
            ) : (
              <div className="liked-row">
                {(liked.length ? liked : uniqueLiked.map((item_id) => ({ item_id, title: item_id, event_type: "like" }))).map(
                  (row) => (
                    <article className="liked-card" key={`${row.item_id}-${row.timestamp || row.title}`}>
                      <Poster title={row.title} />
                      <strong>{parseMovieTitle(row.title).display}</strong>
                    </article>
                  ),
                )}
              </div>
            )}
          </section>
          <section className="panel">
            <h2 style={{ margin: "0 0 8px", letterSpacing: "-0.03em" }}>Category affinities</h2>
            {affinities.length === 0 ? (
              <p className="lede">No genre weights yet — they appear after the first like.</p>
            ) : (
              affinities.slice(0, 12).map(([k, v]) => (
                <div className="affinity" key={k}>
                  <span>{formatCategories([k])[0]}</span>
                  <div className="bar">
                    <i style={{ width: `${Math.max(6, (v / maxAff) * 100)}%` }} />
                  </div>
                  <span>{v.toFixed(2)}</span>
                </div>
              ))
            )}
          </section>
        </>
      )}
    </main>
  );
}
