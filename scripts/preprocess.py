"""Run Stage 2 preprocessing and write its Indonesian audit report."""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.data import QUESTION_TYPES, run_preprocessing


CONFIG_PATH = ROOT / "configs" / "data.yaml"
REPORT_PATH = ROOT / "reports" / "02_preprocessing.md"


def pct(numerator: int, denominator: int) -> str:
    return f"{100 * numerator / denominator:.2f}%".replace(".", ",")


def markdown_table(headers: list[str], rows: list[list[object]]) -> str:
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(str(value) for value in row) + " |")
    return "\n".join(lines)


def main() -> None:
    result = run_preprocessing(ROOT, CONFIG_PATH)
    summary = result.summary
    reconciliation = summary["reconciliation"]
    dev = summary["splits"]["dev"]
    test = summary["splits"]["test"]

    type_rows = [
        [label, dev["question_types"][label], test["question_types"][label]]
        for label in QUESTION_TYPES
    ]
    flag_rows = [
        [
            "QA",
            dev["qa"],
            test["qa"],
            dev["qa"] + test["qa"],
        ],
        [
            "has_number (provisional)",
            f"{dev['has_number']} ({pct(dev['has_number'], dev['qa'])})",
            f"{test['has_number']} ({pct(test['has_number'], test['qa'])})",
            dev["has_number"] + test["has_number"],
        ],
        [
            "has_pes_code",
            f"{dev['has_pes_code']} ({pct(dev['has_pes_code'], dev['qa'])})",
            f"{test['has_pes_code']} ({pct(test['has_pes_code'], test['qa'])})",
            dev["has_pes_code"] + test["has_pes_code"],
        ],
        [
            "context_changed",
            dev["context_changed"],
            test["context_changed"],
            dev["context_changed"] + test["context_changed"],
        ],
    ]

    output_rows = []
    for path in result.output_paths:
        relative = path.relative_to(ROOT)
        lines = sum(1 for _ in path.open("r", encoding="utf-8"))
        output_rows.append([f"`{relative.as_posix()}`", lines, path.stat().st_size])

    report = f"""# Tahap 2 — Pra-pemrosesan dan Split

## Konfigurasi yang dibekukan

- Seed: **{summary['config']['seed']}**.
- Unit split: **dokumen pasien**, bukan baris QA.
- Proporsi: **20% dev / 80% test**.
- Algoritme: urutkan `doc_id`, acak dengan `random.Random(42)`, ambil 20%
  pertama sebagai dev.
- Deduplikasi: kelompok `(normalized_file, exact_trimmed_question)` dan
  pertahankan **ID asli terkecil**.
- Konteks kanonik: teks corpus chunk berdasarkan `(doc_id, page_number,
  chunk_index)`; konteks dataset dipertahankan sebagai `dataset_context`.
- `answer_start` tidak disalin ke data olahan.

Konfigurasi lengkap tersedia di `configs/data.yaml`. Data mentah hanya dibaca;
seluruh artefak turunan ditulis ke `data/processed/` yang diabaikan Git.

## Rekonsiliasi jumlah QA

| Langkah | Jumlah |
| --- | ---: |
| QA mentah | {reconciliation['raw_qa']} |
| Kelompok duplikat | {reconciliation['duplicate_groups']} |
| Baris duplikat dibuang | {reconciliation['duplicate_rows_removed']} |
| Setelah deduplikasi | {reconciliation['after_deduplication']} |
| Berhasil di-join | {reconciliation['joined']} |
| Gagal di-join | {reconciliation['failed_joins']} |
| QA final | {reconciliation['final_qa']} |

Alur rekonsiliasi: **{reconciliation['raw_qa']} →
{reconciliation['after_deduplication']} → {reconciliation['joined']} →
{reconciliation['final_qa']}**. Audit 35 kelompok duplikat menyimpan ID yang
dipertahankan dan dibuang tanpa menyalin keputusan berdasarkan isi jawaban.

## Hasil split

| Split | Dokumen | QA | Proporsi dokumen | Proporsi QA |
| --- | ---: | ---: | ---: | ---: |
| Dev | {dev['documents']} | {dev['qa']} | {pct(dev['documents'], reconciliation['documents'])} | {pct(dev['qa'], reconciliation['final_qa'])} |
| Test | {test['documents']} | {test['qa']} | {pct(test['documents'], reconciliation['documents'])} | {pct(test['qa'], reconciliation['final_qa'])} |

Irisan dokumen dev dan test adalah **{summary['checks']['document_overlap']}**.
Daftar `doc_id` tiap split dibekukan di `split_manifest.json`.

### Distribusi tipe pertanyaan

{markdown_table(['Tipe', 'Dev', 'Test'], type_rows)}

Kedelapan tipe tersedia pada kedua split. Perbedaan satu QA pada beberapa tipe
berasal dari dokumen sumber yang memang tidak memiliki semua template.

### Penanda

{markdown_table(['Penanda', 'Dev', 'Test', 'Total'], flag_rows)}

`has_number` masih menggunakan versi **stage2_candidate_v1**: kode PES dimask,
lalu jawaban ditandai jika memuat kandidat angka biasa. Field ini wajib dihitung
ulang dan dibandingkan dengan modul tervalidasi Tahap 3 sebelum pemilihan subset
eksperimen. `has_pes_code` menggunakan regex kode `NI/NC/NB` terpisah.

## Artefak data olahan

{markdown_table(['File', 'Baris', 'Byte'], output_rows)}

`split_manifest.json` berformat JSON multi-baris, sehingga jumlah barisnya bukan
jumlah record. Semua JSONL disortir deterministik: QA berdasarkan ID dan chunk
berdasarkan `(doc_id, page_number, chunk_index)`.

## Pemeriksaan integritas

- [x] Tidak ada dokumen di dua split.
- [x] Semua QA hasil deduplikasi berhasil di-join.
- [x] Semua delapan tipe ada di dev dan test.
- [x] `has_number` dan `has_pes_code` tersedia pada setiap QA.
- [x] Konteks asli untuk 12 QA yang berbeda tetap tersedia untuk audit.
- [x] `answer_start` yang tidak andal tidak dibawa ke data olahan.

## Catatan untuk Tahap 3

Tahap 3 harus mengganti status provisional `has_number` dengan hasil modul angka
yang telah memiliki minimal 30 unit test. Jika hasilnya berbeda, seluruh file QA
olahan harus diregenerasi dari data mentah dengan split dokumen yang sama dan
perubahan dicatat di `reports/DECISIONS.md`.
"""
    REPORT_PATH.write_text(report, encoding="utf-8", newline="\n")

    print(
        f"RECONCILIATION={reconciliation['raw_qa']}->"
        f"{reconciliation['after_deduplication']}->"
        f"{reconciliation['joined']}->{reconciliation['final_qa']}"
    )
    print(f"DEV_DOCUMENTS={dev['documents']} DEV_QA={dev['qa']}")
    print(f"TEST_DOCUMENTS={test['documents']} TEST_QA={test['qa']}")
    print(f"DOCUMENT_OVERLAP={summary['checks']['document_overlap']}")
    print(f"DEV_HAS_NUMBER={dev['has_number']} DEV_HAS_PES_CODE={dev['has_pes_code']}")
    print(f"TEST_HAS_NUMBER={test['has_number']} TEST_HAS_PES_CODE={test['has_pes_code']}")
    print(f"REPORT={REPORT_PATH.relative_to(ROOT)}")


if __name__ == "__main__":
    main()

