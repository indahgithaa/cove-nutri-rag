"""Generate the read-only Stage 1 exploratory data analysis artifacts.

This script intentionally does not create processed datasets. Numeric parsing in
this stage is exploratory; the validated implementation belongs to Stage 3.
"""

from __future__ import annotations

import hashlib
import json
import random
import re
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from statistics import mean, median
from typing import Iterable

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


ROOT = Path(__file__).resolve().parents[1]
DATASET_PATH = ROOT / "data" / "dataset" / "dataset.json"
CHUNKS_DIR = ROOT / "data" / "chunks"
REPORT_PATH = ROOT / "reports" / "01_eda.md"
FIGURES_DIR = ROOT / "reports" / "figures"
RANDOM_SEED = 42

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

PES_RE = re.compile(r"\bN[ICB]\s*[-.]?\s*\d+(?:\.\d+)+\b", re.IGNORECASE)
NUMBER_RE = re.compile(
    r"(?<![A-Za-z])"
    r"(?P<sign>[+-]?)"
    r"(?P<number>"
    r"(?:\d{1,3}(?:\.\d{3})+(?:,\d+)?|\d+\.\d+|\d+(?:,\d+)?)"
    r")"
    r"(?P<percent>\s*%)?"
)


@dataclass(frozen=True)
class NumberHit:
    raw: str
    value: Decimal
    start: int
    end: int
    is_percent: bool


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def chunk_manifest_sha256(paths: Iterable[Path]) -> str:
    digest = hashlib.sha256()
    for path in sorted(paths, key=lambda item: item.name):
        digest.update(path.name.encode("utf-8"))
        digest.update(b"\0")
        digest.update(sha256(path).encode("ascii"))
        digest.update(b"\n")
    return digest.hexdigest()


def normalize_filename(value: str) -> str:
    value = re.sub(
        r"#U([0-9A-Fa-f]{4,6})",
        lambda match: chr(int(match.group(1), 16)),
        value,
    )
    return unicodedata.normalize("NFKC", value).replace("\u2060", "").strip()


def normalize_question(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip()).casefold()


def question_type(question: str) -> str:
    normalized = normalize_question(question)
    rules = (
        ("skrining", "Skrining"),
        ("status gizi", "Status gizi"),
        ("biokimia", "Biokimia/lab"),
        ("format pes", "Diagnosis PES"),
        ("tujuan diet", "Tujuan diet"),
        ("prinsip diet", "Prinsip diet"),
        ("syarat diet", "Syarat diet"),
        ("pedoman diet", "Pedoman diet"),
    )
    for marker, label in rules:
        if marker in normalized:
            return label
    return "Tidak terpetakan"


def answer_text(row: dict) -> str:
    return row["answer"]["text"][0]


def word_count(text: str) -> int:
    return len(re.findall(r"(?u)\b\w+\b", text))


def length_summary(values: list[int]) -> dict[str, float]:
    array = np.asarray(values)
    return {
        "min": int(array.min()),
        "p25": float(np.percentile(array, 25)),
        "median": float(np.median(array)),
        "mean": float(array.mean()),
        "p75": float(np.percentile(array, 75)),
        "max": int(array.max()),
    }


def normalize_numeric_value(raw: str) -> Decimal | None:
    value = raw.strip().replace(" ", "")
    if "," in value:
        value = value.replace(".", "").replace(",", ".")
    elif re.fullmatch(r"[+-]?\d{1,3}(?:\.\d{3})+", value):
        value = value.replace(".", "")
    try:
        return Decimal(value)
    except InvalidOperation:
        return None


def extract_numbers(text: str, minimum_two_digits: bool = False) -> list[NumberHit]:
    # PES codes are evaluated separately so their components do not inflate the
    # ordinary-number counts.
    masked = list(text)
    for code in PES_RE.finditer(text):
        for position in range(code.start(), code.end()):
            masked[position] = " "
    searchable = "".join(masked)

    hits: list[NumberHit] = []
    for match in NUMBER_RE.finditer(searchable):
        raw = match.group("sign") + match.group("number")
        if minimum_two_digits and sum(char.isdigit() for char in raw) < 2:
            continue
        value = normalize_numeric_value(raw)
        if value is None:
            continue
        hits.append(
            NumberHit(
                raw=raw,
                value=value,
                start=match.start(),
                end=match.end(),
                is_percent=bool(match.group("percent")),
            )
        )
    return hits


