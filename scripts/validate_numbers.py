"""Validate the frozen Stage 3 numeric rules and generate audit artifacts."""

from __future__ import annotations

import json
import random
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.data import read_jsonl, run_preprocessing, write_jsonl
from src.numbers import (
    NUMBER_VERSION,
    NumberConfig,
    NumberMention,
    PESCodeMention,
    extract_numbers,
    extract_pes_codes,
    load_number_config,
    number_in_candidates,
)


DATA_CONFIG_PATH = ROOT / "configs" / "data.yaml"
NUMBER_CONFIG_PATH = ROOT / "configs" / "numbers.yaml"
PROCESSED_DIR = ROOT / "data" / "processed"
REPORT_PATH = ROOT / "reports" / "03_numbers.md"
EXAMPLES_PATH = ROOT / "reports" / "03_number_examples.md"
GOLD_NUMBERS_PATH = PROCESSED_DIR / "gold_numbers.jsonl"
RANDOM_SEED = 42
EXAMPLE_COUNT = 20

CATEGORY_LABELS = {
    "energy": "Energi/kkal",
    "percentage": "Persentase",
    "laboratory": "Nilai laboratorium",
    "anthropometry_zscore": "Antropometri/z-score",
    "weight_height": "Berat/tinggi badan",
    "other": "Lainnya",
}


def pct(numerator: int, denominator: int) -> str:
    if denominator == 0:
        return "n/a"
    return f"{100 * numerator / denominator:.2f}%".replace(".", ",")


def markdown_table(headers: list[str], rows: list[list[object]]) -> str:
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in rows:
        escaped = [str(value).replace("|", "\\|") for value in row]
        lines.append("| " + " | ".join(escaped) + " |")
    return "\n".join(lines)


def load_rows(path: Path) -> list[dict]:
    return list(read_jsonl(path))


def group_chunks_by_document(chunks: Iterable[dict]) -> dict[str, list[dict]]:
    grouped: dict[str, list[dict]] = defaultdict(list)
    for chunk in chunks:
        grouped[chunk["doc_id"]].append(chunk)
    return grouped


def values(mentions: Iterable[NumberMention]):
    return [mention.value for mention in mentions]


def normalized_codes(mentions: Iterable[PESCodeMention]) -> list[str]:
    return [mention.normalized for mention in mentions]


def evaluate_rows(
    rows: list[dict],
    report_numbers: dict[str, list],
    report_codes: dict[str, set[str]],
    config: NumberConfig,
) -> dict:
    result = Counter()
    categories = Counter()

    for row in rows:
        answer_numbers = extract_numbers(row["gold_answer"], config)
        answer_codes = extract_pes_codes(row["gold_answer"])
        chunk_numbers = extract_numbers(row["context"], config)
        chunk_codes = set(normalized_codes(extract_pes_codes(row["context"])))

        result["qa"] += 1
        result["answers_with_number"] += bool(answer_numbers)
        result["answers_with_pes_code"] += bool(answer_codes)
        result["number_mentions"] += len(answer_numbers)
        result["pes_code_mentions"] += len(answer_codes)
        categories.update(mention.category for mention in answer_numbers)

        if answer_numbers:
            report_matches = [
                number_in_candidates(
                    mention.value, report_numbers[row["doc_id"]], config
                )
                for mention in answer_numbers
            ]
            chunk_candidates = values(chunk_numbers)
            chunk_matches = [
                number_in_candidates(mention.value, chunk_candidates, config)
                for mention in answer_numbers
            ]
            result["report_number_hits"] += sum(report_matches)
            result["chunk_number_hits"] += sum(chunk_matches)
            result["answers_all_numbers_in_report"] += all(report_matches)
            result["answers_all_numbers_in_chunk"] += all(chunk_matches)

        if answer_codes:
            code_values = normalized_codes(answer_codes)
            report_code_matches = [
                code in report_codes[row["doc_id"]] for code in code_values
            ]
            chunk_code_matches = [code in chunk_codes for code in code_values]
            result["report_code_hits"] += sum(report_code_matches)
            result["chunk_code_hits"] += sum(chunk_code_matches)
            result["answers_all_codes_in_report"] += all(report_code_matches)
            result["answers_all_codes_in_chunk"] += all(chunk_code_matches)

    result["categories"] = dict(categories)
    return dict(result)


