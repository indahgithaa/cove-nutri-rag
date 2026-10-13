# Tahap 2 — Pra-pemrosesan dan Split

## Konfigurasi yang dibekukan

- Seed: **42**.
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
| QA mentah | 911 |
| Kelompok duplikat | 35 |
| Baris duplikat dibuang | 53 |
| Setelah deduplikasi | 858 |
| Berhasil di-join | 858 |
| Gagal di-join | 0 |
| QA final | 858 |

Alur rekonsiliasi: **911 →
858 → 858 →
858**. Audit 35 kelompok duplikat menyimpan ID yang
dipertahankan dan dibuang tanpa menyalin keputusan berdasarkan isi jawaban.

## Hasil split

| Split | Dokumen | QA | Proporsi dokumen | Proporsi QA |
| --- | ---: | ---: | ---: | ---: |
| Dev | 24 | 175 | 20,00% | 20,40% |
| Test | 96 | 683 | 80,00% | 79,60% |

Irisan dokumen dev dan test adalah **0**.
Daftar `doc_id` tiap split dibekukan di `split_manifest.json`.

### Distribusi tipe pertanyaan

| Tipe | Dev | Test |
| --- | --- | --- |
| Skrining | 24 | 96 |
| Status gizi | 24 | 96 |
| Biokimia/lab | 24 | 95 |
| Diagnosis PES | 24 | 96 |
| Tujuan diet | 24 | 96 |
| Prinsip diet | 24 | 95 |
| Syarat diet | 24 | 95 |
| Pedoman diet | 7 | 14 |

Kedelapan tipe tersedia pada kedua split. Perbedaan satu QA pada beberapa tipe
berasal dari dokumen sumber yang memang tidak memiliki semua template.

### Penanda

| Penanda | Dev | Test | Total |
| --- | --- | --- | --- |
| QA | 175 | 683 | 858 |
| has_number (provisional) | 89 (50,86%) | 329 (48,17%) | 418 |
| has_pes_code | 24 (13,71%) | 89 (13,03%) | 113 |
| context_changed | 0 | 12 | 12 |

`has_number` masih menggunakan versi **stage2_candidate_v1**: kode PES dimask,
lalu jawaban ditandai jika memuat kandidat angka biasa. Field ini wajib dihitung
ulang dan dibandingkan dengan modul tervalidasi Tahap 3 sebelum pemilihan subset
eksperimen. `has_pes_code` menggunakan regex kode `NI/NC/NB` terpisah.

## Artefak data olahan

| File | Baris | Byte |
| --- | --- | --- |
| `data/processed/qa_clean.jsonl` | 858 | 2973282 |
| `data/processed/qa_dev.jsonl` | 175 | 629693 |
| `data/processed/qa_test.jsonl` | 683 | 2343589 |
| `data/processed/chunks_clean.jsonl` | 13737 | 15421986 |
| `data/processed/dedup_audit.jsonl` | 35 | 10880 |
| `data/processed/split_manifest.json` | 213 | 11622 |

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
