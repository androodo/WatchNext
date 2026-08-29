"use client";

import { useEffect, useState } from "react";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8080";

type DebugItem = {
  item_id: string;
  source: string;
  retrieval_score: number;
  source_rank: number;
  ranker_score: number;
  title?: string;
};

type DebugResponse = {
  request_id: string;
  model_version: string;
  experiment: string;
  fallback_used: boolean;
  user_features?: { affinities?: Record<string, number> };
  debug?: DebugItem[];
};

export default function DebugPage() {
  const [userId, setUserId] = useState("1001");
  const [data, setData] = useState<DebugResponse | null>(null);

  async function load() {
    const res = await fetch(`${API}/v1/recommendations/${userId}/debug?limit=15`);
    setData(await res.json());
  }

  useEffect(() => {
    load();
  }, []);

  const rows = data?.debug || [];

  return (
    <main className="page">
      <h1>Recommendation debug</h1>
      <p className="meta">Not explainable AI — just retrieval vs ranker scores for one request.</p>
      <div className="row">
        <input value={userId} onChange={(e) => setUserId(e.target.value)} />
        <button onClick={load}>Inspect</button>
      </div>
      {data && (
        <p className="meta">
          {data.request_id} · {data.experiment} · {data.model_version}
          {data.fallback_used ? " · fallback" : ""}
        </p>
      )}
      <table>
        <thead>
          <tr>
            <th>Item</th>
            <th>Source</th>
            <th>Retrieval</th>
            <th>Ranker</th>
            <th>Final</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={row.item_id}>
              <td>{row.title || row.item_id}</td>
              <td>{row.source} #{row.source_rank}</td>
              <td>{row.retrieval_score.toFixed(4)}</td>
              <td>{row.ranker_score.toFixed(4)}</td>
              <td>{i + 1}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </main>
  );
}
