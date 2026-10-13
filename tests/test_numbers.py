from __future__ import annotations

from decimal import Decimal

import pytest

from src.numbers import (
    NumberConfig,
    canonical_decimal,
    extract_numbers,
    extract_pes_codes,
    has_number,
    normalize_number,
    normalize_pes_code,
    numbers_match,
)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("1705,8", "1705.8"),
        ("1.705,8", "1705.8"),
        ("2.000", "2000"),
        ("12.000", "12000"),
        ("1.500.000", "1500000"),
        ("1.5", "1.5"),
        ("12.5", "12.5"),
        ("-3,2", "-3.2"),
        ("−2,5", "-2.5"),
        ("+15", "15"),
        ("0,01", "0.01"),
        ("15", "15"),
    ],
)
def test_normalize_number(raw: str, expected: str) -> None:
    assert canonical_decimal(normalize_number(raw)) == expected


@pytest.mark.parametrize(
    ("text", "values"),
    [
        ("Energi 1705,8 kkal", ["1705.8"]),
        ("Energi 1.705,8 kkal", ["1705.8"]),
        ("Kebutuhan 2.000 kkal", ["2000"]),
        ("Nilai 1.5", ["1.5"]),
        ("Rentang 136–145 mg/dL", ["136", "145"]),
        ("Rentang 136-145 mg/dL", ["136", "145"]),
        ("Rentang 136 - 145 mg/dL", ["136", "145"]),
        ("Z-score -3,2 SD", ["-3.2"]),
        ("Rentang z-score -3 – -2 SD", ["-3", "-2"]),
        ("BB/U = - 3,3 SD", ["-3.3"]),
        ("Protein 15% dan lemak 20 %", ["15", "20"]),
        ("BB 55 kg, TB 165 cm", ["55", "165"]),
        ("Hb 9,6 g/dL", ["9.6"]),
        ("Usia 2 tahun 6 bulan", ["2", "6"]),
        ("Volume 1.500 mL", ["1500"]),
        ("Frekuensi 3x150 ml", ["3", "150"]),
        ("Persentil P97 dan vitamin B12 serta formula S26", []),
        ("Tidak ada angka", []),
    ],
)
def test_extract_numbers(text: str, values: list[str]) -> None:
    assert [mention.normalized for mention in extract_numbers(text)] == values


@pytest.mark.parametrize(
    "text",
    [
        "1. Energi diberikan sesuai kebutuhan",
        "2) Protein diberikan tinggi",
        "• 3. Lemak diberikan cukup",
        "(4) Karbohidrat diberikan cukup",
        "Halaman 12",
        "hal. 7 dari laporan",
        "Page: 9",
        "2.4 Intervensi Gizi",
        "3.1.2 Rencana Monitoring",
        "\n45\n",
        "Diagnosis NI-2.1",
        "Rekomendasi protein (IDAI, 2011)",
        "Menurut Kemenkes RI tahun 2020",
        "WHO (2006)",
        "Grafik Fenton, 2013",
        "(Penulis A, 2019; Penulis B, 2020)",
        "(Penulis,\n2021)",
    ],
)
def test_excluded_numbers(text: str) -> None:
    assert extract_numbers(text) == []


def test_list_marker_does_not_remove_clinical_number_after_it() -> None:
    mentions = extract_numbers("1. Energi diberikan 1700 kkal")
    assert [mention.normalized for mention in mentions] == ["1700"]


def test_section_like_decimal_with_unit_is_not_excluded() -> None:
    mentions = extract_numbers("2.4 kg")
    assert [mention.normalized for mention in mentions] == ["2.4"]


def test_non_citation_clinical_year_is_retained() -> None:
    mentions = extract_numbers("Pasien dirawat pada tahun 2020")
    assert [mention.normalized for mention in mentions] == ["2020"]


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("NI-2.1", "NI-2.1"),
        ("ni 2.1", "NI-2.1"),
        ("NI.2.1", "NI-2.1"),
        ("NI - 2.1", "NI-2.1"),
        ("NC 4.1", "NC-4.1"),
        ("NB.1.1", "NB-1.1"),
        ("NI2.1", "NI-2.1"),
        ("NC-1", "NC-1"),
        ("NB 1.2.3", "NB-1.2.3"),
    ],
)
def test_normalize_pes_code(raw: str, expected: str) -> None:
    assert normalize_pes_code(raw) == expected


def test_multiple_pes_codes_are_separate_and_not_ordinary_numbers() -> None:
    text = "Diagnosis NI-2.1 dan NC 4.1."
    assert [code.normalized for code in extract_pes_codes(text)] == ["NI-2.1", "NC-4.1"]
    assert extract_numbers(text) == []


@pytest.mark.parametrize(
    ("left", "right", "expected"),
    [
        ("100", "100.5", True),
        ("100", "100.51", False),
        ("0.10", "0.11", True),
        ("0.10", "0.111", False),
        ("2000", "2009", True),
        ("2000", "2011", False),
        ("-3", "-3.01", True),
        ("-3", "-3.02", False),
        ("0", "0", True),
        ("0", "0.02", False),
    ],
)
def test_numbers_match(left: str, right: str, expected: bool) -> None:
    assert numbers_match(Decimal(left), Decimal(right)) is expected


@pytest.mark.parametrize(
    ("text", "category", "unit", "is_percent"),
    [
        ("Energi 1700 kkal", "energy", "kkal", False),
        ("Protein 15%", "percentage", "%", True),
        ("Hb 9,6 g/dL", "laboratory", "g/dL", False),
        ("BB/U -3 SD", "anthropometry_zscore", "SD", False),
        ("Berat badan 55 kg", "weight_height", "kg", False),
        ("Usia 2 tahun", "other", "tahun", False),
    ],
)
def test_number_categories(
    text: str, category: str, unit: str, is_percent: bool
) -> None:
    mention = extract_numbers(text)[0]
    assert mention.category == category
    assert mention.unit == unit
    assert mention.is_percent is is_percent


def test_tolerance_can_be_configured() -> None:
    strict = NumberConfig(
        relative_tolerance=Decimal("0"), absolute_tolerance=Decimal("0")
    )
    assert numbers_match("1", "1", strict)
    assert not numbers_match("1", "1.001", strict)


def test_number_mention_serialization_uses_string_decimal() -> None:
    payload = extract_numbers("Energi 1.705,8 kkal")[0].to_dict()
    assert payload["value"] == "1705.8"
    assert payload["normalized"] == "1705.8"


def test_has_number_excludes_pes_only_text() -> None:
    assert not has_number("Diagnosis NI-2.1")
    assert has_number("Diagnosis NI-2.1 dengan asupan 75%")

