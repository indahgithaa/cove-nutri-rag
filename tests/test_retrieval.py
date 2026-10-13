from __future__ import annotations

from decimal import Decimal

import pytest

from src.numbers import NumberConfig
from src.retrieval import (
    DocumentBM25,
    RetrievalConfig,
    build_document_indexes,
    context_record,
    default_query_stopwords,
    gold_chunk_id,
    make_chunk_id,
    normalize_text,
    numeric_coverage,
    select_condition,
    tokenize_document,
    tokenize_query,
)


def config() -> RetrievalConfig:
    return RetrievalConfig(
        k1=1.5,
        b=0.75,
        epsilon=0.25,
        additional_query_stopwords=frozenset(
            {"apa", "bagaimana", "yang", "ini", "pasien"}
        ),
        conditions={"normal": (1, 3), "degraded": (4, 6)},
    )


def chunks(doc_id: str = "doc") -> list[dict]:
    texts = [
        "energi pasien adalah 1700 kkal",
        "protein diberikan 50 gram",
        "natrium dibatasi 1500 mg",
        "cairan diberikan bertahap",
        "hasil pemeriksaan umum",
        "pedoman makan rumah sakit",
        "catatan pulang pasien",
    ]
    return [
        {
            "doc_id": doc_id,
            "page_number": index // 2 + 1,
            "chunk_index": index,
            "text": text,
        }
        for index, text in enumerate(texts)
    ]


def test_normalize_text_uses_nfkc_and_casefold() -> None:
    assert normalize_text("ＥＮＥＲＧＩ") == "energi"


def test_document_tokens_keep_stopwords() -> None:
    assert tokenize_document("Apa energi yang tepat?") == [
        "apa",
        "energi",
        "yang",
        "tepat",
    ]


def test_query_tokens_remove_sastrawi_and_additional_stopwords() -> None:
    stopwords = default_query_stopwords({"apa", "pasien"})
    tokens = tokenize_query("Apa kebutuhan energi untuk pasien?", stopwords)
    assert tokens == ["kebutuhan", "energi"]


def test_chunk_id_is_stable() -> None:
    assert make_chunk_id("dokumen", 2, 7) == "dokumen::page=2::chunk=7"


def test_gold_chunk_id_uses_qrel_location() -> None:
    qa = {"doc_id": "dokumen", "page_number": 2, "chunk_index": 7}
    assert gold_chunk_id(qa) == "dokumen::page=2::chunk=7"


def test_document_index_rejects_mixed_documents() -> None:
    mixed = chunks("a")[:3] + chunks("b")[:3]
    with pytest.raises(ValueError, match="different documents"):
        DocumentBM25(mixed, config())


def test_document_index_requires_rank_six() -> None:
    with pytest.raises(ValueError, match="rank 6"):
        DocumentBM25(chunks()[:5], config())


def test_build_indexes_rejects_duplicate_chunk_ids() -> None:
    duplicated = chunks() + [chunks()[0]]
    with pytest.raises(ValueError, match="Duplicate chunk id"):
        build_document_indexes(duplicated, config())


def test_ranking_is_scoped_to_requested_document() -> None:
    indexes = build_document_indexes(chunks("a") + chunks("b"), config())
    ranking = indexes["a"].rank(["energi"])
    assert {item.doc_id for item in ranking} == {"a"}
    assert ranking[0].text == "energi pasien adalah 1700 kkal"


def test_ties_are_broken_by_page_and_chunk() -> None:
    ranking = DocumentBM25(chunks(), config()).rank(["token_tidak_ada"])
    assert [(item.page_number, item.chunk_index) for item in ranking] == [
        (1, 0),
        (1, 1),
        (2, 2),
        (2, 3),
        (3, 4),
        (3, 5),
        (4, 6),
    ]


def test_normal_condition_selects_ranks_one_to_three() -> None:
    ranking = DocumentBM25(chunks(), config()).rank(["energi"])
    assert [item.rank for item in select_condition(ranking, "normal", config())] == [
        1,
        2,
        3,
    ]


def test_degraded_condition_selects_ranks_four_to_six() -> None:
    ranking = DocumentBM25(chunks(), config()).rank(["energi"])
    assert [item.rank for item in select_condition(ranking, "degraded", config())] == [
        4,
        5,
        6,
    ]


def test_conditions_are_disjoint() -> None:
    ranking = DocumentBM25(chunks(), config()).rank(["energi"])
    normal = {item.chunk_id for item in select_condition(ranking, "normal", config())}
    degraded = {
        item.chunk_id for item in select_condition(ranking, "degraded", config())
    }
    assert normal.isdisjoint(degraded)


def test_unknown_condition_is_rejected() -> None:
    ranking = DocumentBM25(chunks(), config()).rank(["energi"])
    with pytest.raises(KeyError, match="Unknown retrieval condition"):
        select_condition(ranking, "other", config())


def test_numeric_coverage_uses_stage_three_tolerance() -> None:
    ranking = DocumentBM25(chunks(), config()).rank(["energi"])
    selected = select_condition(ranking, "normal", config())
    hits, total = numeric_coverage(
        "Kebutuhan energi 1705 kkal dan protein 50 gram",
        selected,
        NumberConfig(relative_tolerance=Decimal("0.005")),
    )
    assert (hits, total) == (2, 2)


def test_numeric_coverage_handles_answer_without_numbers() -> None:
    ranking = DocumentBM25(chunks(), config()).rank(["energi"])
    assert numeric_coverage("Tidak ada angka", ranking[:3], NumberConfig()) == (0, 0)


def test_context_record_never_contains_gold_answer() -> None:
    qa = {
        "id": 1,
        "doc_id": "doc",
        "split": "dev",
        "question": "Apa kebutuhan energi?",
        "question_type": "Syarat diet",
        "gold_answer": "Rahasia 1700 kkal",
    }
    selected = DocumentBM25(chunks(), config()).rank(["energi"])[:3]
    record = context_record(
        qa,
        condition="normal",
        query_tokens=["kebutuhan", "energi"],
        selected=selected,
    )
    assert "gold_answer" not in record
    assert "Rahasia" not in str(record)

