# Progres Penelitian

Ringkasan checkpoint setiap tahap ditambahkan secara kronologis setelah tahap
tersebut selesai dan diverifikasi.

## Checkpoint Tahap 0: Setup

Status: SELESAI DENGAN CATATAN

Yang dikerjakan:
- Membuat struktur folder penelitian untuk konfigurasi, prompt, data olahan,
  notebook, source, metode, script, hasil, laporan, paper, model, dan test.
- Membuat virtual environment `.venv` menggunakan Python 3.12.10.
- Mengunci dan memasang dependensi lokal serta memisahkan dependensi inferensi
  GPU Kaggle.
- Menambahkan perlindungan Git untuk data, hasil, model, rahasia, environment,
  dan cache.
- Menambahkan dokumentasi setup dan log keputusan awal.

File yang dibuat/diubah:
- `.gitignore` — aturan privasi dan artefak lokal.
- `requirements.txt` — 13 dependensi langsung lokal dengan versi eksak.
- `notebooks/requirements-kaggle.txt` — stack inferensi Kaggle dengan versi
  eksak.
- `README.md` — petunjuk setup lokal awal.
- `src/__init__.py` dan `src/methods/__init__.py` — inisialisasi package.
- `reports/DECISIONS.md` — keputusan setup dan catatan privasi.
- `reports/PROGRESS.md` — checkpoint ini.

Bukti verifikasi:
- Python lokal: `3.12.10`.
- `pip check`: `No broken requirements found.`
- Smoke test import dan operasi sederhana untuk seluruh 13 dependensi:
  `SMOKE_CHECKS: PASS`.
- `git check-ignore --no-index` mengonfirmasi pola untuk `data/`, `results/`,
  `models/`, `.env`, dan `.venv/`.
- Ditemukan 121 path di `data/` telah dilacak Git sebelum aturan ignore dibuat;
  file lokal tidak dihapus dan index Git tidak diubah.

Kriteria lolos tahap ini:
- [x] Environment terpasang.
- [x] `requirements.txt` menggunakan versi eksak.
- [x] `.gitignore` mengabaikan data, results, models, `.env`, dan cache.
- [x] Semua library lokal dapat di-import.

Temuan penting / keanehan:
- `data/` sudah dilacak Git, sehingga `.gitignore` tidak dapat menghentikan
  tracking terhadap 121 path lama. Pembersihan index dan kemungkinan riwayat
  Git memerlukan keputusan pengguna tersendiri.
- Stack Kaggle dicatat tetapi tidak dipasang di Windows; verifikasi runtime GPU
  dilakukan pada Tahap 5.

Pertanyaan atau keputusan yang butuh persetujuan Anda:
- Apakah 121 path `data/` boleh dihapus dari index Git dengan
  `git rm -r --cached data` tanpa menghapus file lokal? Jika repository pernah
  dipublikasikan, pembersihan riwayat Git juga perlu dibahas terpisah.

Rencana tahap berikutnya (belum dikerjakan):
- Tahap 1 akan mengaudit struktur data dan menghasilkan statistik EDA serta
  visualisasi, setelah rencananya disetujui.

Saran commit message (bahasa Inggris):
- `chore: initialize reproducible research environment`

Menunggu konfirmasi "lanjut".

## Checkpoint Tahap 1: Pemahaman Data dan EDA

Status: SELESAI DENGAN CATATAN

Yang dikerjakan:
- Mengaudit schema, jumlah record, kelengkapan field, panjang teks, nama file,
  join QA–chunk, duplikasi, dan validitas `answer_start` secara read-only.
- Memetakan delapan tipe pertanyaan secara eksploratif dan membandingkan jumlah
  mentah dengan deduplikasi sementara *keep-first*.
- Menghitung statistik angka per tipe dan kategori, kode PES, serta cakupan
  angka gold pada laporan lengkap dan chunk gold.
- Membuat laporan EDA dan tiga gambar 300 dpi melalui script reproducible.

