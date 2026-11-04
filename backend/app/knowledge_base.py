"""Knowledge base loading and retrieval.

Markdown files are split on `##` headings so each chunk is one self-contained
answer. Retrieval uses BM25, which needs no embedding model or vector database
and is easy to swap for a vector store later (see `Retriever`).
"""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

STOPWORDS = frozenset(
    """a an and are as at be but by can do does for from have how i if in into is it
    its my me of on or our so that the their them then there this to was we what when
    where which who why will with you your yours am been being did get got has had
    please hi hello hey would could should want need just about any some""".split()
)


def tokenize(text: str) -> list[str]:
    tokens = re.findall(r"[a-z0-9]+", text.lower())
    return [_stem(t) for t in tokens if t not in STOPWORDS and len(t) > 1]


def _stem(token: str) -> str:
    # A tiny suffix stripper, good enough for FAQ matching: "returns" -> "return",
    # "shipping"/"shipped"/"ships" -> "ship", "internationally" -> "international".
    if token.endswith("ally") and len(token) > 6:
        return token[:-2]
    for suffix in ("ing", "ed", "es", "s"):
        if token.endswith(suffix) and len(token) - len(suffix) >= 3:
            stem = token[: -len(suffix)]
            if len(stem) > 3 and stem[-1] == stem[-2] and stem[-1] not in "lsz":
                stem = stem[:-1]
            return stem
    return token


@dataclass(frozen=True)
class Chunk:
    id: str
    source: str
    title: str
    text: str


@dataclass(frozen=True)
class SearchResult:
    chunk: Chunk
    score: float


def load_chunks(directory: Path) -> list[Chunk]:
    chunks: list[Chunk] = []
    for path in sorted(directory.glob("*.md")):
        doc_title = path.stem.replace("-", " ").title()
        section_title: str | None = None
        lines: list[str] = []

        def flush() -> None:
            body = " ".join(line.strip() for line in lines if line.strip())
            if section_title and body:
                chunks.append(
                    Chunk(
                        id=f"{path.stem}#{len(chunks)}",
                        source=doc_title,
                        title=section_title,
                        text=body,
                    )
                )

        for line in path.read_text(encoding="utf-8").splitlines():
            if line.startswith("# "):
                doc_title = line[2:].strip()
            elif line.startswith("## "):
                flush()
                section_title, lines = line[3:].strip(), []
            else:
                lines.append(line)
        flush()
    return chunks


class Retriever:
    """Okapi BM25 over knowledge base chunks. Section titles are weighted double."""

    def __init__(self, chunks: list[Chunk], k1: float = 1.5, b: float = 0.75):
        self.chunks = chunks
        self.k1, self.b = k1, b
        self._docs = [tokenize(f"{c.title} {c.title} {c.text}") for c in chunks]
        self._tf = [Counter(d) for d in self._docs]
        self._avgdl = sum(len(d) for d in self._docs) / max(len(self._docs), 1)
        df: Counter[str] = Counter()
        for doc in self._docs:
            df.update(set(doc))
        n = len(self._docs)
        self._idf = {t: math.log(1 + (n - f + 0.5) / (f + 0.5)) for t, f in df.items()}

    def search(
        self, query: str, top_k: int = 4, boost_sources: tuple[str, ...] = ()
    ) -> list[SearchResult]:
        """BM25 search. Chunks whose file stem is in `boost_sources` (the topics
        the intent classifier expects) score 1.6x, so "return boots I wore"
        prefers the returns article over the boot sizing one."""
        terms = tokenize(query)
        if not terms:
            return []
        scored: list[SearchResult] = []
        for chunk, tf, doc in zip(self.chunks, self._tf, self._docs):
            score = 0.0
            for term in terms:
                if term not in tf:
                    continue
                freq = tf[term]
                norm = freq * (self.k1 + 1) / (
                    freq + self.k1 * (1 - self.b + self.b * len(doc) / self._avgdl)
                )
                score += self._idf.get(term, 0.0) * norm
            if score > 0 and chunk.id.split("#")[0] in boost_sources:
                score *= 1.6
            if score > 0:
                scored.append(SearchResult(chunk, score))
        scored.sort(key=lambda r: r.score, reverse=True)
        return scored[:top_k]

    def coverage(self, query: str, result: SearchResult) -> float:
        """Share of the query's terms that appear in a chunk (0..1)."""
        terms = set(tokenize(query))
        if not terms:
            return 0.0
        chunk_terms = set(tokenize(f"{result.chunk.title} {result.chunk.text}"))
        return len(terms & chunk_terms) / len(terms)
