"""Write reports/offline_evaluation.md from computed metrics. Never hardcode scores."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import orjson


def write_evaluation_report(results: dict[str, Any], json_path: Path, md_path: Path) -> None:
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_bytes(orjson.dumps(results, option=orjson.OPT_INDENT_2))

    lines = [
        "# Offline evaluation",
        "",
        "Generated from `scripts/evaluate.py`. Do not edit numbers by hand.",
        "",
        f"- Dataset: `{results.get('dataset', 'unknown')}`",
        f"- Train interactions: {results.get('n_train')}",
        f"- Val interactions: {results.get('n_val')}",
        f"- Test interactions: {results.get('n_test')}",
        f"- Test users evaluated: {results.get('n_eval_users')}",
        f"- Catalog size: {results.get('catalog_size')}",
        "",
        "## Candidate retrieval",
        "",
        "| Source | Recall@50 | Recall@100 | HitRate@50 | HitRate@100 |",
        "|---|---:|---:|---:|---:|",
    ]
    cand = results.get("candidates", {})
    for name, row in cand.items():
        lines.append(
            f"| {name} | {row.get('recall@50', 0):.4f} | {row.get('recall@100', 0):.4f} "
            f"| {row.get('hit_rate@50', 0):.4f} | {row.get('hit_rate@100', 0):.4f} |"
        )
    lines += [
        "",
        "## Ranking (feed metrics on test positives)",
        "",
        "| Method | Precision@10 | Recall@10 | NDCG@10 | MRR | HitRate@10 | Coverage@10 |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    rank = results.get("ranking", {})
    for name, row in rank.items():
        lines.append(
            f"| {name} | {row.get('precision@10', 0):.4f} | {row.get('recall@10', 0):.4f} "
            f"| {row.get('ndcg@10', 0):.4f} | {row.get('mrr', 0):.4f} "
            f"| {row.get('hit_rate@10', 0):.4f} | {row.get('coverage@10', 0):.4f} |"
        )
    lines += [
        "",
        "## Notes",
        "",
        "- Split is **temporal** (earliest 80% train, next 10% val, latest 10% test).",
        "- Test labels are positive events (`like`, `watch`) after the train cutoff.",
        "- Random baseline uses a fixed seed.",
        "- ALS + ranker reranks ALS/popularity candidates; it does not score the full catalog.",
        "",
    ]
    md_path.write_text("\n".join(lines), encoding="utf-8")