File yang dibuat/diubah:
- `scripts/run_eda.py` — generator EDA deterministik dan read-only terhadap data.
- `reports/01_eda.md` — laporan lengkap Tahap 1.
- `reports/figures/01_question_types.png` — distribusi tipe pertanyaan.
- `reports/figures/01_numeric_by_type.png` — proporsi jawaban berangka per tipe.
- `reports/figures/01_number_categories.png` — cakupan kategori angka.
- `reports/DECISIONS.md` — status aturan eksploratif dan isu konteks kanonik.
- `reports/PROGRESS.md` — checkpoint ini.

Bukti verifikasi:
- Data berisi 911 QA, 120 dokumen, 120 file chunk, dan 13.737 chunk.
- Semua 911 QA berhasil di-join secara unik berdasarkan file, halaman, dan
  indeks chunk; 899/911 teks konteks identik dengan chunk.
- Terdapat 35 kelompok duplikat dengan 53 baris berlebih; ukuran deduplikasi
  eksploratif adalah 858 QA.
- Hanya 79/911 (8,67%) `answer_start` yang cocok tepat.
- Parser eksploratif menemukan 441/911 (48,41%) jawaban dengan angka biasa dan
  kode PES pada 120/128 (93,75%) jawaban diagnosis PES.
- Cakupan kemunculan angka gold: 4.800/4.830 (99,38%) pada laporan pasien dan
  3.485/4.830 (72,15%) pada chunk gold; 435/441 (98,64%) jawaban berangka
  memiliki seluruh angka di laporan.
- Ketiga PNG beresolusi 300 dpi; kompilasi script lulus dan SHA-256 seluruh
  output identik setelah dijalankan ulang (`REPRODUCIBLE_OUTPUTS=True`).
- `git status -- data` kosong: data mentah tidak diubah.

Kriteria lolos tahap ini:
- [x] Statistik umum dan distribusi delapan tipe pertanyaan dilaporkan.
- [x] Statistik angka per tipe dan kategori dilaporkan.
- [x] Contoh pendek setiap kategori disertakan tanpa identitas pasien.
- [x] Tiga gambar tersimpan dan telah diperiksa secara visual.

Temuan penting / keanehan:
- Snapshot data saat ini tidak memiliki nama `#Uxxxx`; satu nama memuat U+2060
  pada dataset dan disk. Normalisasi tetap diperlukan agar stabil.
- Mayoritas kelompok duplikat bukan salinan identik: hanya 4/35 mempunyai
  jawaban sama dan 7/35 mempunyai konteks sama.
- Dua hasil tidak persis sama dengan temuan pendahuluan: jumlah jawaban dengan
  angka minimal dua digit adalah 393 menurut parser eksploratif (402 dengan
  regex mentah), bukan 413; cakupan chunk gold adalah 72,15%, bukan sekitar 76%.
  Perbedaan tidak disesuaikan dan harus diaudit pada Tahap 3.

Pertanyaan atau keputusan yang butuh persetujuan Anda:
- Pada Tahap 2 perlu ditetapkan aturan deduplikasi untuk kelompok yang berbeda
  jawaban/konteks serta sumber konteks kanonik bagi 12 QA yang tidak identik.

Rencana tahap berikutnya (belum dikerjakan):
- Tahap 2 akan mengimplementasikan normalisasi nama, kebijakan deduplikasi yang
  dapat diaudit, pemetaan tipe, split dokumen 20% dev/80% test seed 42, serta
  penanda angka dan kode PES.

Saran commit message (bahasa Inggris):
- `feat: add reproducible exploratory data analysis`

Menunggu konfirmasi "lanjut".

## Checkpoint Tahap 2: Pra-pemrosesan dan Split

Status: SELESAI DENGAN CATATAN

Yang dikerjakan:
- Mengimplementasikan normalisasi nama file, validasi schema, join QA–chunk,
  deduplikasi deterministik, pemetaan tipe, dan split per dokumen.
- Menggunakan konteks corpus chunk sebagai konteks kanonik dan mempertahankan
  konteks dataset untuk audit.
- Menghasilkan data bersih, split dev/test, corpus chunk bersih, audit
  duplikasi, dan manifest split.
- Menambahkan penanda angka provisional dan kode PES serta 25 unit test.