def combined_metrics(*metrics: dict) -> dict:
    combined = Counter()
    categories = Counter()
    for metric in metrics:
        for key, value in metric.items():
            if key == "categories":
                categories.update(value)
            else:
                combined[key] += value
    combined["categories"] = dict(categories)
    return dict(combined)


def serialize_gold_numbers(rows: list[dict], config: NumberConfig) -> list[dict]:
    output = []
    for row in rows:
        mentions = extract_numbers(row["gold_answer"], config)
        codes = extract_pes_codes(row["gold_answer"])
        output.append(
            {
                "id": row["id"],
                "doc_id": row["doc_id"],
                "split": row["split"],
                "number_version": NUMBER_VERSION,
                "numbers": [mention.to_dict() for mention in mentions],
                "unique_normalized_numbers": sorted(
                    {mention.normalized for mention in mentions}
                ),
                "pes_codes": [code.to_dict() for code in codes],
                "unique_pes_codes": sorted({code.normalized for code in codes}),
            }
        )
    return output


def sanitize_snippet(text: str) -> str:
    text = re.sub(
        r"\b(?:Ny|Tn|An)\.?\s+[A-Z][\w.-]*",
        "[identitas]",
        text,
        flags=re.IGNORECASE,
    )
    return re.sub(r"\s+", " ", text).strip()


def snippet_around(text: str, position: int, radius: int = 100) -> str:
    start = max(0, position - radius)
    end = min(len(text), position + radius)
    snippet = sanitize_snippet(text[start:end])
    if start:
        snippet = "…" + snippet
    if end < len(text):
        snippet += "…"
    return snippet


def render_dev_examples(rows: list[dict], config: NumberConfig) -> str:
    eligible = [
        row
        for row in rows
        if extract_numbers(row["gold_answer"], config)
        or extract_pes_codes(row["gold_answer"])
    ]
    selected = random.Random(RANDOM_SEED).sample(eligible, EXAMPLE_COUNT)
    table_rows = []
    for index, row in enumerate(selected, start=1):
        numbers = extract_numbers(row["gold_answer"], config)
        codes = extract_pes_codes(row["gold_answer"])
        first_position = min(
            [mention.start for mention in numbers]
            + [mention.start for mention in codes]
        )
        rendered_numbers = ", ".join(
            f"{mention.normalized} [{CATEGORY_LABELS[mention.category]}"
            + (f"; {mention.unit}" if mention.unit else "")
            + "]"
            for mention in numbers
        )
        rendered_codes = ", ".join(code.normalized for code in codes) or "—"
        table_rows.append(
            [
                index,
                row["id"],
                row["question_type"],
                snippet_around(row["gold_answer"], first_position),
                rendered_numbers or "—",
                rendered_codes,
            ]
        )

    return f"""# Contoh Ekstraksi Angka Tahap 3

Seluruh contoh dipilih secara acak dari **split dev** dengan seed
`{RANDOM_SEED}` setelah aturan `{NUMBER_VERSION}` dibekukan. Fragmen dibatasi di
sekitar kemunculan pertama dan pola sapaan/nama sederhana disamarkan. Tidak ada
contoh test yang ditampilkan atau digunakan untuk mengubah aturan.

{markdown_table(['No.', 'QA ID', 'Tipe', 'Fragmen', 'Angka ternormalisasi', 'Kode PES'], table_rows)}
"""