def numbers_match(left: Decimal, right: Decimal) -> bool:
    absolute_difference = abs(left - right)
    if absolute_difference <= Decimal("0.01"):
        return True
    if left == 0:
        return False
    return absolute_difference / abs(left) <= Decimal("0.005")


def number_is_present(value: Decimal, candidates: Iterable[Decimal]) -> bool:
    return any(numbers_match(value, candidate) for candidate in candidates)


def number_category(text: str, hit: NumberHit) -> str:
    before = text[max(0, hit.start - 45) : hit.start].casefold()
    after = text[hit.end : min(len(text), hit.end + 45)].casefold()
    window = before + text[hit.start : hit.end].casefold() + after

    if hit.is_percent or re.search(r"^\s*persen\b", after):
        return "Persentase"
    if re.search(r"^\s*(?:kkal|kcal)\b", after) or re.search(
        r"(?:energi|kalori)\s*(?:=|sebesar|sebanyak)?\s*$", before
    ):
        return "Energi/kkal"
    if re.search(
        r"(?:mg|g|gr|mmol|mEq)/(?:dL|L)|fL\b|pg\b|/uL\b|/µL\b", after, re.I
    ) or re.search(
        r"(?:hemoglobin|\bhb|albumin|natrium|kalium|leukosit|trombosit|"
        r"hematokrit|mcv|mchc?|gds|sgot|sgpt)\s*[:=]?\s*$",
        before,
    ):
        return "Nilai laboratorium"
    if re.search(
        r"z[ -]?score|simpang baku|standar deviasi|\bsd\b|imt|persentil|"
        r"bb/u|tb/u|pb/u|bb/tb|lila/u",
        window,
    ):
        return "Antropometri/z-score"
    if re.search(r"^\s*(?:kg|cm)\b", after) or re.search(
        r"(?:\bbb|\btb|berat badan|tinggi badan|lila|lingkar lengan)\s*[:=]?\s*$",
        before,
    ):
        return "Berat/tinggi badan"
    return "Lainnya"


def pct(numerator: int, denominator: int) -> str:
    return f"{100 * numerator / denominator:.2f}%".replace(".", ",")


def decimal_id(value: float, digits: int = 2) -> str:
    return f"{value:.{digits}f}".replace(".", ",")


def markdown_table(headers: list[str], rows: list[list[object]]) -> str:
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in rows:
        escaped = [str(value).replace("|", "\\|") for value in row]
        lines.append("| " + " | ".join(escaped) + " |")
    return "\n".join(lines)


