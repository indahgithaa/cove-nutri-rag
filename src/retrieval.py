"""Fixed within-document BM25 retrieval for the CoVe experiment."""

from __future__ import annotations

import re
import unicodedata
from collections import defaultdict
from dataclasses import asdict, dataclass
from decimal import Decimal
from pathlib import Path
from typing import Iterable, Sequence

import yaml
from rank_bm25 import BM25Okapi
from Sastrawi.StopWordRemover.StopWordRemoverFactory import StopWordRemoverFactory

from src.numbers import NumberConfig, extract_numbers, number_in_candidates


RETRIEVAL_VERSION = "bm25_fixed_v1"
TOKEN_RE = re.compile(r"\w+", flags=re.UNICODE)


@dataclass(frozen=True)
class RetrievalConfig:
    k1: float
    b: float
    epsilon: float
    additional_query_stopwords: frozenset[str]
    conditions: dict[str, tuple[int, int]]

    @property
    def maximum_rank(self) -> int:
        return max(end for _, end in self.conditions.values())


@dataclass(frozen=True)
class RankedChunk:
    rank: int
    chunk_id: str
    doc_id: str
    page_number: int
    chunk_index: int
    text: str
    score: float

    def to_dict(self) -> dict:
        payload = asdict(self)
        payload["score"] = round(self.score, 12)
        return payload


def load_retrieval_config(path: Path) -> RetrievalConfig:
    with path.open("r", encoding="utf-8") as handle:
        raw = yaml.safe_load(handle)
    if raw["version"] != RETRIEVAL_VERSION:
        raise ValueError(
            f"Unsupported retrieval version {raw['version']!r}; "
            f"expected {RETRIEVAL_VERSION!r}"
        )
    if raw["bm25"]["scope"] != "within_document":
        raise ValueError("Retrieval scope must remain within_document")
    if not raw["tokenization"]["remove_stopwords_from_query_only"]:
        raise ValueError("Stage 4 requires stopword removal from queries only")

    conditions = {
        name: tuple(int(value) for value in values["ranks"])
        for name, values in raw["conditions"].items()
    }
    for name, (start, end) in conditions.items():
        if start < 1 or end < start or end - start + 1 != 3:
            raise ValueError(f"Condition {name!r} must select exactly three ranks")
    if conditions != {"normal": (1, 3), "degraded": (4, 6)}:
        raise ValueError("Frozen conditions must be normal=1-3 and degraded=4-6")

    return RetrievalConfig(
        k1=float(raw["bm25"]["k1"]),
        b=float(raw["bm25"]["b"]),
        epsilon=float(raw["bm25"]["epsilon"]),
        additional_query_stopwords=frozenset(
            word.casefold()
            for word in raw["tokenization"]["additional_query_stopwords"]
        ),
        conditions=conditions,
    )


def normalize_text(text: str) -> str:
    return unicodedata.normalize("NFKC", text).casefold()


def tokenize_document(text: str) -> list[str]:
    """Tokenize corpus text without removing stopwords."""

    return TOKEN_RE.findall(normalize_text(text))


def default_query_stopwords(additional: Iterable[str] = ()) -> frozenset[str]:
    words = {
        normalize_text(word)
        for word in StopWordRemoverFactory().get_stop_words()
    }
    words.update(normalize_text(word) for word in additional)
    return frozenset(words)


def tokenize_query(text: str, stopwords: frozenset[str]) -> list[str]:
    return [token for token in tokenize_document(text) if token not in stopwords]


def make_chunk_id(doc_id: str, page_number: int, chunk_index: int) -> str:
    return f"{doc_id}::page={page_number}::chunk={chunk_index}"


def gold_chunk_id(qa: dict) -> str:
    return make_chunk_id(qa["doc_id"], qa["page_number"], qa["chunk_index"])


