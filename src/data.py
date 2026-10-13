"""Deterministic preprocessing and document-level splitting.

The module treats raw research data as read-only. It writes derived artifacts
only to ``data/processed`` and keeps an audit trail for every removed duplicate.
The numeric flag is explicitly provisional until Stage 3 validates it.
"""

from __future__ import annotations

import hashlib
import json
import random
import re
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator

import yaml


QUESTION_TYPES = (
    "Skrining",
    "Status gizi",
    "Biokimia/lab",
    "Diagnosis PES",
    "Tujuan diet",
    "Prinsip diet",
    "Syarat diet",
    "Pedoman diet",
)

QUESTION_TYPE_RULES = (
    ("skrining", "Skrining"),
    ("status gizi", "Status gizi"),
    ("biokimia", "Biokimia/lab"),
    ("format pes", "Diagnosis PES"),
    ("tujuan diet", "Tujuan diet"),
    ("prinsip diet", "Prinsip diet"),
    ("syarat diet", "Syarat diet"),
    ("pedoman diet", "Pedoman diet"),
)

PES_CODE_RE = re.compile(r"\bN[ICB]\s*[-.]?\s*\d+(?:\.\d+)+\b", re.IGNORECASE)
CANDIDATE_NUMBER_RE = re.compile(
    r"(?<![A-Za-z])"
    r"[+-]?"
    r"(?:\d{1,3}(?:\.\d{3})+(?:,\d+)?|\d+\.\d+|\d+(?:,\d+)?)"
    r"(?:\s*%)?"
)

REQUIRED_QA_FIELDS = {
    "id",
    "file",
    "page_number",
    "chunk_index",
    "question",
    "context",
    "answer",
    "medical_diagnosis",
    "anthropometric_assessment",
    "report_title",
}
REQUIRED_CHUNK_FIELDS = {"pdf_name", "page_number", "chunk_index", "text"}


@dataclass(frozen=True)
class PreprocessingResult:
    summary: dict
    output_paths: tuple[Path, ...]


def normalize_filename(value: str) -> str:
    """Normalize known filename corruption without changing case."""

    decoded = re.sub(
        r"#U([0-9A-Fa-f]{4})",
        lambda match: chr(int(match.group(1), 16)),
        value,
    )
    return unicodedata.normalize("NFKC", decoded).replace("\u2060", "").strip()


def normalize_question(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip()).casefold()


def classify_question(question: str) -> str:
    normalized = normalize_question(question)
    for marker, label in QUESTION_TYPE_RULES:
        if marker in normalized:
            return label
    raise ValueError(f"Unrecognized question template: {question!r}")


def extract_answer_text(row: dict) -> str:
    answer = row.get("answer")
    if not isinstance(answer, dict):
        raise ValueError(f"QA id={row.get('id')} has a non-object answer")
    texts = answer.get("text")
    if not isinstance(texts, list) or len(texts) != 1 or not isinstance(texts[0], str):
        raise ValueError(f"QA id={row.get('id')} must contain exactly one answer text")
    return texts[0]


def contains_pes_code(text: str) -> bool:
    return PES_CODE_RE.search(text) is not None


