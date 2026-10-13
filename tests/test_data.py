from __future__ import annotations

import random

import pytest

from src.data import (
    QUESTION_TYPES,
    classify_question,
    contains_numeric_candidate,
    contains_pes_code,
    deduplicate_rows,
    normalize_filename,
    split_documents,
)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("LAPORAN#U2019A.chunks.json", "LAPORAN’A.chunks.json"),
        ("A\u2060B.chunks.json", "AB.chunks.json"),
        ("ＡＢＣ.chunks.json", "ABC.chunks.json"),
        ("  laporan.chunks.json  ", "laporan.chunks.json"),
    ],
)
def test_normalize_filename(raw: str, expected: str) -> None:
    assert normalize_filename(raw) == expected


@pytest.mark.parametrize(
    ("question", "expected"),
    [
        ("Apa metode skrining status gizi yang direkomendasikan?", "Skrining"),
        ("Bagaimana status gizi pada pasien ini?", "Status gizi"),
        ("Bagaimana data biokimia/parameter lab pada pasien?", "Biokimia/lab"),
        ("Bagaimana menyusun diagnosis gizi dengan format PES?", "Diagnosis PES"),
        ("Apa tujuan diet pada pasien ini?", "Tujuan diet"),
        ("Bagaimana prinsip diet yang tepat?", "Prinsip diet"),
        ("Bagaimana syarat diet yang harus dipenuhi?", "Syarat diet"),
        ("Apa pedoman diet yang digunakan?", "Pedoman diet"),
    ],
)
def test_classify_question(question: str, expected: str) -> None:
    assert classify_question(question) == expected


def test_all_question_type_labels_are_covered() -> None:
    examples = [
        "metode skrining",
        "status gizi",
        "data biokimia",
        "format PES",
        "tujuan diet",
        "prinsip diet",
        "syarat diet",
        "pedoman diet",
    ]
    assert {classify_question(example) for example in examples} == set(QUESTION_TYPES)


def test_unknown_question_is_rejected() -> None:
    with pytest.raises(ValueError, match="Unrecognized question template"):
        classify_question("Pertanyaan di luar delapan template")


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Energi 1.705,8 kkal", True),
        ("Asupan 15%", True),
        ("Z-score -3 SD", True),
        ("Tidak terdapat angka", False),
        ("Diagnosis NI-2.1", False),
    ],
)
def test_provisional_number_flag(text: str, expected: bool) -> None:
    assert contains_numeric_candidate(text) is expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Diagnosis NI-2.1", True),
        ("Diagnosis NC 4.1", True),
        ("Diagnosis NB.1.1", True),
        ("Energi 2000 kkal", False),
    ],
)
def test_pes_code_flag(text: str, expected: bool) -> None:
    assert contains_pes_code(text) is expected


def _qa_row(identifier: int, answer: str = "jawaban") -> dict:
    return {
        "id": identifier,
        "file": "dokumen.chunks.json",
        "question": "Apa tujuan diet pada pasien ini?",
        "answer": {"text": [answer], "answer_start": [0]},
        "context": f"konteks {identifier}",
    }


def test_deduplication_keeps_smallest_id_independent_of_input_order() -> None:
    rows = [_qa_row(9, "sembilan"), _qa_row(2, "dua"), _qa_row(5, "lima")]
    random.Random(99).shuffle(rows)
    kept, audit = deduplicate_rows(rows)
    assert [row["id"] for row in kept] == [2]
    assert audit[0]["kept_id"] == 2
    assert audit[0]["dropped_ids"] == [5, 9]
    assert audit[0]["answers_identical"] is False


def test_document_split_is_deterministic_disjoint_and_exhaustive() -> None:
    documents = [f"doc-{index:03d}" for index in range(120)]
    first_dev, first_test = split_documents(documents, seed=42, dev_fraction=0.2)
    second_dev, second_test = split_documents(
        reversed(documents), seed=42, dev_fraction=0.2
    )
    assert first_dev == second_dev
    assert first_test == second_test
    assert len(first_dev) == 24
    assert len(first_test) == 96
    assert not first_dev & first_test
    assert first_dev | first_test == set(documents)

