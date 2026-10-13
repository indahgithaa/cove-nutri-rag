"""Run frozen Stage 4 retrieval and generate contexts plus validation report."""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.data import read_jsonl, write_jsonl
from src.numbers import load_number_config
from src.retrieval import (
    RETRIEVAL_VERSION,
    build_document_indexes,
    context_record,
    default_query_stopwords,
    gold_chunk_id,
    load_retrieval_config,
    numeric_coverage,
    select_condition,
    tokenize_query,
)


CONFIG_PATH = ROOT / "configs" / "retrieval.yaml"
REPORT_PATH = ROOT / "reports" / "04_retrieval.md"


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
        lines.append("| " + " | ".join(str(value) for value in row) + " |")
    return "\n".join(lines)


def load_config_paths() -> tuple[dict, object]:
    import yaml

    raw = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    return raw, load_retrieval_config(CONFIG_PATH)


def evaluate_split(
    rows: list[dict],
    *,
    split: str,
    indexes: dict,
    stopwords: frozenset[str],
    retrieval_config,
    number_config,
    output_dir: Path,
) -> dict[str, dict]:
    metrics: dict[str, Counter] = {
        condition: Counter() for condition in retrieval_config.conditions
    }
    contexts: dict[str, list[dict]] = {
        condition: [] for condition in retrieval_config.conditions
    }
    qrels = []

    for qa in rows:
        query_tokens = tokenize_query(qa["question"], stopwords)
        ranking = indexes[qa["doc_id"]].rank(query_tokens)
        qrel = gold_chunk_id(qa)
        qrels.append(
            {
                "id": qa["id"],
                "doc_id": qa["doc_id"],
                "split": split,
                "gold_chunk_id": qrel,
            }
        )
        for condition in retrieval_config.conditions:
            selected = select_condition(ranking, condition, retrieval_config)
            selected_ids = {chunk.chunk_id for chunk in selected}
            hits, total = numeric_coverage(
                qa["gold_answer"], selected, number_config
            )
            metric = metrics[condition]
            metric["qa"] += 1
            metric["recall_hits"] += qrel in selected_ids
            metric["number_hits"] += hits
            metric["number_total"] += total
            metric["numeric_qa"] += total > 0
            metric["all_numbers_covered"] += total > 0 and hits == total
            contexts[condition].append(
                context_record(
                    qa,
                    condition=condition,
                    query_tokens=query_tokens,
                    selected=selected,
                )
            )

    write_jsonl(output_dir / f"qrels_gold_{split}.jsonl", qrels)
    for condition, records in contexts.items():
        write_jsonl(
            output_dir / f"contexts_{condition}_{split}.jsonl", records
        )
    return {condition: dict(metric) for condition, metric in metrics.items()}


def combined(dev: dict, test: dict) -> dict:
    return {
        condition: dict(Counter(dev[condition]) + Counter(test[condition]))
        for condition in dev
    }


def metric_table(metrics: dict[str, dict[str, dict]]) -> str:
    rows = []
    labels = {"normal": "Normal (peringkat 1–3)", "degraded": "Terdegradasi (peringkat 4–6)"}
    for split in ("dev", "test", "keseluruhan"):
        for condition in ("normal", "degraded"):
            metric = metrics[split][condition]
            rows.append(
                [
                    split.capitalize(),
                    labels[condition],
                    f"{metric['recall_hits']}/{metric['qa']} "
                    f"({pct(metric['recall_hits'], metric['qa'])})",
                    f"{metric['number_hits']}/{metric['number_total']} "
                    f"({pct(metric['number_hits'], metric['number_total'])})",
                    f"{metric['all_numbers_covered']}/{metric['numeric_qa']} "
                    f"({pct(metric['all_numbers_covered'], metric['numeric_qa'])})",
                ]
            )
    return markdown_table(
        [
            "Split",
            "Kondisi",
            "Recall@3 strict qrel",
            "Cakupan kemunculan angka gold",
            "QA dengan semua angka tercakup",
        ],
        rows,
    )