def contains_numeric_candidate(text: str) -> bool:
    """Provisional Stage 2 flag; Stage 3 owns validated number extraction."""

    without_codes = PES_CODE_RE.sub(" ", text)
    return CANDIDATE_NUMBER_RE.search(without_codes) is not None


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_config(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        config = yaml.safe_load(handle)
    if config["seed"] != config["split"]["seed"]:
        raise ValueError("Top-level and split seeds must be identical")
    if config["dev_fraction"] != config["split"]["dev_fraction"]:
        raise ValueError("Top-level and split dev fractions must be identical")
    return config


def load_json(path: Path):
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def read_jsonl(path: Path) -> Iterator[dict]:
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                yield json.loads(line)


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(text, encoding="utf-8", newline="\n")
    temporary.replace(path)


def write_json(path: Path, payload: dict) -> None:
    text = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    _atomic_write_text(path, text)


def write_jsonl(path: Path, rows: Iterable[dict]) -> None:
    text = "".join(
        json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows
    )
    _atomic_write_text(path, text)


def validate_raw_rows(rows: list[dict]) -> None:
    missing = [row.get("id") for row in rows if not REQUIRED_QA_FIELDS <= set(row)]
    if missing:
        raise ValueError(f"Rows with missing required fields: {missing[:10]}")
    ids = [row["id"] for row in rows]
    if len(ids) != len(set(ids)):
        raise ValueError("QA ids are not unique")
    for row in rows:
        extract_answer_text(row)
        classify_question(row["question"])


def load_chunk_corpus(chunks_dir: Path) -> tuple[list[dict], dict[str, str]]:
    normalized_sources: dict[str, str] = {}
    flattened: list[dict] = []
    for path in sorted(chunks_dir.glob("*.json"), key=lambda item: item.name):
        doc_id = normalize_filename(path.name)
        if doc_id in normalized_sources:
            raise ValueError(
                f"Filename normalization collision: {path.name!r} and "
                f"{normalized_sources[doc_id]!r}"
            )
        normalized_sources[doc_id] = path.name
        chunks = load_json(path)
        if not isinstance(chunks, list):
            raise ValueError(f"Chunk file is not a list: {path}")
        for chunk in chunks:
            if not REQUIRED_CHUNK_FIELDS <= set(chunk):
                raise ValueError(f"Invalid chunk schema in {path.name}")
            flattened.append(
                {
                    "doc_id": doc_id,
                    "source_file": path.name,
                    "pdf_name": normalize_filename(chunk["pdf_name"]),
                    "page_number": chunk["page_number"],
                    "chunk_index": chunk["chunk_index"],
                    "text": chunk["text"],
                }
            )
    flattened.sort(key=lambda row: (row["doc_id"], row["page_number"], row["chunk_index"]))
    return flattened, normalized_sources


def build_chunk_index(chunks: Iterable[dict]) -> dict[tuple[str, int, int], dict]:
    index: dict[tuple[str, int, int], dict] = {}
    for chunk in chunks:
        key = (chunk["doc_id"], chunk["page_number"], chunk["chunk_index"])
        if key in index:
            raise ValueError(f"Duplicate chunk join key: {key!r}")
        index[key] = chunk
    return index


def deduplicate_rows(rows: Iterable[dict]) -> tuple[list[dict], list[dict]]:
    """Keep the smallest original id for each normalized document/question."""

    groups: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for row in rows:
        key = (normalize_filename(row["file"]), row["question"].strip())
        groups[key].append(row)

    kept: list[dict] = []
    audit: list[dict] = []
    for (doc_id, question), group in sorted(groups.items()):
        ordered = sorted(group, key=lambda row: row["id"])
        kept.append(ordered[0])
        if len(ordered) > 1:
            audit.append(
                {
                    "doc_id": doc_id,
                    "question": question,
                    "question_type": classify_question(question),
                    "kept_id": ordered[0]["id"],
                    "dropped_ids": [row["id"] for row in ordered[1:]],
                    "group_size": len(ordered),
                    "answers_identical": len(
                        {extract_answer_text(row) for row in ordered}
                    )
                    == 1,
                    "contexts_identical": len({row["context"] for row in ordered}) == 1,
                }
            )
    kept.sort(key=lambda row: row["id"])
    audit.sort(key=lambda row: row["kept_id"])
    return kept, audit


def split_documents(
    documents: Iterable[str], *, seed: int, dev_fraction: float
) -> tuple[set[str], set[str]]:
    ordered = sorted(set(documents))
    shuffled = ordered.copy()
    random.Random(seed).shuffle(shuffled)
    dev_count = int(round(len(shuffled) * dev_fraction))
    if not 0 < dev_count < len(shuffled):
        raise ValueError("Split must assign at least one document to each partition")
    dev = set(shuffled[:dev_count])
    test = set(shuffled[dev_count:])
    if dev & test or dev | test != set(ordered):
        raise AssertionError("Document split is not disjoint and exhaustive")
    return dev, test


def _count_by_type(rows: Iterable[dict]) -> dict[str, int]:
    counts = Counter(row["question_type"] for row in rows)
    return {label: counts[label] for label in QUESTION_TYPES}


def _count_flags(rows: Iterable[dict]) -> dict[str, int]:
    materialized = list(rows)
    return {
        "qa": len(materialized),
        "has_number": sum(row["has_number"] for row in materialized),
        "has_pes_code": sum(row["has_pes_code"] for row in materialized),
        "context_changed": sum(row["context_changed"] for row in materialized),
    }


def run_preprocessing(root: Path, config_path: Path) -> PreprocessingResult:
    config = load_config(config_path)
    dataset_path = root / config["paths"]["dataset"]
    chunks_dir = root / config["paths"]["chunks_dir"]
    processed_dir = root / config["paths"]["processed_dir"]

    raw_rows = load_json(dataset_path)
    if not isinstance(raw_rows, list):
        raise ValueError("Dataset root must be a list")
    validate_raw_rows(raw_rows)

    chunks, normalized_sources = load_chunk_corpus(chunks_dir)
    chunk_index = build_chunk_index(chunks)
    deduplicated, dedup_audit = deduplicate_rows(raw_rows)

    qa_documents = {normalize_filename(row["file"]) for row in raw_rows}
    chunk_documents = set(normalized_sources)
    unmatched_documents = sorted(qa_documents - chunk_documents)
    if unmatched_documents:
        raise ValueError(f"QA documents without chunk files: {unmatched_documents}")

    dev_documents, test_documents = split_documents(
        {normalize_filename(row["file"]) for row in deduplicated},
        seed=config["seed"],
        dev_fraction=config["dev_fraction"],
    )

    processed_rows: list[dict] = []
    failed_joins: list[dict] = []
    for row in deduplicated:
        doc_id = normalize_filename(row["file"])
        join_key = (doc_id, row["page_number"], row["chunk_index"])
        chunk = chunk_index.get(join_key)
        if chunk is None:
            failed_joins.append(
                {
                    "id": row["id"],
                    "doc_id": doc_id,
                    "page_number": row["page_number"],
                    "chunk_index": row["chunk_index"],
                }
            )
            continue
        gold_answer = extract_answer_text(row)
        canonical_context = chunk["text"]
        processed_rows.append(
            {
                "id": row["id"],
                "doc_id": doc_id,
                "source_file": row["file"],
                "report_title": row["report_title"],
                "page_number": row["page_number"],
                "chunk_index": row["chunk_index"],
                "question": row["question"].strip(),
                "question_type": classify_question(row["question"]),
                "gold_answer": gold_answer,
                "medical_diagnosis": row["medical_diagnosis"],
                "anthropometric_assessment": row["anthropometric_assessment"],
                "context": canonical_context,
                "dataset_context": row["context"],
                "context_changed": canonical_context != row["context"],
                "has_number": contains_numeric_candidate(gold_answer),
                "has_pes_code": contains_pes_code(gold_answer),
                "number_flag_version": config["flags"]["has_number_version"],
                "split": "dev" if doc_id in dev_documents else "test",
            }
        )

    if failed_joins:
        raise ValueError(f"Failed QA-to-chunk joins: {failed_joins[:10]}")
    processed_rows.sort(key=lambda row: row["id"])
    dev_rows = [row for row in processed_rows if row["split"] == "dev"]
    test_rows = [row for row in processed_rows if row["split"] == "test"]

    observed_dev_documents = {row["doc_id"] for row in dev_rows}
    observed_test_documents = {row["doc_id"] for row in test_rows}
    overlap = sorted(observed_dev_documents & observed_test_documents)
    if overlap:
        raise AssertionError(f"Document leakage detected: {overlap}")

    missing_types = {
        split: sorted(set(QUESTION_TYPES) - {row["question_type"] for row in subset})
        for split, subset in (("dev", dev_rows), ("test", test_rows))
    }
    if any(missing_types.values()):
        raise ValueError(f"Question types missing from split: {missing_types}")

    output_paths = {
        "qa_clean": processed_dir / "qa_clean.jsonl",
        "qa_dev": processed_dir / "qa_dev.jsonl",
        "qa_test": processed_dir / "qa_test.jsonl",
        "chunks_clean": processed_dir / "chunks_clean.jsonl",
        "dedup_audit": processed_dir / "dedup_audit.jsonl",
        "split_manifest": processed_dir / "split_manifest.json",
    }
    write_jsonl(output_paths["qa_clean"], processed_rows)
    write_jsonl(output_paths["qa_dev"], dev_rows)
    write_jsonl(output_paths["qa_test"], test_rows)
    write_jsonl(output_paths["chunks_clean"], chunks)
    write_jsonl(output_paths["dedup_audit"], dedup_audit)

    summary = {
        "config": {
            "seed": config["seed"],
            "dev_fraction": config["dev_fraction"],
            "deduplication": config["deduplication"],
            "context": config["context"],
            "flags": config["flags"],
        },
        "fingerprints": {
            "dataset_sha256": sha256(dataset_path),
            "chunk_file_count": len(normalized_sources),
        },
        "reconciliation": {
            "raw_qa": len(raw_rows),
            "duplicate_groups": len(dedup_audit),
            "duplicate_rows_removed": len(raw_rows) - len(deduplicated),
            "after_deduplication": len(deduplicated),
            "joined": len(processed_rows),
            "failed_joins": len(failed_joins),
            "final_qa": len(processed_rows),
            "documents": len(qa_documents),
            "chunks": len(chunks),
        },
        "splits": {
            "dev": {
                "documents": len(observed_dev_documents),
                **_count_flags(dev_rows),
                "question_types": _count_by_type(dev_rows),
            },
            "test": {
                "documents": len(observed_test_documents),
                **_count_flags(test_rows),
                "question_types": _count_by_type(test_rows),
            },
        },
        "checks": {
            "document_overlap": len(overlap),
            "missing_question_types": missing_types,
            "answer_start_retained": False,
            "canonical_context": "chunk_corpus",
        },
        "documents": {
            "dev": sorted(dev_documents),
            "test": sorted(test_documents),
        },
    }
    write_json(output_paths["split_manifest"], summary)
    return PreprocessingResult(summary=summary, output_paths=tuple(output_paths.values()))

