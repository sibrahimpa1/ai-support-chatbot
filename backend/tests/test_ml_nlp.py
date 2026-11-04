"""Tests for the trained NLP components (they use the local embedding model)."""

import pytest

from app.config import Settings
from app.engine import build_nlp
from app.intents import analyze
from app.knowledge_base import HybridRetriever


@pytest.fixture(scope="module")
def nlp():
    s = Settings()
    retriever, classifier, detector = build_nlp(
        s.knowledge_base_dir, s.nlu_train_file, s.needs_action_file, "ml", s.intent_features,
        "hybrid", s.embedding_model, s.model_cache_dir, s.bm25_weight, s.action_threshold,
    )
    if not isinstance(retriever, HybridRetriever):
        pytest.skip("embedding model unavailable")
    return retriever, classifier, detector


@pytest.mark.parametrize(
    "text, intent",
    [
        ("how do I get my money back", "returns_refunds"),  # no keyword the rules know
        ("I'd prefer a person over a chatbot", "human_handoff"),
        ("do you post orders to Spain", "shipping"),
        ("can you recommend a stock to buy", "other"),
    ],
)
def test_classifier_understands_paraphrases(nlp, text, intent):
    _, classifier, _ = nlp
    predicted, confidence, probs = classifier.predict(text)
    assert predicted == intent
    assert 0 < confidence <= 1 and abs(sum(probs.values()) - 1) < 1e-3


def test_rules_miss_what_the_model_catches(nlp):
    _, classifier, detector = nlp
    text = "how do I get my money back"
    assert analyze(text).intent != "returns_refunds"
    ml = analyze(text, classifier, detector)
    assert ml.intent == "returns_refunds" and ml.source == "ml"


def test_action_detector_flags_problems_without_keywords(nlp):
    _, _, detector = nlp
    assert detector("the parcel got wet and the down jacket inside is ruined")
    assert not detector("how much is express shipping")


def test_semantic_retrieval_matches_paraphrase(nlp):
    retriever, _, _ = nlp
    top = retriever.search("when will the money be back on my card", 3)
    assert top[0].chunk.title == "Refund timing"
    assert top[0].similarity is not None and top[0].similarity > 0.6


def test_off_topic_query_retrieves_nothing_relevant(nlp):
    retriever, _, _ = nlp
    results = retriever.search("explain the theory of relativity", 3)
    assert all((r.similarity or 0) < 0.62 for r in results)


def test_eval_dataset_is_disjoint_from_training_data():
    import json
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent
    load = lambda p: {json.loads(l)["text"].lower() for l in (root / p).read_text().splitlines() if l}  # noqa: E731
    train = load("data/nlu/train.jsonl") | load("data/nlu/needs_action.jsonl")
    assert not train & load("eval/dataset.jsonl")
    assert not train & load("eval/dev.jsonl")
    assert not load("eval/dev.jsonl") & load("eval/dataset.jsonl")