File yang dibuat/diubah:
- `configs/data.yaml` — konfigurasi pra-pemrosesan dan split yang dibekukan.
- `src/data.py` — implementasi pipeline data.
- `scripts/preprocess.py` — entry point dan generator laporan Tahap 2.
- `tests/test_data.py` — unit test normalisasi, tipe, penanda, deduplikasi, dan
  split.
- `reports/02_preprocessing.md` — laporan rekonsiliasi dan distribusi split.
- `data/processed/qa_clean.jsonl` — 858 QA final.
- `data/processed/qa_dev.jsonl` — 175 QA dari 24 dokumen dev.
- `data/processed/qa_test.jsonl` — 683 QA dari 96 dokumen test.
- `data/processed/chunks_clean.jsonl` — 13.737 chunk kanonik.
- `data/processed/dedup_audit.jsonl` — audit 35 kelompok duplikat.
- `data/processed/split_manifest.json` — konfigurasi, fingerprint, dan daftar
  dokumen per split.
- `reports/DECISIONS.md` dan `reports/PROGRESS.md` — keputusan dan checkpoint.

Bukti verifikasi:
- Rekonsiliasi: `911 → 858 → 858 → 858`; 53 baris duplikat dibuang dan 0 QA
  gagal di-join.
- Split: dev 24 dokumen/175 QA; test 96 dokumen/683 QA; irisan dokumen 0.
- Semua delapan tipe pertanyaan tersedia pada dev dan test.
- Penanda: dev memiliki 89 `has_number` dan 24 `has_pes_code`; test memiliki
  329 `has_number` dan 89 `has_pes_code`.
- `25 passed in 0.12s`.
- Regenerasi menghasilkan SHA-256 identik untuk keenam artefak data dan laporan
  (`REPRODUCIBLE_OUTPUTS=True`).
- Validasi menyeluruh: `PROCESSED_INTEGRITY_CHECK: PASS`; tidak ada perubahan
  pada `data/dataset` atau `data/chunks`.

Kriteria lolos tahap ini:
- [x] Rekonsiliasi jumlah QA lengkap.
- [x] Tidak ada QA gagal di-join.
- [x] Tidak ada dokumen pada dua split.
- [x] Semua delapan tipe tersedia pada kedua split.
- [x] `has_number` dan `has_pes_code` tersedia pada setiap QA.

Temuan penting / keanehan:
- Dua puluh lima unit test menangkap dan memperbaiki decoder `#Uxxxx` yang
  semula dapat menyerap huruf heksadesimal setelah empat digit.
- Semua 12 ketidaksesuaian konteks berada pada split test. Keputusan memakai
  chunk corpus sebagai konteks kanonik telah dibuat sebelum hasil split dilihat,
  dan isi kasus test tidak digunakan untuk desain metode.
- `has_number` menandai 418/858 QA dan tetap provisional sampai Tahap 3.

Pertanyaan atau keputusan yang butuh persetujuan Anda:
- Tidak ada untuk menutup Tahap 2. Tahap 3 harus mengaudit ulang `has_number`
  dan meregenerasi data QA jika hasil modul tervalidasi berbeda.

Rencana tahap berikutnya (belum dikerjakan):
- Tahap 3 akan mengimplementasikan ekstraksi/normalisasi angka dan kode PES,
  minimal 30 unit test, validasi cakupan pada gold, serta 20 contoh acak untuk
  pemeriksaan pengguna.

Saran commit message (bahasa Inggris):
- `feat: add deterministic preprocessing and document splits`

Menunggu konfirmasi "lanjut".

## Checkpoint Tahap 3: Modul Angka dan Validasi Metrik

Status: SELESAI DENGAN CATATAN

Yang dikerjakan:
- Mengimplementasikan ekstraksi dan normalisasi angka klinis Indonesia,
  rentang, persen, satuan, serta kode PES yang dipisahkan dari angka biasa.
- Membekukan toleransi pencocokan pada selisih relatif ≤0,5% atau absolut
  ≤0,01 dan menyimpannya dalam konfigurasi mesin-baca.
- Menambahkan 104 unit test dan tes regresi untuk seluruh koreksi berbasis dev.
- Meregenerasi penanda angka pada data olahan dan menghasilkan audit terstruktur
  per QA, laporan cakupan, serta 20 contoh acak dev.

