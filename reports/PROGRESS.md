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

