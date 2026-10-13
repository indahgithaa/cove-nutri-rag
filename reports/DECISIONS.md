# Catatan Keputusan Penelitian

Semua keputusan desain dicatat secara kronologis. Keputusan setelah evaluasi
test wajib disertai alasan dan, bila mengubah konfigurasi, mewajibkan seluruh
konfigurasi terdampak dijalankan ulang.

## 2026-10-13 — Lingkungan lokal

- **Keputusan:** Menggunakan Python 3.12 pada Windows/PowerShell dan virtual
  environment repository-local bernama `.venv`.
- **Alasan:** Python 3.12.10 telah tersedia pada mesin penelitian dan seluruh
  dependensi lokal yang dipilih menyediakan dukungan Python 3.12.

## 2026-10-13 — Strategi penguncian dependensi

- **Keputusan:** Semua dependensi langsung lokal dikunci dengan versi eksak di
  `requirements.txt`; runtime langsung BERTScore (`torch` dan `transformers`)
  juga dikunci eksplisit.
- **Alasan:** Mengurangi variasi lingkungan tanpa mencampurkan stack inferensi
  GPU Kaggle ke environment lokal.

## 2026-10-13 — Stack inferensi Kaggle awal

- **Keputusan:** Mengunci stack Kaggle pada `vllm==0.8.5.post1`,
  `torch==2.6.0`, dan paket pendukung yang kompatibel di
  `notebooks/requirements-kaggle.txt`.
- **Alasan:** Metadata paket vLLM menetapkan PyTorch 2.6.0 dan membutuhkan
  Transformers minimal 4.51.1. Pemilihan model, revisi model, lisensi, dan
  kuantisasi belum diputuskan dan akan diverifikasi pada tahap yang relevan.

## 2026-10-13 — Proteksi artefak sensitif

- **Keputusan:** Mengabaikan seluruh `data/`, `results/`, `models/`, file
  `.env`, dan cache dari Git.
- **Alasan:** Data klinis tetap sensitif walaupun telah disamarkan, sedangkan
  output eksperimen dan model dapat berukuran besar atau memuat cuplikan data.

## 2026-10-13 — Data yang sudah dilacak Git

- **Temuan:** Sebanyak 121 path di bawah `data/` telah dilacak Git sebelum
  `.gitignore` Tahap 0 dibuat.
- **Keputusan sementara:** Tidak menjalankan `git rm --cached` dan tidak
  menulis ulang riwayat Git tanpa persetujuan pengguna. `.gitignore` tetap
  diberlakukan untuk mencegah file data baru ikut terlacak.
- **Alasan:** Menghapus data dari index atau riwayat repository merupakan
  perubahan terhadap status versi yang harus dilakukan secara eksplisit dan
  tidak boleh disamakan dengan penghapusan file lokal.