class DocumentBM25:
    """A deterministic BM25 index restricted to one patient report."""

    def __init__(self, chunks: Sequence[dict], config: RetrievalConfig):
        if not chunks:
            raise ValueError("A document BM25 index requires at least one chunk")
        doc_ids = {chunk["doc_id"] for chunk in chunks}
        if len(doc_ids) != 1:
            raise ValueError("DocumentBM25 cannot mix chunks from different documents")
        self.config = config
        self.chunks = sorted(
            chunks,
            key=lambda row: (row["page_number"], row["chunk_index"]),
        )
        if len(self.chunks) < config.maximum_rank:
            raise ValueError(
                f"Document {next(iter(doc_ids))!r} has only {len(self.chunks)} "
                f"chunks; rank {config.maximum_rank} is required"
            )
        tokenized = [tokenize_document(chunk["text"]) for chunk in self.chunks]
        self.index = BM25Okapi(
            tokenized,
            k1=config.k1,
            b=config.b,
            epsilon=config.epsilon,
        )

    def rank(self, query_tokens: Sequence[str]) -> list[RankedChunk]:
        scores = self.index.get_scores(list(query_tokens))
        order = sorted(
            range(len(self.chunks)),
            key=lambda index: (
                -float(scores[index]),
                self.chunks[index]["page_number"],
                self.chunks[index]["chunk_index"],
            ),
        )
        ranked = []
        for rank, index in enumerate(order, start=1):
            chunk = self.chunks[index]
            ranked.append(
                RankedChunk(
                    rank=rank,
                    chunk_id=make_chunk_id(
                        chunk["doc_id"], chunk["page_number"], chunk["chunk_index"]
                    ),
                    doc_id=chunk["doc_id"],
                    page_number=chunk["page_number"],
                    chunk_index=chunk["chunk_index"],
                    text=chunk["text"],
                    score=float(scores[index]),
                )
            )
        return ranked


def build_document_indexes(
    chunks: Iterable[dict], config: RetrievalConfig
) -> dict[str, DocumentBM25]:
    grouped: dict[str, list[dict]] = defaultdict(list)
    seen_chunk_ids: set[str] = set()
    for chunk in chunks:
        chunk_id = make_chunk_id(
            chunk["doc_id"], chunk["page_number"], chunk["chunk_index"]
        )
        if chunk_id in seen_chunk_ids:
            raise ValueError(f"Duplicate chunk id: {chunk_id}")
        seen_chunk_ids.add(chunk_id)
        grouped[chunk["doc_id"]].append(chunk)
    return {
        doc_id: DocumentBM25(document_chunks, config)
        for doc_id, document_chunks in sorted(grouped.items())
    }


def select_condition(
    ranking: Sequence[RankedChunk], condition: str, config: RetrievalConfig
) -> list[RankedChunk]:
    if condition not in config.conditions:
        raise KeyError(f"Unknown retrieval condition: {condition!r}")
    start, end = config.conditions[condition]
    selected = list(ranking[start - 1 : end])
    if len(selected) != 3:
        raise ValueError(
            f"Condition {condition!r} requires three chunks, got {len(selected)}"
        )
    return selected


def numeric_coverage(
    gold_answer: str,
    chunks: Sequence[RankedChunk],
    number_config: NumberConfig,
) -> tuple[int, int]:
    gold = extract_numbers(gold_answer, number_config)
    candidates = [
        mention.value
        for chunk in chunks
        for mention in extract_numbers(chunk.text, number_config)
    ]
    hits = sum(
        number_in_candidates(mention.value, candidates, number_config)
        for mention in gold
    )
    return hits, len(gold)


def context_record(
    qa: dict,
    *,
    condition: str,
    query_tokens: Sequence[str],
    selected: Sequence[RankedChunk],
) -> dict:
    """Serialize retrieval input without gold answers or test-only annotations."""

    return {
        "id": qa["id"],
        "doc_id": qa["doc_id"],
        "split": qa["split"],
        "question": qa["question"],
        "question_type": qa["question_type"],
        "condition": condition,
        "retrieval_version": RETRIEVAL_VERSION,
        "query_tokens": list(query_tokens),
        "chunks": [chunk.to_dict() for chunk in selected],
    }

