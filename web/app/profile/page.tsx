"use client";

import { useEffect, useState } from "react";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8080";

export default function ProfilePage() {
  const [userId, setUserId] = useState("1001");
  const [features, setFeatures] = useState<Record<string, unknown> | null>(null);

  async function load() {
    const res = await fetch(`${API}/v1/users/${userId}/features`);
    const body = await res.json();
    setFeatures(body.features);
  }

  useEffect(() => {
    load();
  }, []);

  const affinities = (features?.affinities || {}) as Record<string, number>;

  return (
    <main className="page">
      <h1>User profile</h1>
      <div className="row">
        <input value={userId} onChange={(e) => setUserId(e.target.value)} />
        <button onClick={load}>Load</button>
      </div>
      {features && (
        <section className="card" style={{ marginTop: 16 }}>
          <p>interactions: {String(features.interaction_count)}</p>
          <p>likes 24h: {String(features.likes_24h)} · skips 24h: {String(features.skips_24h)}</p>
          <p>avg engagement: {String(features.avg_engagement)}</p>
          <h3>Category affinities</h3>
          <table>
            <tbody>
              {Object.entries(affinities)
                .sort((a, b) => b[1] - a[1])
                .map(([k, v]) => (
                  <tr key={k}>
                    <td>{k}</td>
                    <td>{v.toFixed(4)}</td>
                  </tr>
                ))}
            </tbody>
          </table>
        </section>
      )}
    </main>
  );
}
