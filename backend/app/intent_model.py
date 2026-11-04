"""Trained intent classifier (scikit-learn logistic regression).

Three feature sets can be compared in `eval/run_eval.py`:

- "tfidf":     word 1-2 grams + character 3-5 grams. Robust to typos, no model download.
- "embedding": sentence embeddings. Understands paraphrases ("get my money back").
- "combined":  both, concatenated. Usually the best of the two.

Training takes well under a second on the bundled ~250 examples, so the model
is fit at startup from `data/nlu/train.jsonl` instead of shipping a binary.
Logistic regression gives probabilities, which the escalation policy uses as
the intent confidence.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
from scipy.sparse import csr_matrix, hstack
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_union

if TYPE_CHECKING:
    from app.embeddings import Embedder

FEATURE_SETS = ("tfidf", "embedding", "combined")


def load_examples(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


class IntentClassifier:
    def __init__(self, examples: list[dict], embedder: "Embedder | None" = None,
                 features: str = "combined"):
        if features not in FEATURE_SETS:
            raise ValueError(f"features must be one of {FEATURE_SETS}")
        if features != "tfidf" and embedder is None:
            features = "tfidf"  # graceful fallback when the embedding model is unavailable
        self.features = features
        self.embedder = embedder
        self._tfidf = make_union(
            TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True),
            TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), sublinear_tf=True),
        )
        texts = [e["text"] for e in examples]
        labels = [e["intent"] for e in examples]
        self._tfidf.fit(texts)
        self._model = LogisticRegression(C=8.0, max_iter=3000, class_weight="balanced")
        self._model.fit(self._featurize(texts), labels)
        self.labels: list[str] = list(self._model.classes_)

    def _featurize(self, texts: list[str]):
        parts = []
        if self.features in ("tfidf", "combined"):
            parts.append(self._tfidf.transform(texts))
        if self.features in ("embedding", "combined"):
            # Scale dense vectors so they carry weight comparable to the sparse block.
            parts.append(csr_matrix(self.embedder.embed(texts) * 2.0))
        return hstack(parts).tocsr() if len(parts) > 1 else parts[0]

    def predict_proba(self, texts: list[str]) -> np.ndarray:
        return self._model.predict_proba(self._featurize(texts))

    def predict(self, text: str) -> tuple[str, float, dict[str, float]]:
        probs = self.predict_proba([text])[0]
        best = int(probs.argmax())
        return self.labels[best], float(probs[best]), dict(zip(self.labels, probs.round(4)))


class ActionDetector:
    """Binary classifier: does this message report a problem a person must fix?

    (damaged or missing items, double charges, warranty claims...) Positives come
    from `data/nlu/needs_action.jsonl`; negatives are the ordinary intent
    examples. It replaces brittle keyword lists: "the box showed up crushed"
    never says "damaged", but its embedding sits right next to the examples.
    """

    def __init__(self, positives: list[str], negatives: list[str], embedder: "Embedder",
                 threshold: float = 0.5):
        self.embedder = embedder
        self.threshold = threshold
        texts = positives + negatives
        labels = [1] * len(positives) + [0] * len(negatives)
        self._model = LogisticRegression(C=4.0, max_iter=3000, class_weight="balanced")
        self._model.fit(embedder.embed(texts), labels)

    def probability(self, text: str) -> float:
        return float(self._model.predict_proba(self.embedder.embed([text]))[0, 1])

    def __call__(self, text: str) -> bool:
        return self.probability(text) >= self.threshold
