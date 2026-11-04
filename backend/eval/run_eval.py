"""Offline evaluation of the support bot's NLP on a held-out, labeled test set.

    uv run python -m eval.run_eval            # print report, write eval/results.{md,json}
    uv run python -m eval.run_eval --check    # also fail (exit 1) if quality drops below the gates

Measures three things on `eval/dataset.jsonl` (never used for training):

1. Intent classification: accuracy and macro-F1 for the regex rules and for
   the trained classifier with three feature sets.
2. Retrieval: Recall@1, Recall@3 and MRR of the expected help-center section
   for BM25, dense embeddings, and the hybrid (RRF) retriever.
3. End-to-end escalation: does the full pipeline (offline provider) hand the
   chat to a human exactly when it should? Reported as precision / recall /
   F1, plus the share of answerable questions it resolves on its own.
"""

from __future__ import annotations

import argparse
import json
import statistics
import time
from dataclasses import dataclass
from pathlib import Path

from sklearn.metrics import accuracy_score, f1_score, precision_recall_fscore_support

from app.config import Settings
from app.embeddings import load_embedder
from app.engine import INTENT_SOURCES, SupportEngine
from app.intent_model import IntentClassifier, load_examples
from app.intents import analyze
from app.knowledge_base import HybridRetriever, Retriever, load_chunks
from app.providers.mock import MockProvider
from app.store import Store

EVAL_DIR = Path(__file__).resolve().parent
# Regression gates for CI, for the production configuration (ml + hybrid).
FEATURE_LABELS = {"tfidf": "TF-IDF", "embedding": "embeddings", "combined": "TF-IDF + embeddings"}
# Set a little below the current scores so CI catches regressions, not float noise.
GATES = {"intent_accuracy": 0.90, "retrieval_recall_at_3": 0.85, "escalation_f1": 0.80}


@dataclass
class Case:
    text: str
    intent: str
    article: str | None
    escalate: bool


def load_cases(path: Path = EVAL_DIR / "dataset.jsonl") -> list[Case]:
    return [Case(**json.loads(line)) for line in path.read_text().splitlines() if line.strip()]


def article_key(chunk) -> str:
    return f"{chunk.id.split('#')[0]}:{chunk.title}"


def eval_intents(cases, settings, embedder):
    gold = [c.intent for c in cases]
    examples = load_examples(settings.nlu_train_file)
    rows = {"Regex rules (baseline)": [analyze(c.text).intent for c in cases]}
    for features, name in FEATURE_LABELS.items():
        label = f"ML: {name}"
        clf = IntentClassifier(examples, embedder, features)
        rows[label] = [clf.predict(c.text)[0] for c in cases]
    results = {
        name: {
            "accuracy": accuracy_score(gold, pred),
            "macro_f1": f1_score(gold, pred, average="macro", zero_division=0),
        }
        for name, pred in rows.items()
    }
    best = rows[f"ML: {FEATURE_LABELS[settings.intent_features]}"]
    errors = [(c.text, c.intent, p) for c, p in zip(cases, best) if p != c.intent]
    return results, errors


def eval_retrieval(cases, settings, embedder):
    chunks = load_chunks(settings.knowledge_base_dir)
    bm25 = Retriever(chunks)
    hybrid = HybridRetriever(chunks, embedder, bm25_weight=1.0)
    production = HybridRetriever(chunks, embedder, bm25_weight=settings.bm25_weight)
    clf = IntentClassifier(load_examples(settings.nlu_train_file), embedder, settings.intent_features)
    boost = lambda q: INTENT_SOURCES.get(clf.predict(q)[0], ())  # noqa: E731
    systems = {
        "BM25 (baseline)": lambda q: bm25.search(q, 3),
        "Dense embeddings": lambda q: hybrid.dense_search(q, 3),
        "Hybrid RRF (BM25 + embeddings)": lambda q: hybrid.search(q, 3, boost(q)),
        "Embeddings + intent boost": lambda q: production.search(q, 3, boost(q)),
    }
    with_article = [c for c in cases if c.article]
    results = {}
    for name, search in systems.items():
        ranks = []
        for c in with_article:
            keys = [article_key(r.chunk) for r in search(c.text)]
            ranks.append(keys.index(c.article) + 1 if c.article in keys else None)
        results[name] = {
            "recall_at_1": sum(r == 1 for r in ranks) / len(ranks),
            "recall_at_3": sum(r is not None for r in ranks) / len(ranks),
            "mrr": sum(1 / r for r in ranks if r) / len(ranks),
        }
    return results, len(with_article)


