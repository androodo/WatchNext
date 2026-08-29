"use client";

import { useEffect, useState } from "react";
import { API } from "@/lib/api";

export default function SystemPage() {
  const [health, setHealth] = useState("…");
  const [ready, setReady] = useState("…");
  const [metrics, setMetrics] = useState("");
  const [error, setError] = useState<string | null>(null);

  async function load() {
    setError(null);
    try {
      const healthRes = await fetch(`${API}/health`);
      const readyRes = await fetch(`${API}/ready`);
      const metricsRes = await fetch(`${API}/metrics`);
      if (!healthRes.ok) throw new Error(`health ${healthRes.status}`);
      const h = await healthRes.json();
      const r = await readyRes.json();
      const m = await metricsRes.text();
      setHealth(h.status || "unknown");
      setReady(r.status || "unknown");
      const keep = m
        .split("\n")
        .filter((line) => line.startsWith("watchnext_") && !line.startsWith("#"))
        .slice(0, 40);
      setMetrics(keep.join("\n") || "no watchnext_ metrics yet");
    } catch (err) {
      setError(String(err));
    }
  }

  useEffect(() => {
    load();
  }, []);

  return (
    <main className="page">
      <p className="page-kicker">Projection booth</p>
      <h1>Backstage</h1>
      <p className="lede">Whether the API is up. Grafana is on port 3001 if you started the full Docker stack.</p>
      <div className="toolbar">
        <button className="btn" type="button" onClick={load}>
          Refresh
        </button>
      </div>
      {error && <p className="error">{error}</p>}
      <div className="status-grid">
        <div className="status-card">
          <span className="dot" />
          Health
          <strong>{health}</strong>
        </div>
        <div className="status-card">
          <span className="dot" />
          Ready
          <strong>{ready}</strong>
        </div>
      </div>
      <pre className="panel">{metrics || "no metrics yet"}</pre>
    </main>
  );
}