File yang dibuat/diubah:
- `configs/numbers.yaml` — format, eksklusi, kategori, dan toleransi final.
- `src/numbers.py` — parser angka, kode PES, kategorisasi, dan pencocokan.
- `tests/test_numbers.py` — unit test dan kasus regresi modul angka.
- `src/data.py`, `configs/data.yaml`, `tests/test_data.py` — integrasi penanda
  `numbers_v1.2` ke pipeline pra-pemrosesan.
- `scripts/validate_numbers.py` — validasi cakupan dan generator artefak.
- `data/processed/gold_numbers.jsonl` — ekstraksi angka/kode per QA.
- `data/processed/qa_clean.jsonl`, `qa_dev.jsonl`, `qa_test.jsonl` — penanda
  angka final dengan ID, konteks, dan split yang dipertahankan.
- `reports/03_numbers.md` — metode, hasil, audit anti-kebocoran, dan keterbatasan.
- `reports/03_number_examples.md` — 20 contoh acak dari dev.
- `reports/DECISIONS.md` dan `reports/PROGRESS.md` — keputusan dan checkpoint.

Bukti verifikasi:
- `104 passed in 0.30s`; syarat minimal 30 unit test terlampaui.
- Penanda final: 322/858 QA berangka, terdiri dari 67/175 dev dan 255/683
  test; kode PES terdapat pada 24 dev dan 89 test.
- Cakupan kemunculan angka gold: 3617/3645 (99,23%) pada laporan pasien dan
  2445/3645 (67,08%) pada chunk gold.
- Semua angka gold per jawaban tercakup pada laporan untuk 314/322 (97,52%)
  QA berangka dan pada chunk untuk 141/322 (43,79%).
- `PROCESSED_INTEGRITY_CHECK: PASS`; dev/test tetap 24/96 dokumen tanpa overlap,
  seluruh flag identik dengan hasil parser, dan 20 contoh unik semuanya dev.
- SHA-256 sepuluh artefak data/laporan identik setelah rerun
  (`REPRODUCIBLE_OUTPUTS=True`).
- `git status -- data/dataset data/chunks` kosong dan `git diff --check` tidak
  menemukan error whitespace.

Kriteria lolos tahap ini:
- [x] Sedikitnya 30 unit test lulus (aktual: 104).
- [x] Proporsi angka gold pada laporan dan chunk dilaporkan; selisih terhadap
  temuan pendahuluan dijelaskan tanpa tuning ke target.
- [x] Dua puluh contoh ekstraksi acak ditampilkan dan seluruhnya berasal dari
  dev.

Temuan penting / keanehan:
- Cakupan laporan 99,23% konsisten dengan estimasi pendahuluan sekitar 99%,
  tetapi cakupan chunk 67,08% lebih rendah 8,92 poin persentase dari estimasi
  sekitar 76%.
- Parser tetap dapat mempertahankan sebagian nomor regulasi, referensi bebas,
  atau indeks formula yang tidak memiliki pola eksklusi tegas. Kategori berbasis
  konteks juga bersifat deskriptif, bukan label klinis tervalidasi.
- Setelah validasi pertama, koreksi hanya dirancang dari audit dev; setiap
  versi dikunci dan seluruh validasi dev/test dijalankan ulang serta dicatat.

Pertanyaan atau keputusan yang butuh persetujuan Anda:
- Tidak ada untuk menutup Tahap 3. Selisih cakupan chunk akan dibawa sebagai
  catatan saat menafsirkan hasil retrieval, bukan dihilangkan lewat tuning.

Rencana tahap berikutnya (belum dikerjakan):
- Tahap 4 akan mengimplementasikan BM25 tetap untuk kondisi normal (peringkat
  1–3) dan terdegradasi (peringkat 4–6), lalu melaporkan Recall@3 dan cakupan
  angka gold serta menyimpan konteks per split/kondisi.

Saran commit message (bahasa Inggris):
- `feat: add validated numeric extraction and coverage audit`

Menunggu konfirmasi "lanjut".

## Checkpoint Tahap 4: Retrieval BM25 Tetap

Status: SELESAI

