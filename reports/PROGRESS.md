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

