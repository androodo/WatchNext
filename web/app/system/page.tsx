"use client";

import { useEffect, useState } from "react";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8080";

export default function SystemPage() {
  const [health, setHealth] = useState("…");
  const [ready, setReady] = useState("…");
  const [metrics, setMetrics] = useState("");

  async function load() {
    const h = await fetch(`${API}/health`).then((r) => r.json());
    const r = await fetch(`${API}/ready`).then((x) => x.json());
    const m = await fetch(`${API}/metrics`).then((x) => x.text());
    setHealth(h.status);
    setReady(r.status);
    const keep = m
      .split("\n")
      .filter((line) => line.startsWith("pulserank_") && !line.startsWith("pulserank_") === false)
      .filter((line) => !line.startsWith("#"))
      .slice(0, 40);
    setMetrics(keep.join("\n"));
  }

  useEffect(() => {
    load();
  }, []);

  return (
    <main className="page">
      <h1>System</h1>
      <p>health: {health} · ready: {ready}</p>
      <p className="meta">Prometheus scrape of the Go API. Grafana is on :3001 if compose is running.</p>
      <pre className="card">{metrics || "no metrics yet"}</pre>
      <button onClick={load}>Refresh</button>
    </main>
  );
}