def compact_fragment(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip(" ,;:-")


def numeric_examples(rows: list[dict]) -> dict[str, str]:
    patterns = {
        "Energi/kkal": re.compile(r"\b\d[\d.,]*\s*kkal(?:/[A-Za-z]+)?", re.I),
        "Persentase": re.compile(r"\b\d[\d.,]*\s*%"),
        "Nilai laboratorium": re.compile(
            r"\b(?:Hb|hemoglobin|albumin|natrium|kalium|leukosit|trombosit|"
            r"hematokrit)\s*[:=]?\s*(?:rendah|tinggi)?\s*\d[\d.,]*"
            r"(?:\s*(?:g?r?/d[lL]|mg/d[lL]|mmol/[lL]|%|/[uµ][lL]))?",
            re.I,
        ),
        "Antropometri/z-score": re.compile(
            r"\b(?:z[ -]?score|BB/U|TB/U|PB/U|BB/TB|IMT/U)\s*"
            r"(?:[=:]|sebesar)?\s*[<>≤≥]?\s*-?\d[\d.,]*\s*(?:SD)?",
            re.I,
        ),
        "Berat/tinggi badan": re.compile(
            r"\b(?:Berat Badan|Tinggi Badan|BB|TB)\s*[:=]?\s*"
            r"\d[\d.,]*\s*(?:kg|cm)\b",
            re.I,
        ),
        "Kode PES": PES_RE,
        "Lainnya": re.compile(
            r"\b(?:usia gestasi|usia)\s*\d[\d.,]*\s*"
            r"(?:tahun|bulan|minggu|hari)\b",
            re.I,
        ),
    }
    candidates: dict[str, list[str]] = defaultdict(list)
    for row in rows:
        text = answer_text(row)
        for label, pattern in patterns.items():
            for match in pattern.finditer(text):
                candidates[label].append(compact_fragment(match.group(0)))

    rng = random.Random(RANDOM_SEED)
    return {
        label: rng.choice(values) if values else "Tidak ditemukan"
        for label, values in candidates.items()
    }


def save_figures(
    raw_type_counts: Counter,
    dedup_type_counts: Counter,
    numeric_by_type: dict[str, tuple[int, int]],
    answers_by_category: Counter,
) -> None:
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    plt.style.use("seaborn-v0_8-whitegrid")

    positions = np.arange(len(QUESTION_TYPES))
    width = 0.38
    fig, axis = plt.subplots(figsize=(11, 5.5))
    axis.bar(
        positions - width / 2,
        [raw_type_counts[label] for label in QUESTION_TYPES],
        width,
        label="Mentah",
        color="#4472C4",
    )
    axis.bar(
        positions + width / 2,
        [dedup_type_counts[label] for label in QUESTION_TYPES],
        width,
        label="Deduplikasi eksploratif",
        color="#70AD47",
    )
    axis.set_ylabel("Jumlah QA")
    axis.set_title("Distribusi QA menurut tipe pertanyaan")
    axis.set_xticks(positions, QUESTION_TYPES, rotation=28, ha="right")
    axis.legend()
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "01_question_types.png", dpi=300)
    plt.close(fig)

    values = [
        100 * numeric_by_type[label][0] / numeric_by_type[label][1]
        for label in QUESTION_TYPES
    ]
    fig, axis = plt.subplots(figsize=(11, 5.5))
    bars = axis.bar(QUESTION_TYPES, values, color="#ED7D31")
    axis.set_ylim(0, 108)
    axis.set_ylabel("Jawaban dengan angka biasa (%)")
    axis.set_title("Proporsi jawaban berangka menurut tipe pertanyaan")
    axis.tick_params(axis="x", rotation=28)
    for bar, value in zip(bars, values):
        axis.text(
            bar.get_x() + bar.get_width() / 2,
            value + 1.2,
            f"{value:.1f}%",
            ha="center",
            va="bottom",
            fontsize=8,
        )
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "01_numeric_by_type.png", dpi=300)
    plt.close(fig)

    categories = (
        "Energi/kkal",
        "Persentase",
        "Nilai laboratorium",
        "Antropometri/z-score",
        "Berat/tinggi badan",
        "Kode PES",
        "Lainnya",
    )
    fig, axis = plt.subplots(figsize=(10, 5.5))
    bars = axis.barh(
        categories,
        [answers_by_category[label] for label in categories],
        color="#5B9BD5",
    )
    axis.invert_yaxis()
    axis.set_xlabel("Jumlah jawaban (kategori dapat tumpang tindih)")
    axis.set_title("Cakupan kategori angka dalam jawaban gold")
    for bar in bars:
        axis.text(
            bar.get_width() + 3,
            bar.get_y() + bar.get_height() / 2,
            f"{int(bar.get_width())}",
            va="center",
            fontsize=8,
        )
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "01_number_categories.png", dpi=300)
    plt.close(fig)