Yang dikerjakan:
- Mengimplementasikan BM25 per laporan pasien dengan parameter protokol dan
  tokenisasi query berbasis stopword Sastrawi.
- Membekukan kondisi normal pada peringkat 1–3 dan kondisi terdegradasi pada
  peringkat 4–6 dari ranking yang sama.
- Membuat qrel strict, menghitung Recall@3 serta cakupan angka gold, dan
  menghasilkan konteks fixed untuk seluruh QA dev/test.
- Memisahkan konteks LLM dari jawaban gold, qrel, dan metrik evaluasi.

File yang dibuat/diubah:
- `configs/retrieval.yaml` — parameter dan kondisi retrieval yang dibekukan.
- `src/retrieval.py` — tokenisasi, indeks BM25 per dokumen, ranking, pemilihan
  kondisi, qrel, dan cakupan numerik.
- `scripts/run_retrieval.py` — generator konteks, qrels, metrik, dan laporan.
- `tests/test_retrieval.py` — 17 tes retrieval.
- `data/processed/contexts_normal_dev.jsonl` — 175 konteks normal dev.
- `data/processed/contexts_degraded_dev.jsonl` — 175 konteks terdegradasi dev.
- `data/processed/contexts_normal_test.jsonl` — 683 konteks normal test.
- `data/processed/contexts_degraded_test.jsonl` — 683 konteks terdegradasi test.
- `data/processed/qrels_gold_dev.jsonl` dan `qrels_gold_test.jsonl` — qrel strict.
- `reports/04_retrieval.md` — metode, hasil, validasi, dan keterbatasan.
- `reports/DECISIONS.md` dan `reports/PROGRESS.md` — keputusan dan checkpoint.

Bukti verifikasi:
- Recall@3 keseluruhan: normal 305/858 (35,55%); terdegradasi 138/858
  (16,08%).
- Cakupan kemunculan angka gold keseluruhan: normal 1606/3645 (44,06%);
  terdegradasi 1388/3645 (38,08%).
- Dev: Recall 27,43%/20,57% dan cakupan angka 43,89%/39,64% untuk
  normal/terdegradasi.
- Test: Recall 37,63%/14,93% dan cakupan angka 44,11%/37,66% untuk
  normal/terdegradasi.
- `RETRIEVAL_INTEGRITY_CHECK=PASS`: 858 qrel valid, tiga chunk per kondisi,
  dokumen sesuai, 0 query kosong, 0 kebocoran gold, dan 0 overlap kondisi.
- `121 passed`; 17 di antaranya tes retrieval baru.
- Ketujuh artefak konteks/qrel/laporan identik pada rerun
  (`REPRODUCIBLE_OUTPUTS=True`), dan data mentah tidak berubah.

Kriteria lolos tahap ini:
- [x] Recall@3 dan cakupan angka gold dilaporkan untuk kondisi normal dan
  terdegradasi pada dev/test.
- [x] File konteks tersedia untuk seluruh split dan kondisi.

Temuan penting / keanehan:
- Recall normal relatif rendah karena delapan pertanyaan merupakan template
  umum yang berulang, sehingga sinyal leksikal untuk menemukan lokasi gold
  terbatas.
- Kondisi terdegradasi menurunkan Recall@3 sebesar 19,47 poin persentase dan
  cakupan angka sebesar 5,98 poin persentase secara keseluruhan.
- Pada dev, proporsi QA dengan seluruh angka tercakup sedikit lebih tinggi pada
  kondisi terdegradasi (19,40%) daripada normal (14,93%), meski cakupan per
  kemunculan angka lebih rendah. Semua hasil dipertahankan tanpa tuning.

Pertanyaan atau keputusan yang butuh persetujuan Anda:
- Tidak ada untuk menutup Tahap 4.

Rencana tahap berikutnya (belum dikerjakan):
- Tahap 5 akan menyiapkan notebook inferensi Kaggle, format job/result dan
  cache, konfigurasi dua model, alur multi-langkah, serta smoke test lima QA dev
  per model.

Saran commit message (bahasa Inggris):
- `feat: add fixed bm25 retrieval contexts`

Menunggu konfirmasi "lanjut".

