"use client";

import { useEffect, useState } from "react";
import Poster from "@/components/Poster";
import UserSwitcher from "@/components/UserSwitcher";
import { api } from "@/lib/api";
import { parseMovieTitle } from "@/lib/titles";
import { useUserId } from "@/lib/useUserId";

type DebugItem = {
  item_id: string;
  source: string;
  retrieval_score?: number;
  source_rank?: number;
  ranker_score?: number;
  title?: string;
};

type DebugResponse = {
  request_id: string;
  model_version: string;
  experiment: string;
  fallback_used: boolean;
  debug?: DebugItem[];
};

export default function DebugPage() {
  const { userId } = useUserId();
  const [data, setData] = useState<DebugResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  async function load() {
    if (!userId) return;
    setError(null);
    setLoading(true);
    try {
      setData(await api<DebugResponse>(`/v1/recommendations/${userId}/debug?limit=15`));
    } catch (err) {
      setError(String(err));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, [userId]);

  const rows = (data?.debug || []).slice(0, 15);

  return (
    <main className="page">
      <p className="page-kicker">How the bill was cut</p>
      <h1>Ranking</h1>
      <p className="lede">
        These numbers are how the retriever and ranker scored tonight’s list. If you liked 3 movies, that count lives
        on <strong>Liked</strong>. This page still shows about 10–15 titles with scores.
      </p>
      <div className="toolbar">
        <UserSwitcher />
        <button className="btn" type="button" onClick={load} disabled={loading || !userId}>
          Reload
        </button>
      </div>
      {data && (
        <div className="meta-row">
          <span className="chip ok">{data.experiment}</span>
          <span className="chip">{data.model_version}</span>
          {data.fallback_used ? <span className="chip warn">fallback</span> : null}
        </div>
      )}
      {error && <p className="error">{error}</p>}
      <div className="table-wrap panel">
        <table>
          <thead>
            <tr>
              <th>Final</th>
              <th>Title</th>
              <th>Source</th>
              <th>Retrieval</th>
              <th>Ranker</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row, i) => {
              const parsed = parseMovieTitle(row.title);
              return (
                <tr key={row.item_id}>
                  <td>{i + 1}</td>
                  <td>
                    <div className="debug-title">
                      <Poster title={row.title} />
                      <div>
                        <strong>{parsed.display}</strong>
                        <div className="caption-meta">{parsed.year}</div>
                      </div>
                    </div>
                  </td>
                  <td>
                    {row.source} #{row.source_rank ?? "—"}
                  </td>
                  <td>{(row.retrieval_score ?? 0).toFixed(3)}</td>
                  <td>{(row.ranker_score ?? 0).toFixed(3)}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </main>
  );
}
