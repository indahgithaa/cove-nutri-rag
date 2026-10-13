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

## 2026-10-13 — Status aturan EDA Tahap 1

- **Keputusan:** Pemetaan delapan tipe pertanyaan, deduplikasi *keep-first*,
  normalisasi angka, kategorisasi angka, dan toleransi pencocokan yang digunakan
  dalam `reports/01_eda.md` dinyatakan eksploratif, bukan konfigurasi final.
- **Alasan:** Sebanyak 31 dari 35 kelompok duplikat mempunyai jawaban berbeda;
  selain itu parser eksploratif menghasilkan 393 jawaban dengan angka minimal
  dua digit, bukan temuan pendahuluan 413, dan cakupan angka pada chunk gold
  72,15%, bukan sekitar 76%. Keputusan final memerlukan audit formal pada Tahap
  2 dan unit test modul angka pada Tahap 3.

## 2026-10-13 — Sumber konteks kanonik belum ditetapkan

- **Temuan:** Seluruh 911 QA cocok secara unik berdasarkan `(file,
  page_number, chunk_index)`, tetapi hanya 899 teks `context` yang identik
  dengan teks pada file chunk.
- **Keputusan:** Tidak mengubah 12 konteks yang berbeda pada Tahap 1. Pemilihan
  antara `context` dataset dan teks chunk sebagai sumber kanonik diputuskan dan
  dicatat pada Tahap 2 sebelum data olahan dibuat.
- **Alasan:** Tahap 1 hanya mengaudit data dan tidak berwenang membuat perubahan
  pra-pemrosesan.