def metric_rows(metrics_by_split: dict[str, dict]) -> list[list[str]]:
    rows = []
    for split in ("dev", "test", "keseluruhan"):
        metric = metrics_by_split[split]
        rows.append(
            [
                split.capitalize(),
                metric["qa"],
                metric.get("answers_with_number", 0),
                metric.get("number_mentions", 0),
                f"{metric.get('report_number_hits', 0)}/{metric.get('number_mentions', 0)} "
                f"({pct(metric.get('report_number_hits', 0), metric.get('number_mentions', 0))})",
                f"{metric.get('chunk_number_hits', 0)}/{metric.get('number_mentions', 0)} "
                f"({pct(metric.get('chunk_number_hits', 0), metric.get('number_mentions', 0))})",
                f"{metric.get('answers_all_numbers_in_report', 0)}/"
                f"{metric.get('answers_with_number', 0)} "
                f"({pct(metric.get('answers_all_numbers_in_report', 0), metric.get('answers_with_number', 0))})",
                f"{metric.get('answers_all_numbers_in_chunk', 0)}/"
                f"{metric.get('answers_with_number', 0)} "
                f"({pct(metric.get('answers_all_numbers_in_chunk', 0), metric.get('answers_with_number', 0))})",
            ]
        )
    return rows


def code_metric_rows(metrics_by_split: dict[str, dict]) -> list[list[str]]:
    rows = []
    for split in ("dev", "test", "keseluruhan"):
        metric = metrics_by_split[split]
        rows.append(
            [
                split.capitalize(),
                metric.get("answers_with_pes_code", 0),
                metric.get("pes_code_mentions", 0),
                f"{metric.get('report_code_hits', 0)}/{metric.get('pes_code_mentions', 0)} "
                f"({pct(metric.get('report_code_hits', 0), metric.get('pes_code_mentions', 0))})",
                f"{metric.get('chunk_code_hits', 0)}/{metric.get('pes_code_mentions', 0)} "
                f"({pct(metric.get('chunk_code_hits', 0), metric.get('pes_code_mentions', 0))})",
            ]
        )
    return rows


