"""Grid-search the pipeline's knobs on the dev set (eval/dev.jsonl).

    uv run python -m eval.tune

The test set (eval/dataset.jsonl) is never used here, so the numbers in
eval/results.md stay an honest estimate. Pick the winner, put it in
app/config.py, then run `python -m eval.run_eval`.
"""

from __future__ import annotations

import itertools

from sklearn.metrics import precision_recall_fscore_support

from app.config import Settings
from app.engine import SupportEngine
from app.providers.mock import MockProvider
from app.store import Store
from eval.run_eval import EVAL_DIR, article_key, load_cases

BUILD_GRID = {
    "intent_features": ["embedding", "combined"],
    "bm25_weight": [0.0, 0.25, 0.5, 1.0],
    "action_threshold": [0.3, 0.5, 0.7],
}
DECISION_GRID = {
    "confidence_intent_weight": [0.2, 0.35, 0.5],
    "escalation_threshold": [0.3, 0.35, 0.4, 0.45],
}


def score(cases, overrides):
    settings = Settings(llm_provider="mock", database_path=":memory:", seed_demo_data=False, **overrides)
    engine = SupportEngine(settings, Store(":memory:"), MockProvider(settings.confidence_intent_weight))
    predicted, hits = [], 0
    for c in cases:
        res = engine.handle_message(c.text)
        predicted.append(res["escalated"])
        top = [r["id"] for r in res["debug"]["retrieved"][:3]]
        if c.article:
            hits += any(article_key(ch) == c.article for ch in engine.retriever.chunks if ch.id in top)
    _, _, f1, _ = precision_recall_fscore_support(
        [c.escalate for c in cases], predicted, average="binary", zero_division=0
    )
    answerable = [c for c, e in zip(cases, predicted) if not c.escalate]
    self_service = sum(1 for c, e in zip(cases, predicted) if not c.escalate and not e) / len(answerable)
    recall3 = hits / sum(1 for c in cases if c.article)
    return f1, self_service, recall3


def main() -> None:
    cases = load_cases(EVAL_DIR / "dev.jsonl")
    rows = []
    for build in itertools.product(*BUILD_GRID.values()):
        build_kw = dict(zip(BUILD_GRID, build))
        for decision in itertools.product(*DECISION_GRID.values()):
            kw = build_kw | dict(zip(DECISION_GRID, decision))
            rows.append((*score(cases, kw), kw))
    rows.sort(key=lambda r: (r[0], r[1], r[2]), reverse=True)
    print(f"dev set: {len(cases)} cases, {len(rows)} configurations\n")
    print("esc_F1  self_serv  recall@3  config")
    for f1, ss, r3, kw in rows[:10]:
        print(f"{f1:.3f}   {ss:.3f}      {r3:.3f}     {kw}")


if __name__ == "__main__":
    main()
