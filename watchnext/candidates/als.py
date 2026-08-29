"""ALS collaborative filtering via the implicit library."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import orjson
from scipy import sparse

from watchnext.common.constants import CANDIDATE_K, POSITIVE_EVENT_TYPES

try:
    from implicit.als import AlternatingLeastSquares
except ImportError:  # pragma: no cover
    AlternatingLeastSquares = None


class ALSModel:
    def __init__(
        self,
        user_map: dict[str, int],
        item_map: dict[str, int],
        user_factors: np.ndarray,
        item_factors: np.ndarray,
        user_items: sparse.csr_matrix,
    ) -> None:
        self.user_map = user_map
        self.item_map = item_map
        self.inv_item = {i: k for k, i in item_map.items()}
        self.inv_user = {i: k for k, i in user_map.items()}
        self.user_factors = user_factors
        self.item_factors = item_factors
        self.user_items = user_items

    def recommend(
        self,
        user_id: str,
        k: int = CANDIDATE_K,
        exclude: set[str] | None = None,
    ) -> list[dict[str, Any]]:
        uid = self.user_map.get(str(user_id))
        if uid is None:
            return []
        user_vec = self.user_factors[uid]
        scores = self.item_factors @ user_vec
        seen = set(self.user_items[uid].indices.tolist())
        if exclude:
            for item in exclude:
                idx = self.item_map.get(str(item))
                if idx is not None:
                    seen.add(idx)
        for idx in seen:
            scores[idx] = -1e9
        k = min(k, scores.shape[0])
        # argpartition for top-k
        top = np.argpartition(scores, -k)[-k:]
        top = top[np.argsort(scores[top])[::-1]]
        out = []
        for rank, idx in enumerate(top, start=1):
            if scores[idx] <= -1e8:
                continue
            out.append(
                {
                    "item_id": self.inv_item[int(idx)],
                    "source": "als",
                    "retrieval_score": round(float(scores[idx]), 6),
                    "source_rank": rank,
                }
            )
        return out


def _confidence_matrix(
    user_ids: list[str],
    item_ids: list[str],
    values: list[float],
    user_map: dict[str, int],
    item_map: dict[str, int],
) -> sparse.csr_matrix:
    rows = [user_map[u] for u in user_ids]
    cols = [item_map[i] for i in item_ids]
    data = np.array(values, dtype=np.float32)
    data = np.clip(data, 0.01, None)
    return sparse.coo_matrix(
        (data, (rows, cols)),
        shape=(len(user_map), len(item_map)),
    ).tocsr()


def _train_als_numpy(
    user_items: sparse.csr_matrix,
    factors: int,
    regularization: float,
    iterations: int,
    random_state: int,
) -> tuple[np.ndarray, np.ndarray]:
    """Hu–Koren–Volinsky implicit ALS. Used when `implicit` is unavailable."""
    rng = np.random.default_rng(random_state)
    n_users, n_items = user_items.shape
    X = rng.normal(0, 0.1, size=(n_users, factors)).astype(np.float64)
    Y = rng.normal(0, 0.1, size=(n_items, factors)).astype(np.float64)
    alpha = 15.0
    Cui = user_items.astype(np.float64)
    Ciu = Cui.T.tocsr()

    def _least_squares(latent: np.ndarray, other: np.ndarray, conf: sparse.csr_matrix) -> None:
        n = conf.shape[0]
        yt_y = other.T @ other
        eye = np.eye(factors) * regularization
        for i in range(n):
            start, end = conf.indptr[i], conf.indptr[i + 1]
            if start == end:
                continue
            idx = conf.indices[start:end]
            pref = conf.data[start:end]
            c = 1.0 + alpha * pref
            Y_i = other[idx]
            a = yt_y + (Y_i.T * (c - 1.0)) @ Y_i + eye
            b = (Y_i.T * c) @ np.ones(len(idx))
            latent[i] = np.linalg.solve(a, b)

    for _ in range(iterations):
        _least_squares(X, Y, Cui)
        _least_squares(Y, X, Ciu)
    return X.astype(np.float32), Y.astype(np.float32)


def train_als(
    train,
    factors: int = 64,
    regularization: float = 0.08,
    iterations: int = 15,
    random_state: int = 42,
) -> ALSModel:
    import polars as pl

    pos = train.filter(pl.col("event_type").is_in(list(POSITIVE_EVENT_TYPES)))
    if pos.is_empty():
        pos = train.filter(pl.col("value") > 0)

    users = sorted({str(u) for u in pos["user_id"].to_list()})
    items = sorted({str(i) for i in train["item_id"].to_list()})
    user_map = {u: i for i, u in enumerate(users)}
    item_map = {it: i for i, it in enumerate(items)}

    conf = [max(float(v), 0.01) for v in pos["value"].to_list()]
    user_items = _confidence_matrix(
        [str(u) for u in pos["user_id"].to_list()],
        [str(i) for i in pos["item_id"].to_list()],
        conf,
        user_map,
        item_map,
    )

    if AlternatingLeastSquares is not None:
        model = AlternatingLeastSquares(
            factors=factors,
            regularization=regularization,
            iterations=iterations,
            random_state=random_state,
            use_gpu=False,
        )
        model.fit(user_items, show_progress=True)
        user_factors = np.asarray(model.user_factors)
        item_factors = np.asarray(model.item_factors)
    else:
        user_factors, item_factors = _train_als_numpy(user_items, factors, regularization, iterations, random_state)

    return ALSModel(
        user_map=user_map,
        item_map=item_map,
        user_factors=user_factors,
        item_factors=item_factors,
        user_items=user_items,
    )


def save_als(model: ALSModel, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        path,
        user_factors=model.user_factors,
        item_factors=model.item_factors,
        user_items_data=model.user_items.data,
        user_items_indices=model.user_items.indices,
        user_items_indptr=model.user_items.indptr,
        user_items_shape=np.array(model.user_items.shape),
    )
    meta = path.with_suffix(".json")
    meta.write_bytes(
        orjson.dumps(
            {
                "user_map": model.user_map,
                "item_map": model.item_map,
            }
        )
    )


def load_als(path: Path) -> ALSModel:
    blob = np.load(path, allow_pickle=False)
    shape = tuple(int(x) for x in blob["user_items_shape"])
    user_items = sparse.csr_matrix(
        (blob["user_items_data"], blob["user_items_indices"], blob["user_items_indptr"]),
        shape=shape,
    )
    meta = orjson.loads(path.with_suffix(".json").read_bytes())
    return ALSModel(
        user_map={str(k): int(v) for k, v in meta["user_map"].items()},
        item_map={str(k): int(v) for k, v in meta["item_map"].items()},
        user_factors=blob["user_factors"],
        item_factors=blob["item_factors"],
        user_items=user_items,
    )