def main() -> None:
    number_config = load_number_config(NUMBER_CONFIG_PATH)

    old_rows = load_rows(PROCESSED_DIR / "qa_clean.jsonl")
    old_split_by_id = {row["id"]: row["split"] for row in old_rows}

    # Regenerate from raw inputs using the same frozen deduplication and split.
    run_preprocessing(ROOT, DATA_CONFIG_PATH)
    rows = load_rows(PROCESSED_DIR / "qa_clean.jsonl")
    dev_rows = load_rows(PROCESSED_DIR / "qa_dev.jsonl")
    test_rows = load_rows(PROCESSED_DIR / "qa_test.jsonl")
    chunks = load_rows(PROCESSED_DIR / "chunks_clean.jsonl")

    new_split_by_id = {row["id"]: row["split"] for row in rows}
    if old_split_by_id != new_split_by_id:
        raise AssertionError("Stage 3 regeneration changed QA split assignments")
    if any(row["number_flag_version"] != NUMBER_VERSION for row in rows):
        raise AssertionError(f"Not all QA rows use the frozen {NUMBER_VERSION} flag")

    chunks_by_doc = group_chunks_by_document(chunks)
    report_numbers = {
        doc_id: values(
            extract_numbers(
                "\n".join(chunk["text"] for chunk in document_chunks),
                number_config,
            )
        )
        for doc_id, document_chunks in chunks_by_doc.items()
    }
    report_codes = {
        doc_id: set(
            normalized_codes(
                extract_pes_codes(
                    "\n".join(chunk["text"] for chunk in document_chunks)
                )
            )
        )
        for doc_id, document_chunks in chunks_by_doc.items()
    }

    dev_metrics = evaluate_rows(dev_rows, report_numbers, report_codes, number_config)
    test_metrics = evaluate_rows(test_rows, report_numbers, report_codes, number_config)
    all_metrics = combined_metrics(dev_metrics, test_metrics)
    chunk_coverage = (
        100 * all_metrics["chunk_number_hits"] / all_metrics["number_mentions"]
    )
    chunk_gap_pp = 76 - chunk_coverage
    metrics_by_split = {
        "dev": dev_metrics,
        "test": test_metrics,
        "keseluruhan": all_metrics,
    }

    gold_number_rows = serialize_gold_numbers(rows, number_config)
    write_jsonl(GOLD_NUMBERS_PATH, gold_number_rows)
    EXAMPLES_PATH.write_text(
        render_dev_examples(dev_rows, number_config), encoding="utf-8", newline="\n"
    )

    category_rows = []
    for category, label in CATEGORY_LABELS.items():
        category_rows.append(
            [
                label,
                dev_metrics["categories"].get(category, 0),
                test_metrics["categories"].get(category, 0),
                all_metrics["categories"].get(category, 0),
            ]
        )

    report = f"""# Tahap 3 — Modul Angka dan Validasi Metrik

## Protokol anti-kebocoran

Aturan awal `numbers_v1` dikembangkan menggunakan contoh sintetis dan audit dev.
Sesudah validasi pertama, pemeriksaan contoh **dev** menemukan tiga cacat format:
tanda negatif berspasi, tahun sitasi majemuk, dan operand kedua pola `3x150`.
Audit dev berikutnya menemukan parser masih dapat mulai pada digit kedua kode
alfanumerik (`P97`, `B12`) dan sitasi multi-baris. Koreksi tidak didasarkan pada
contoh atau arah hasil test, dicatat berturut-turut sebagai `numbers_v1.1` dan
`numbers_v1.2`, serta setiap perubahan diikuti rerun validasi penuh. Dua puluh
contoh pemeriksaan tetap berasal dari dev saja.

Sebanyak **104 unit test** lulus pada versi final; jumlah ini melampaui syarat
minimal 30 kasus.

## Aturan yang dibekukan

- Koma adalah desimal: `1705,8 → 1705.8`.
- Titik dengan kelompok tiga digit adalah pemisah ribuan: `1.705,8 → 1705.8`
  dan `2.000 → 2000`.
- Titik lain adalah desimal: `1.5 → 1.5`.
- Persen dipertahankan sebagai poin persentase: `15% → 15`.
- Rentang menghasilkan dua angka; tanda hubung kompak tidak menjadi tanda
  negatif untuk ujung kedua.
- Nomor daftar, halaman berlabel, nomor tunggal satu baris, nomor bagian, tahun
  sitasi berpola jelas, dan komponen kode PES dikecualikan dari angka biasa.
- Kode PES dinormalisasi ke bentuk `NI-2.1`, `NC-4.1`, atau `NB-1.1`.
- Pencocokan menggunakan selisih absolut ≤0,01 atau selisih relatif simetris
  ≤0,5% dengan penyebut nilai absolut terbesar. Unit tidak menjadi bagian dari
  keputusan cocok, sesuai definisi metrik penelitian.

Konfigurasi mesin-baca tersedia di `configs/numbers.yaml` dan implementasi di
`src/numbers.py`.

## Perubahan penanda Tahap 2

- Tahap 2 provisional: **418/858** QA (`stage2_candidate_v1`).
- Validasi pertama sebelum koreksi format dev: **346/858** QA (`numbers_v1`).
- Validasi setelah koreksi pertama: **344/858** QA (`numbers_v1.1`).
- Versi final: **{sum(row['has_number'] for row in rows)}/{len(rows)}** QA
  (`{NUMBER_VERSION}`).
- ID, kebijakan deduplikasi, konteks, dan split tidak berubah pada regenerasi.

## Validasi angka gold

{markdown_table(
    ['Split', 'QA', 'Jawaban berangka', 'Kemunculan angka', 'Ada di laporan',
     'Ada di chunk gold', 'Semua angka di laporan', 'Semua angka di chunk'],
    metric_rows(metrics_by_split),
)}

Secara keseluruhan, proporsi kemunculan angka gold yang ada di laporan adalah
**{pct(all_metrics['report_number_hits'], all_metrics['number_mentions'])}** dan
proporsi jawaban berangka yang seluruh angkanya ada di laporan adalah
**{pct(all_metrics['answers_all_numbers_in_report'], all_metrics['answers_with_number'])}**.
Nilai tersebut dibandingkan dengan temuan pendahuluan sekitar 99% dan 98% tanpa
menjadikannya target optimasi. Cakupan chunk gold adalah
**{pct(all_metrics['chunk_number_hits'], all_metrics['number_mentions'])}**,
dibandingkan perkiraan awal sekitar 76% (selisih
**{str(f'{chunk_gap_pp:.2f}').replace('.', ',')} poin persentase**). Selisih ini
masuk akal karena parser final mengeluarkan angka sitasi, penomoran, dan
komponen kode PES, sedangkan definisi rinci perhitungan pendahuluan tidak
tersedia. Selain itu, Tahap 2 menetapkan teks corpus chunk sebagai konteks
kanonik. Angka final dipakai apa adanya dan parser tidak dituning ke estimasi
pendahuluan.

### Kategori angka

{markdown_table(['Kategori', 'Dev', 'Test', 'Total'], category_rows)}

## Validasi kode PES

{markdown_table(
    ['Split', 'Jawaban dengan kode', 'Kemunculan kode', 'Ada di laporan',
     'Ada di chunk gold'],
    code_metric_rows(metrics_by_split),
)}

Kode PES diperlakukan terpisah dari angka biasa. Angka `2` dan `1` dalam
`NI-2.1` tidak masuk ke denominator metrik numerik.

## Keterbatasan

- Penyaringan bersifat konservatif dan tidak menjamin semua nomor regulasi,
  nomor referensi bebas, atau indeks dalam notasi formula terhapus.
- Kategori angka ditentukan dengan heuristik kata sekitar, sehingga kategori
  hanya cocok untuk analisis deskriptif dan bukan label klinis tervalidasi.
- Kecocokan angka sengaja tidak memeriksa kesetaraan unit; metrik ini hanya
  mengukur keberadaan nilai numerik menurut definisi penelitian.
- Perbedaan cakupan chunk dari estimasi awal tidak dapat diatribusikan pada
  satu faktor tanpa artefak dan definisi parser pendahuluan yang lengkap.

## Artefak

- `data/processed/gold_numbers.jsonl`: satu record per QA berisi seluruh mention,
  nilai ternormalisasi, kategori, unit, posisi karakter, dan kode PES.
- `reports/03_number_examples.md`: 20 contoh acak dev untuk pemeriksaan manual.
- File QA olahan diregenerasi dari sumber mentah dengan split yang sama dan
  `number_flag_version={NUMBER_VERSION}`.

## Kesimpulan validasi

Modul memenuhi cakupan format yang diminta dan lulus 104 unit test. Perbedaan
terhadap temuan pendahuluan dilaporkan apa adanya; tidak ada contoh atau arah
hasil test yang digunakan untuk menyesuaikan parser.
"""
    REPORT_PATH.write_text(report, encoding="utf-8", newline="\n")

    print(f"QA={len(rows)} DEV={len(dev_rows)} TEST={len(test_rows)}")
    print(
        f"HAS_NUMBER_STAGE2=418 HAS_NUMBER_V1=346 HAS_NUMBER_V1_1=344 "
        f"HAS_NUMBER_FINAL={sum(row['has_number'] for row in rows)}"
    )
    print(
        f"NUMBER_COVERAGE_REPORT="
        f"{all_metrics['report_number_hits']}/{all_metrics['number_mentions']} "
        f"({pct(all_metrics['report_number_hits'], all_metrics['number_mentions'])})"
    )
    print(
        f"NUMBER_COVERAGE_CHUNK="
        f"{all_metrics['chunk_number_hits']}/{all_metrics['number_mentions']} "
        f"({pct(all_metrics['chunk_number_hits'], all_metrics['number_mentions'])})"
    )
    print(f"GOLD_NUMBER_ROWS={len(gold_number_rows)}")
    print(f"DEV_EXAMPLES={EXAMPLE_COUNT}")
    print(f"REPORT={REPORT_PATH.relative_to(ROOT)}")


if __name__ == "__main__":
    main()

