"""Retrieve lexically similar, professionally fact-checked claims from the imported datasets.

This works without any trained model. Results show the fact-checker's ORIGINAL verdict and the
fact-check URL as context for human verification. They are never used to decide a label, and the
absence of a match never implies that a claim is false.
"""

from __future__ import annotations

import threading

import numpy as np
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from healthmisinfo.db.models import Dataset, DatasetSample, SourceRegistry

MIN_SIMILARITY = 0.30


class _Index:
    def __init__(self, signature, vectorizer, matrix, meta):
        self.signature = signature
        self.vectorizer = vectorizer
        self.matrix = matrix
        self.meta = meta


class SimilarClaimIndex:
    def __init__(self) -> None:
        self._indexes: dict[str, _Index] = {}
        self._lock = threading.Lock()

    @staticmethod
    def _signature(db: Session, language: str):
        return db.execute(
            select(func.count(DatasetSample.id), func.max(DatasetSample.id))
            .join(Dataset, Dataset.id == DatasetSample.dataset_id)
            .where(
                DatasetSample.language == language,
                DatasetSample.text_available.is_(True),
                Dataset.is_synthetic.is_(False),
                Dataset.kind == "import",
                DatasetSample.duplicate_of_id.is_(None),
            )
        ).one()

    def _build(self, db: Session, language: str, signature) -> _Index | None:
        from sklearn.feature_extraction.text import TfidfVectorizer

        rows = db.execute(
            select(
                DatasetSample.id,
                DatasetSample.normalized_text,
                DatasetSample.original_text,
                DatasetSample.original_label,
                DatasetSample.source_url,
                Dataset.name,
                Dataset.version,
                SourceRegistry.key,
            )
            .join(Dataset, Dataset.id == DatasetSample.dataset_id)
            .join(SourceRegistry, SourceRegistry.id == Dataset.source_id, isouter=True)
            .where(
                DatasetSample.language == language,
                DatasetSample.text_available.is_(True),
                Dataset.is_synthetic.is_(False),
                Dataset.kind == "import",
                DatasetSample.duplicate_of_id.is_(None),
            )
        ).all()
        if not rows:
            return None
        vec = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), sublinear_tf=True)
        matrix = vec.fit_transform([r[1] or "" for r in rows])
        meta = [
            {
                "sample_id": r[0],
                "text": (r[2] or "")[:400],
                "original_label": r[3],
                "fact_check_url": r[4],
                "dataset": f"{r[5]}@{r[6]}",
                "source_key": r[7] or "user_upload",
            }
            for r in rows
        ]
        return _Index(signature, vec, matrix, meta)

    def search(self, db: Session, text: str, language: str, k: int = 5) -> list[dict]:
        if language not in ("ar", "en"):
            return []
        sig = tuple(self._signature(db, language))
        with self._lock:
            idx = self._indexes.get(language)
            if idx is None or idx.signature != sig:
                idx = self._build(db, language, sig)
                if idx is None:
                    self._indexes.pop(language, None)
                    return []
                self._indexes[language] = idx
        q = idx.vectorizer.transform([text])
        sims = (idx.matrix @ q.T).toarray().ravel()
        order = np.argsort(-sims)[:k]
        return [{**idx.meta[i], "similarity": round(float(sims[i]), 4)} for i in order if sims[i] >= MIN_SIMILARITY]


similar_index = SimilarClaimIndex()

VERIFICATION_RESOURCES = [
    {"name": {"en": "World Health Organization", "ar": "منظمة الصحة العالمية"}, "url": "https://www.who.int/", "kind": "reference"},
    {"name": {"en": "Saudi Ministry of Health", "ar": "وزارة الصحة السعودية"}, "url": "https://www.moh.gov.sa/", "kind": "reference"},
    {"name": {"en": "PubMed (biomedical literature)", "ar": "PubMed (الأدبيات الطبية)"}, "url": "https://pubmed.ncbi.nlm.nih.gov/", "kind": "reference"},
]