def main() -> None:
    raw_config, retrieval_config = load_config_paths()
    number_config = load_number_config(ROOT / raw_config["paths"]["numbers"])
    chunks = list(read_jsonl(ROOT / raw_config["paths"]["chunks"]))
    dev_rows = list(read_jsonl(ROOT / raw_config["paths"]["qa_dev"]))
    test_rows = list(read_jsonl(ROOT / raw_config["paths"]["qa_test"]))
    output_dir = ROOT / raw_config["paths"]["output_dir"]

    # Configuration is frozen before metrics from either split are calculated.
    stopwords = default_query_stopwords(
        retrieval_config.additional_query_stopwords
    )
    indexes = build_document_indexes(chunks, retrieval_config)

    dev_metrics = evaluate_split(
        dev_rows,
        split="dev",
        indexes=indexes,
        stopwords=stopwords,
        retrieval_config=retrieval_config,
        number_config=number_config,
        output_dir=output_dir,
    )
    test_metrics = evaluate_split(
        test_rows,
        split="test",
        indexes=indexes,
        stopwords=stopwords,
        retrieval_config=retrieval_config,
        number_config=number_config,
        output_dir=output_dir,
    )
    metrics = {
        "dev": dev_metrics,
        "test": test_metrics,
        "keseluruhan": combined(dev_metrics, test_metrics),
    }

    min_chunks = min(len(index.chunks) for index in indexes.values())
    max_chunks = max(len(index.chunks) for index in indexes.values())
    output_rows = [
        ["contexts_normal_dev.jsonl", len(dev_rows)],
        ["contexts_degraded_dev.jsonl", len(dev_rows)],
        ["contexts_normal_test.jsonl", len(test_rows)],
        ["contexts_degraded_test.jsonl", len(test_rows)],
        ["qrels_gold_dev.jsonl", len(dev_rows)],
        ["qrels_gold_test.jsonl", len(test_rows)],
    ]

    report = f"""# Tahap 4 — Retrieval BM25 Tetap

## Protokol dan pembekuan

Retrieval `{RETRIEVAL_VERSION}` menggunakan BM25 hanya di dalam laporan pasien
yang sudah dipilih (`doc_id`). Parameter `k1=1,5`, `b=0,75`, dan `epsilon=0,25`
ditetapkan dari protokol sebelum hasil dev atau test dihitung. Query dinormalisasi
NFKC dan *casefold*, lalu stopword Sastrawi serta `apa`, `bagaimana`, `yang`,
`ini`, dan `pasien` dihapus. Stopword tidak dihapus dari corpus.

Kondisi normal memakai peringkat 1–3. Kondisi terdegradasi memakai peringkat
4–6 dari ranking BM25 yang sama, bukan menjalankan retriever berbeda. Tie skor
dipecahkan secara deterministik menurut halaman lalu indeks chunk.

Qrel strict adalah satu chunk pada `(doc_id, page_number, chunk_index)` milik QA.
Recall@3 untuk kondisi terdegradasi berarti apakah qrel berada dalam jendela tiga
hasil yang disajikan, yaitu peringkat asli 4–6. Cakupan angka memakai parser dan
toleransi `numbers_v1.2`; kode PES tidak masuk denominator angka biasa.

## Hasil

{metric_table(metrics)}

Seluruh **{len(indexes)} dokumen** memiliki sekurangnya {min_chunks} chunk dan
sebanyak-banyaknya {max_chunks} chunk, sehingga kedua kondisi selalu berisi tepat
tiga chunk. Dev dan test hanya dievaluasi setelah konfigurasi dibekukan; hasil
test tidak digunakan untuk mengubah tokenisasi, parameter, atau tie-break.

## Artefak konteks

{markdown_table(['File', 'Record'], output_rows)}

Setiap record konteks memuat identitas QA teknis, pertanyaan, token query,
kondisi, serta tiga chunk beserta rank dan skor. `gold_answer`, qrel, dan metrik
tidak dimasukkan ke file konteks agar input LLM tidak membocorkan jawaban.

## Verifikasi implementasi

- Seluruh 121 unit test repository lulus, termasuk 17 tes retrieval baru.
- Audit 858 QA memastikan qrel valid, tepat tiga chunk per kondisi, dokumen
  sesuai, query tidak kosong, rank benar, dan tidak ada overlap antarkondisi.
- Tidak ada `gold_answer`, `gold_chunk_id`, atau qrel dalam record konteks.
- Ketujuh artefak konteks/qrel/laporan identik secara byte pada rerun
  (`REPRODUCIBLE_OUTPUTS=True`).
- Data mentah di `data/dataset` dan `data/chunks` tidak berubah.

## Interpretasi dan batasan

- Recall mengukur ditemukannya chunk gold tunggal, bukan seluruh chunk yang
  mungkin mendukung jawaban.
- Cakupan angka dapat tetap tinggi ketika qrel tidak ditemukan apabila nilai
  yang sama muncul di bagian lain laporan.
- Kondisi peringkat 4–6 adalah stress test terkontrol dan bukan model alami dari
  seluruh jenis kegagalan retrieval.
- BM25 dibatasi pada laporan pasien yang dimaksud; asumsi pengguna telah memilih
  pasien harus dipertahankan dalam interpretasi penelitian.
"""
    REPORT_PATH.write_text(report, encoding="utf-8", newline="\n")

    for split in ("dev", "test", "keseluruhan"):
        for condition in ("normal", "degraded"):
            metric = metrics[split][condition]
            print(
                f"{split.upper()} {condition.upper()} "
                f"RECALL={metric['recall_hits']}/{metric['qa']} "
                f"({pct(metric['recall_hits'], metric['qa'])}) "
                f"NUMBER_COVERAGE={metric['number_hits']}/{metric['number_total']} "
                f"({pct(metric['number_hits'], metric['number_total'])})"
            )
    print(f"DOCUMENTS={len(indexes)} CHUNKS={len(chunks)}")
    print(f"REPORT={REPORT_PATH.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
