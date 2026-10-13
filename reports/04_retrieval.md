# Tahap 4 — Retrieval BM25 Tetap

## Protokol dan pembekuan

Retrieval `bm25_fixed_v1` menggunakan BM25 hanya di dalam laporan pasien
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

| Split | Kondisi | Recall@3 strict qrel | Cakupan kemunculan angka gold | QA dengan semua angka tercakup |
| --- | --- | --- | --- | --- |
| Dev | Normal (peringkat 1–3) | 48/175 (27,43%) | 341/777 (43,89%) | 10/67 (14,93%) |
| Dev | Terdegradasi (peringkat 4–6) | 36/175 (20,57%) | 308/777 (39,64%) | 13/67 (19,40%) |
| Test | Normal (peringkat 1–3) | 257/683 (37,63%) | 1265/2868 (44,11%) | 60/255 (23,53%) |
| Test | Terdegradasi (peringkat 4–6) | 102/683 (14,93%) | 1080/2868 (37,66%) | 55/255 (21,57%) |
| Keseluruhan | Normal (peringkat 1–3) | 305/858 (35,55%) | 1606/3645 (44,06%) | 70/322 (21,74%) |
| Keseluruhan | Terdegradasi (peringkat 4–6) | 138/858 (16,08%) | 1388/3645 (38,08%) | 68/322 (21,12%) |

Seluruh **120 dokumen** memiliki sekurangnya 32 chunk dan
sebanyak-banyaknya 256 chunk, sehingga kedua kondisi selalu berisi tepat
tiga chunk. Dev dan test hanya dievaluasi setelah konfigurasi dibekukan; hasil
test tidak digunakan untuk mengubah tokenisasi, parameter, atau tie-break.

## Artefak konteks

| File | Record |
| --- | --- |
| contexts_normal_dev.jsonl | 175 |
| contexts_degraded_dev.jsonl | 175 |
| contexts_normal_test.jsonl | 683 |
| contexts_degraded_test.jsonl | 683 |
| qrels_gold_dev.jsonl | 175 |
| qrels_gold_test.jsonl | 683 |

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