def eval_escalation(cases, configs):
    results = {}
    for name, overrides in configs.items():
        settings = Settings(llm_provider="mock", database_path=":memory:",
                            seed_demo_data=False, **overrides)
        engine = SupportEngine(settings, Store(":memory:"),
                               MockProvider(settings.confidence_intent_weight))
        predicted, latencies, answered_right = [], [], 0
        for c in cases:
            started = time.perf_counter()
            res = engine.handle_message(c.text)
            latencies.append((time.perf_counter() - started) * 1000)
            predicted.append(res["escalated"])
            if not c.escalate and not res["escalated"] and c.article:
                top = res["debug"]["retrieved"][:1]
                answered_right += bool(top) and top[0]["id"].split("#")[0] == c.article.split(":")[0]
        gold = [c.escalate for c in cases]
        p, r, f, _ = precision_recall_fscore_support(gold, predicted, average="binary", zero_division=0)
        answerable = [c for c in cases if not c.escalate]
        resolved = sum(1 for c, e in zip(cases, predicted) if not c.escalate and not e)
        results[name] = {
            "escalation_precision": p,
            "escalation_recall": r,
            "escalation_f1": f,
            "self_service_rate": resolved / len(answerable),
            "answered_from_right_article": answered_right / sum(1 for c in answerable if c.article),
            "median_latency_ms": statistics.median(latencies),
        }
    return results


def pct(x: float) -> str:
    return f"{x * 100:.1f}%"


def render(report: dict) -> str:
    lines = [
        "# Evaluation results",
        "",
        f"Held-out test set: **{report['n_cases']} labeled customer messages** "
        f"({report['n_with_article']} with an expected help-center article), "
        "written separately from the classifier's training data. "
        "Reproduce with `make eval`.",
        "",
        "## 1. Intent classification (13 intents)",
        "",
        "| Method | Accuracy | Macro F1 |",
        "| --- | ---: | ---: |",
    ]
    for name, m in report["intents"].items():
        lines.append(f"| {name} | {pct(m['accuracy'])} | {pct(m['macro_f1'])} |")
    lines += ["", "## 2. Knowledge-base retrieval", "",
              "| Method | Recall@1 | Recall@3 | MRR |", "| --- | ---: | ---: | ---: |"]
    for name, m in report["retrieval"].items():
        lines.append(f"| {name} | {pct(m['recall_at_1'])} | {pct(m['recall_at_3'])} | {m['mrr']:.3f} |")
    lines += ["", "## 3. End-to-end: when to hand off to a human", "",
              "Full pipeline with the offline provider (no LLM), one fresh conversation per message.", "",
              "| Pipeline | Escalation precision | Escalation recall | Escalation F1 | Self-service rate | Right article | Median latency |",
              "| --- | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for name, m in report["escalation"].items():
        lines.append(
            f"| {name} | {pct(m['escalation_precision'])} | {pct(m['escalation_recall'])} | "
            f"{pct(m['escalation_f1'])} | {pct(m['self_service_rate'])} | "
            f"{pct(m['answered_from_right_article'])} | {m['median_latency_ms']:.0f} ms |"
        )
    lines += [
        "",
        "- **Escalation precision**: of the chats handed to a human, how many really needed one.",
        "- **Escalation recall**: of the chats that needed a human, how many were handed over.",
        "- **Self-service rate**: answerable questions the bot resolved without a human.",
        "- **Right article**: of those, answered from the expected help-center section.",
        "",
        "## Remaining intent errors (production model)",
        "",
        "| Message | Expected | Predicted |",
        "| --- | --- | --- |",
    ]
    for text, gold, pred in report["intent_errors"]:
        lines.append(f"| {text} | {gold} | {pred} |")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="exit 1 if a quality gate fails")
    args = parser.parse_args()

    settings = Settings(llm_provider="mock", database_path=":memory:", seed_demo_data=False)
    embedder = load_embedder(settings.embedding_model, str(settings.model_cache_dir))
    if embedder is None:
        raise SystemExit("Embedding model could not be loaded; the eval needs it.")
    cases = load_cases()

    intents, errors = eval_intents(cases, settings, embedder)
    retrieval, n_with_article = eval_retrieval(cases, settings, embedder)
    escalation = eval_escalation(cases, {
        # The baseline keeps the settings it was originally tuned with.
        "Baseline: regex rules + BM25": {"nlu_mode": "rules", "retrieval_mode": "bm25",
                                         "escalation_threshold": 0.45, "confidence_intent_weight": 0.5},
        "Current: ML intents + embedding retrieval": {},
    })
    report = {
        "n_cases": len(cases),
        "n_with_article": n_with_article,
        "intents": intents,
        "retrieval": retrieval,
        "escalation": escalation,
        "intent_errors": errors,
    }

    markdown = render(report)
    (EVAL_DIR / "results.md").write_text(markdown)
    (EVAL_DIR / "results.json").write_text(json.dumps(report, indent=2))
    print(markdown)

    current = {
        "intent_accuracy": intents[f"ML: {FEATURE_LABELS[settings.intent_features]}"]["accuracy"],
        "retrieval_recall_at_3": retrieval["Embeddings + intent boost"]["recall_at_3"],
        "escalation_f1": escalation["Current: ML intents + embedding retrieval"]["escalation_f1"],
    }
    failed = {k: v for k, v in current.items() if v < GATES[k]}
    for k, v in current.items():
        print(f"{'FAIL' if k in failed else 'ok  '} {k}: {v:.3f} (gate {GATES[k]})")
    return 1 if args.check and failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