def main() -> None:
    rows = load_json(DATASET_PATH)
    chunk_paths = sorted(CHUNKS_DIR.glob("*.json"), key=lambda item: item.name)
    chunks_by_name = {
        normalize_filename(path.name): load_json(path) for path in chunk_paths
    }

    required_fields = {
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
    missing_field_rows = sum(not required_fields <= set(row) for row in rows)
    empty_required_values = sum(
        value is None or (isinstance(value, str) and not value.strip())
        for row in rows
        for key, value in row.items()
        if key in required_fields
    )

    all_chunks = [chunk for chunks in chunks_by_name.values() for chunk in chunks]
    chunks_per_document = [len(chunks) for chunks in chunks_by_name.values()]
    chunk_keysets = Counter(tuple(sorted(chunk)) for chunk in all_chunks)

    raw_names = {row["file"] for row in rows}
    disk_names = {path.name for path in chunk_paths}
    normalized_qa_names = {normalize_filename(name) for name in raw_names}
    normalized_disk_names = {normalize_filename(name) for name in disk_names}
    raw_filename_matches = len(raw_names & disk_names)
    normalized_filename_matches = len(normalized_qa_names & normalized_disk_names)
    hash_u_names = sum("#U" in name for name in raw_names | disk_names)
    word_joiner_names = sum("\u2060" in name for name in raw_names | disk_names)

    page_index_joined = 0
    exact_context_joined = 0
    ambiguous_page_index = 0
    report_text: dict[str, str] = {}
    for normalized_name, chunks in chunks_by_name.items():
        report_text[normalized_name] = "\n".join(chunk["text"] for chunk in chunks)

    for row in rows:
        candidates = [
            chunk
            for chunk in chunks_by_name[normalize_filename(row["file"])]
            if chunk["page_number"] == row["page_number"]
            and chunk["chunk_index"] == row["chunk_index"]
        ]
        page_index_joined += bool(candidates)
        ambiguous_page_index += len(candidates) > 1
        exact_context_joined += any(
            chunk["text"] == row["context"] for chunk in candidates
        )

    duplicate_groups: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for row in rows:
        duplicate_groups[(row["file"], row["question"])].append(row)
    duplicate_groups = {
        key: group for key, group in duplicate_groups.items() if len(group) > 1
    }
    duplicate_extra_rows = sum(len(group) - 1 for group in duplicate_groups.values())
    duplicate_multiplicity = Counter(len(group) for group in duplicate_groups.values())
    duplicate_same_answer = sum(
        len({answer_text(row) for row in group}) == 1
        for group in duplicate_groups.values()
    )
    duplicate_same_context = sum(
        len({row["context"] for row in group}) == 1
        for group in duplicate_groups.values()
    )

    seen_pairs: set[tuple[str, str]] = set()
    deduplicated_rows = []
    for row in rows:
        key = (row["file"], row["question"])
        if key not in seen_pairs:
            deduplicated_rows.append(row)
            seen_pairs.add(key)

    total_answer_spans = 0
    valid_answer_starts = 0
    for row in rows:
        texts = row["answer"].get("text", [])
        starts = row["answer"].get("answer_start", [])
        for index, text in enumerate(texts):
            total_answer_spans += 1
            start = starts[index] if index < len(starts) else None
            valid_answer_starts += (
                isinstance(start, int)
                and start >= 0
                and row["context"][start : start + len(text)] == text
            )

    raw_type_counts = Counter(question_type(row["question"]) for row in rows)
    dedup_type_counts = Counter(
        question_type(row["question"]) for row in deduplicated_rows
    )
    unique_question_templates = len(
        {normalize_question(row["question"]) for row in rows}
    )

    length_summaries = {
        "Pertanyaan (kata)": length_summary(
            [word_count(row["question"]) for row in rows]
        ),
        "Jawaban (kata)": length_summary([word_count(answer_text(row)) for row in rows]),
        "Jawaban (karakter)": length_summary([len(answer_text(row)) for row in rows]),
        "Konteks gold (kata)": length_summary(
            [word_count(row["context"]) for row in rows]
        ),
    }

    ordinary_numbers = {row["id"]: extract_numbers(answer_text(row)) for row in rows}
    two_digit_numbers = {
        row["id"]: extract_numbers(answer_text(row), minimum_two_digits=True)
        for row in rows
    }
    answers_with_number = sum(bool(ordinary_numbers[row["id"]]) for row in rows)
    answers_with_two_digit_number = sum(
        bool(two_digit_numbers[row["id"]]) for row in rows
    )
    raw_two_digit_regex_count = sum(
        bool(re.search(r"\d{2,}", answer_text(row))) for row in rows
    )
    numeric_counts = [len(ordinary_numbers[row["id"]]) for row in rows]
    positive_numeric_counts = [count for count in numeric_counts if count]

    numeric_by_type: dict[str, tuple[int, int]] = {}
    two_digit_by_type: dict[str, tuple[int, int]] = {}
    for label in QUESTION_TYPES:
        subset = [row for row in rows if question_type(row["question"]) == label]
        numeric_by_type[label] = (
            sum(bool(ordinary_numbers[row["id"]]) for row in subset),
            len(subset),
        )
        two_digit_by_type[label] = (
            sum(bool(two_digit_numbers[row["id"]]) for row in subset),
            len(subset),
        )

    category_tokens: Counter = Counter()
    answers_by_category: Counter = Counter()
    for row in rows:
        present = set()
        text = answer_text(row)
        for hit in ordinary_numbers[row["id"]]:
            label = number_category(text, hit)
            category_tokens[label] += 1
            present.add(label)
        answers_by_category.update(present)
        if PES_RE.search(text):
            answers_by_category["Kode PES"] += 1
            category_tokens["Kode PES"] += len(PES_RE.findall(text))

    pes_diagnosis_rows = [
        row for row in rows if question_type(row["question"]) == "Diagnosis PES"
    ]
    pes_diagnosis_with_code = sum(
        bool(PES_RE.search(answer_text(row))) for row in pes_diagnosis_rows
    )

    report_numbers = {
        name: [hit.value for hit in extract_numbers(text)]
        for name, text in report_text.items()
    }
    total_gold_numbers = 0
    report_number_hits = 0
    chunk_number_hits = 0
    numbered_answers = 0
    all_numbers_in_report = 0
    all_numbers_in_chunk = 0
    for row in rows:
        answer_values = [hit.value for hit in ordinary_numbers[row["id"]]]
        if not answer_values:
            continue
        numbered_answers += 1
        document_values = report_numbers[normalize_filename(row["file"])]
        context_values = [hit.value for hit in extract_numbers(row["context"])]
        report_matches = [
            number_is_present(value, document_values) for value in answer_values
        ]
        chunk_matches = [
            number_is_present(value, context_values) for value in answer_values
        ]
        total_gold_numbers += len(answer_values)
        report_number_hits += sum(report_matches)
        chunk_number_hits += sum(chunk_matches)
        all_numbers_in_report += all(report_matches)
        all_numbers_in_chunk += all(chunk_matches)

    examples = numeric_examples(rows)
    save_figures(raw_type_counts, dedup_type_counts, numeric_by_type, answers_by_category)

    type_rows = []
    for label in QUESTION_TYPES:
        with_number, total = numeric_by_type[label]
        with_two_digits, _ = two_digit_by_type[label]
        type_rows.append(
            [
                label,
                raw_type_counts[label],
                dedup_type_counts[label],
                f"{with_number} ({pct(with_number, total)})",
                f"{with_two_digits} ({pct(with_two_digits, total)})",
            ]
        )

    length_rows = []
    for label, values in length_summaries.items():
        length_rows.append(
            [
                label,
                values["min"],
                decimal_id(values["p25"], 1),
                decimal_id(values["median"], 1),
                decimal_id(values["mean"], 2),
                decimal_id(values["p75"], 1),
                values["max"],
            ]
        )

    category_order = (
        "Energi/kkal",
        "Persentase",
        "Nilai laboratorium",
        "Antropometri/z-score",
        "Berat/tinggi badan",
        "Kode PES",
        "Lainnya",
    )
    category_rows = [
        [
            label,
            category_tokens[label],
            answers_by_category[label],
            examples.get(label, "Tidak ditemukan"),
        ]
        for label in category_order
    ]

    report = f"""# Tahap 1 — Analisis Eksploratif Data

## Ruang lingkup dan prinsip

Analisis ini membaca data mentah secara *read-only*. Tidak ada split, data
olahan, atau perubahan label yang dibuat pada tahap ini. Seluruh statistik angka
bersifat eksploratif; parser angka tervalidasi, pengecualian nomor daftar/halaman,
dan keputusan normalisasi final baru ditetapkan pada Tahap 3.

- Seed contoh: `{RANDOM_SEED}`.
- SHA-256 `dataset.json`: `{sha256(DATASET_PATH)}`.
- SHA-256 manifest 120 file chunk: `{chunk_manifest_sha256(chunk_paths)}`.

## Statistik umum

| Ukuran | Nilai |
| --- | ---: |
| QA mentah | {len(rows)} |
| ID QA unik | {len({row['id'] for row in rows})} |
| Dokumen pada QA | {len(raw_names)} |
| File chunk | {len(chunk_paths)} |
| Total chunk | {len(all_chunks)} |
| Chunk per dokumen, minimum–rata-rata–maksimum | {min(chunks_per_document)}–{decimal_id(mean(chunks_per_document), 2)}–{max(chunks_per_document)} |
| Template pertanyaan unik setelah normalisasi spasi/case | {unique_question_templates} |

Semua QA memiliki sepuluh field yang diharapkan dan tidak ada nilai wajib yang
kosong (`missing-field rows = {missing_field_rows}`; `empty/null values =
{empty_required_values}`). Semua 120 file chunk berupa list dengan total 13.737
record dan keyset konsisten: `{', '.join(next(iter(chunk_keysets)))}`.

### Distribusi tipe pertanyaan

{markdown_table(['Tipe', 'QA mentah', 'Setelah dedup eksploratif', 'Memuat angka biasa', 'Memuat angka ≥2 digit'], type_rows)}

![Distribusi tipe pertanyaan](figures/01_question_types.png)

Pemetaan di atas bersifat deterministik karena data hanya memiliki delapan teks
pertanyaan unik. Label permanen akan ditulis ke data olahan pada Tahap 2.

### Panjang teks

{markdown_table(['Komponen', 'Min', 'P25', 'Median', 'Rata-rata', 'P75', 'Maks'], length_rows)}

## Audit kualitas data

### Rekonsiliasi dokumen dan chunk

- Nama mentah yang langsung cocok: **{raw_filename_matches}/{len(raw_names)}**.
- Nama yang cocok setelah NFKC, konversi `#Uxxxx`, dan penghapusan U+2060:
  **{normalized_filename_matches}/{len(normalized_qa_names)}**.
- Nama yang memuat `#Uxxxx`: **{hash_u_names}**; nama yang memuat U+2060:
  **{word_joiner_names}**. Snapshot ini sudah memakai nama Unicode yang sama di
  dataset dan disk, tetapi satu nama masih mengandung U+2060 pada kedua sisi.
- Join unik berdasarkan `(file, page_number, chunk_index)` berhasil untuk
  **{page_index_joined}/{len(rows)}** QA dan tidak ada kunci ambigu
  (`{ambiguous_page_index}`).
- Isi `context` sama persis dengan teks chunk pada **{exact_context_joined}/{len(rows)}**
  QA; **{len(rows) - exact_context_joined}** QA memiliki perbedaan teks walaupun
  kunci chunk cocok. Tahap 2 harus menetapkan sumber konteks kanonik.

### Duplikasi

Terdapat **{len(duplicate_groups)}** kelompok duplikat `(file, question)`:
{duplicate_multiplicity[2]} kelompok berisi dua baris dan
{duplicate_multiplicity[3]} kelompok berisi tiga baris. Ini menghasilkan
**{duplicate_extra_rows}** baris berlebih, sehingga ukuran setelah deduplikasi
eksploratif *keep-first* adalah **{len(deduplicated_rows)} QA**.

Hanya **{duplicate_same_answer}/{len(duplicate_groups)}** kelompok memiliki
jawaban identik dan **{duplicate_same_context}/{len(duplicate_groups)}** memiliki
konteks identik. Karena mayoritas duplikat berbeda isi, *keep-first* di sini
hanya dipakai untuk menghitung ukuran sementara; aturan deduplikasi formal harus
didokumentasikan pada Tahap 2.

### `answer_start`

Dari {total_answer_spans} span jawaban, hanya **{valid_answer_starts}
({pct(valid_answer_starts, total_answer_spans)})** yang cocok tepat dengan
`context`; **{total_answer_spans - valid_answer_starts}** tidak cocok. Field ini
tidak layak digunakan sebagai lokasi jawaban, sesuai masalah data yang telah
diantisipasi.

## Fokus angka

### Definisi eksploratif

Parser sementara mengenali bilangan bulat, desimal titik/koma, pemisah ribuan
titik, tanda negatif, persen, dan kedua ujung rentang. Kode PES dimask dari
angka biasa dan dihitung terpisah. Ambiguitas seperti `1.500` sementara dianggap
ribuan, sedangkan `1.5` dianggap desimal; pengecualian nomor daftar, nomor
halaman, tahun sitasi, dan nomor bagian belum final.

- **{answers_with_number}/{len(rows)} ({pct(answers_with_number, len(rows))})**
  jawaban memuat sedikitnya satu angka biasa.
- **{answers_with_two_digit_number}/{len(rows)}
  ({pct(answers_with_two_digit_number, len(rows))})** memuat token angka biasa
  dengan sedikitnya dua digit setelah kode PES dimask.
- Regex mentah `\\d{{2,}}` tanpa parsing menemukan **{raw_two_digit_regex_count}**
  jawaban. Tidak satu pun definisi eksploratif ini mereplikasi angka pendahuluan
  413 secara persis; perbedaan definisi akan diaudit pada Tahap 3, bukan
  disesuaikan agar cocok dengan target.
- Total angka biasa yang terdeteksi: **{sum(numeric_counts)}**; rata-rata seluruh
  QA **{decimal_id(mean(numeric_counts), 2)}**, median **{decimal_id(median(numeric_counts), 1)}**,
  dan maksimum **{max(numeric_counts)}**. Di antara jawaban yang berangka,
  rata-ratanya **{decimal_id(mean(positive_numeric_counts), 2)}** angka.
- Jawaban diagnosis PES dengan kode: **{pes_diagnosis_with_code}/{len(pes_diagnosis_rows)}
  ({pct(pes_diagnosis_with_code, len(pes_diagnosis_rows))})**.

![Proporsi jawaban berangka](figures/01_numeric_by_type.png)

### Kategori angka

Kategori ditetapkan dengan aturan konteks lokal dan dapat muncul bersama dalam
satu jawaban. `Lainnya` mencakup usia, waktu, volume, gram zat gizi, rasio, tahun,
dan angka yang belum dapat diklasifikasikan dengan aman.

{markdown_table(['Kategori', 'Token/kode', 'Jawaban', 'Contoh pendek (seed 42)'], category_rows)}

![Kategori angka](figures/01_number_categories.png)

Contoh hanya berupa fragmen pendek dari jawaban gold dan tidak memuat nama atau
identitas pasien. Pemilihan contoh dilakukan otomatis dengan seed 42 dari semua
fragmen yang cocok dengan pola berpresisi tinggi.

### Cakupan angka gold

Dengan toleransi sementara selisih absolut ≤0,01 atau relatif ≤0,5%:

| Ukuran | Hasil |
| --- | ---: |
| Kemunculan angka gold yang ada di seluruh laporan | {report_number_hits}/{total_gold_numbers} ({pct(report_number_hits, total_gold_numbers)}) |
| Kemunculan angka gold yang ada di chunk gold | {chunk_number_hits}/{total_gold_numbers} ({pct(chunk_number_hits, total_gold_numbers)}) |
| Jawaban berangka yang seluruh angkanya ada di laporan | {all_numbers_in_report}/{numbered_answers} ({pct(all_numbers_in_report, numbered_answers)}) |
| Jawaban berangka yang seluruh angkanya ada di chunk gold | {all_numbers_in_chunk}/{numbered_answers} ({pct(all_numbers_in_chunk, numbered_answers)}) |

Hasil laporan (**{pct(report_number_hits, total_gold_numbers)}** dan
**{pct(all_numbers_in_report, numbered_answers)}**) konsisten dengan temuan
pendahuluan sekitar 99% dan 98%. Cakupan chunk gold
**{pct(chunk_number_hits, total_gold_numbers)}** lebih rendah daripada perkiraan
awal sekitar 76% sebesar
{decimal_id(76 - 100 * chunk_number_hits / total_gold_numbers, 2)} poin
persentase. Kemungkinan penyebabnya meliputi definisi angka, perlakuan kode PES,
angka daftar/sitasi, dan 12 ketidaksesuaian konteks; semuanya harus diuji dengan
unit test dan audit contoh pada Tahap 3.

## Implikasi untuk tahap berikutnya

1. Seluruh dokumen dapat direkonsiliasi, tetapi nama tetap harus dinormalisasi
   agar U+2060 tidak menjadi identitas dokumen berbeda.
2. Deduplikasi tidak boleh diasumsikan sebagai salinan identik karena 31 dari 35
   kelompok mempunyai jawaban berbeda.
3. `answer_start` tidak digunakan pada pipeline.
4. Angka gold hampir selalu tersedia di laporan penuh, sedangkan banyak tidak
   tersedia di chunk gold; ini mendukung pengujian retrieval verifikasi tambahan.
5. Semua hasil angka pada bab ini bersifat eksploratif dan tidak menggantikan
   validasi Tahap 3.
"""

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(report, encoding="utf-8")
    print(f"QA_COUNT={len(rows)}")
    print(f"DOCUMENT_COUNT={len(raw_names)}")
    print(f"CHUNK_COUNT={len(all_chunks)}")
    print(f"DEDUP_PREVIEW_COUNT={len(deduplicated_rows)}")
    print(f"ANSWERS_WITH_NUMBER={answers_with_number}")
    print(f"REPORT_NUMBER_COVERAGE={report_number_hits / total_gold_numbers:.6f}")
    print(f"CHUNK_NUMBER_COVERAGE={chunk_number_hits / total_gold_numbers:.6f}")
    print(f"REPORT={REPORT_PATH.relative_to(ROOT)}")
    print("FIGURES=3")


if __name__ == "__main__":
    main()
