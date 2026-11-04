from app.config import Settings
from app.knowledge_base import Retriever, load_chunks


def retriever():
    return Retriever(load_chunks(Settings().knowledge_base_dir))


def test_knowledge_base_is_chunked_by_section():
    chunks = load_chunks(Settings().knowledge_base_dir)
    assert len(chunks) > 20
    assert all(c.title and c.text for c in chunks)


def test_retrieval_finds_relevant_section():
    cases = {
        "how long do refunds take": "Refund timing",
        "do you ship internationally to the UK": "International shipping",
        "my hiking boots size": "Sizing help",
        "reset my password": "Resetting your password",
    }
    r = retriever()
    for query, title in cases.items():
        assert r.search(query)[0].chunk.title == title, query


def test_retrieval_returns_nothing_for_stopwords():
    assert retriever().search("what is the") == []
