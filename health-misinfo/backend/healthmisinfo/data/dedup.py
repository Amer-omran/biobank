"""Duplicate and near-duplicate detection + leakage groups.

Groups are the unit of splitting: every member of a group lands in the same split. Members are
linked (union-find) when they share any of:

1. the exact-duplicate key (``match_key_hash``),
2. a near-duplicate pair: cosine similarity of character n-gram TF-IDF vectors >= threshold,
3. the same fact-check article URL (``source_url``) – the same claim checked once,
4. a researcher-supplied ``group_key`` (e.g. linking a translation or paraphrase).

Cross-lingual translations cannot be detected lexically; they matter only for multilingual models.
This platform trains one model per language with per-language splits, and researchers can link
known translations with ``group_key``. See docs/METHODOLOGY.md.
"""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np

DEFAULT_NEAR_DUP_THRESHOLD = 0.85
DEDUP_VERSION = "dedup-v1-char3-5-tfidf"


class UnionFind:
    def __init__(self, n: int) -> None:
        self.parent = list(range(n))

    def find(self, x: int) -> int:
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a: int, b: int) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            if ra < rb:
                self.parent[rb] = ra
            else:
                self.parent[ra] = rb


def near_duplicate_pairs(texts: Sequence[str], threshold: float = DEFAULT_NEAR_DUP_THRESHOLD, chunk: int = 512) -> list[tuple[int, int, float]]:
    """Return (i, j, similarity) for i < j with cosine similarity >= threshold."""
    if len(texts) < 2:
        return []
    from sklearn.feature_extraction.text import TfidfVectorizer

    vec = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), sublinear_tf=True, min_df=1)
    try:
        X = vec.fit_transform(texts)
    except ValueError:  # empty vocabulary
        return []
    pairs: list[tuple[int, int, float]] = []
    n = X.shape[0]
    XT = X.T.tocsc()
    for start in range(0, n, chunk):
        end = min(start + chunk, n)
        sims = (X[start:end] @ XT).toarray()
        for local_i in range(end - start):
            i = start + local_i
            row = sims[local_i]
            js = np.nonzero(row >= threshold)[0]
            for j in js:
                if j > i:
                    pairs.append((i, int(j), float(row[j])))
    return pairs


@dataclass
class GroupItem:
    key_hash: str
    text: str
    source_url: str | None = None
    group_key: str | None = None


def compute_groups(items: Sequence[GroupItem], threshold: float = DEFAULT_NEAR_DUP_THRESHOLD) -> tuple[list[str], dict]:
    """Return a deterministic group id per item and statistics about the links found."""
    n = len(items)
    uf = UnionFind(n)
    stats = {"exact_links": 0, "near_duplicate_links": 0, "source_url_links": 0, "group_key_links": 0}

    def link_by(attr: str, stat: str) -> None:
        first: dict[str, int] = {}
        for i, it in enumerate(items):
            v = getattr(it, attr)
            if not v:
                continue
            if v in first:
                if uf.find(first[v]) != uf.find(i):
                    stats[stat] += 1
                uf.union(first[v], i)
            else:
                first[v] = i

    link_by("key_hash", "exact_links")
    link_by("source_url", "source_url_links")
    link_by("group_key", "group_key_links")
    max_sim = [0.0] * n
    for i, j, sim in near_duplicate_pairs([it.text for it in items], threshold):
        if uf.find(i) != uf.find(j):
            stats["near_duplicate_links"] += 1
        uf.union(i, j)
        max_sim[i] = max(max_sim[i], sim)
        max_sim[j] = max(max_sim[j], sim)

    members: dict[int, list[int]] = {}
    for i in range(n):
        members.setdefault(uf.find(i), []).append(i)
    group_of: list[str] = [""] * n
    for idxs in members.values():
        basis = min(items[k].key_hash for k in idxs)
        gid = "g-" + hashlib.sha1(basis.encode(), usedforsecurity=False).hexdigest()[:16]
        for k in idxs:
            group_of[k] = gid
    stats["groups"] = len(members)
    stats["multi_member_groups"] = sum(1 for v in members.values() if len(v) > 1)
    stats["threshold"] = threshold
    stats["method"] = DEDUP_VERSION
    stats["max_similarity"] = max_sim
    return group_of, stats
