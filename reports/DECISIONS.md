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

## 2026-10-13 — Kebijakan deduplikasi Tahap 2

- **Keputusan:** Setelah normalisasi nama file, kelompok duplikat dibentuk dari
  `(normalized_file, exact_trimmed_question)` dan baris dengan ID asli terkecil
  dipertahankan.
- **Alasan:** Aturan ini deterministik, independen dari kualitas isi jawaban,
  dan tidak memilih label secara oportunistik. Semua ID yang dipertahankan dan
  dibuang disimpan di `data/processed/dedup_audit.jsonl`.

## 2026-10-13 — Konteks kanonik Tahap 2

- **Keputusan:** Teks corpus chunk pada kunci `(doc_id, page_number,
  chunk_index)` menjadi field `context` kanonik. Teks konteks dari dataset tetap
  disimpan sebagai `dataset_context`, disertai `context_changed`.
- **Alasan:** Retrieval berikutnya beroperasi pada corpus chunk, sehingga qrel
  dan konteks kanonik harus merujuk pada representasi corpus yang sama. Retensi
  konteks dataset menjaga auditabilitas 12 ketidaksesuaian.

## 2026-10-13 — Split dokumen dibekukan

- **Keputusan:** Urutkan 120 `doc_id`, acak dengan `random.Random(42)`, lalu
  tetapkan 24 dokumen pertama sebagai dev dan 96 sisanya sebagai test.
- **Alasan:** Algoritme tidak bergantung pada urutan filesystem, menghasilkan
  tepat 20%/80% dokumen, tidak menimbulkan kebocoran, dan mempertahankan semua
  delapan tipe pertanyaan pada kedua split.

## 2026-10-13 — Penanda angka Tahap 2 bersifat provisional

- **Keputusan:** `has_number` versi `stage2_candidate_v1` memask kode PES lalu
  mendeteksi kandidat angka biasa. `has_pes_code` dihitung terpisah.
- **Alasan:** Urutan tahap meminta penanda tersedia sebelum modul angka formal
  Tahap 3. Penanda ini tidak boleh digunakan untuk pemilihan subset eksperimen
  sebelum diverifikasi dan, bila perlu, dihitung ulang oleh modul tervalidasi.

## 2026-10-13 — Aturan angka final Tahap 3

- **Keputusan:** Membekukan parser `numbers_v1.2`: koma sebagai desimal, titik
  tiga digit sebagai pemisah ribuan, rentang menjadi dua nilai, persen tetap
  dalam poin persentase, serta nomor daftar/halaman/bagian, tahun sitasi, dan
  komponen kode PES dikecualikan dari angka biasa.
- **Keputusan:** Dua nilai cocok bila selisih absolutnya ≤0,01 atau selisih
  relatif simetrisnya ≤0,5%, dengan penyebut nilai absolut terbesar. Unit tidak
  menentukan kecocokan.
- **Alasan:** Definisi tersebut eksplisit, dapat diuji, mendukung format angka
  klinis Indonesia, dan sesuai definisi metrik pada protokol penelitian.

## 2026-10-13 — Koreksi parser setelah validasi pertama

- **Temuan:** Sesudah run validasi pertama, pemeriksaan 20 contoh acak dari
  **dev** menemukan tanda negatif berspasi, sitasi tahun majemuk, dan pola
  perkalian kompak belum ditangani. Audit dev berikutnya menemukan awalan angka
  parsial pada kode alfanumerik dan sitasi multi-baris.
- **Keputusan:** Memperbaiki masalah tersebut dalam `numbers_v1.1` lalu
  `numbers_v1.2`, menambah tes regresi, dan menjalankan ulang validasi lengkap
  setelah setiap perubahan. Tidak ada contoh atau arah hasil test yang dipakai
  untuk merancang koreksi.
- **Alasan:** Perubahan memperbaiki cacat format yang dapat direproduksi pada
  dev. Rerun penuh menjaga hasil dev/test tetap berasal dari satu konfigurasi
  final yang sama.

## 2026-10-13 — Penanda angka dan hasil validasi final

- **Keputusan:** Mengganti penanda provisional Tahap 2 dengan hasil
  `numbers_v1.2`; subset final berangka adalah 322/858 QA (67 dev, 255 test).
- **Temuan:** Cakupan kemunculan angka gold pada laporan adalah 3617/3645
  (99,23%), sedangkan pada chunk gold 2445/3645 (67,08%). Nilai chunk lebih
  rendah 8,92 poin persentase dari estimasi pendahuluan sekitar 76%.
- **Keputusan:** Memakai dan melaporkan nilai final apa adanya tanpa menyesuaikan
  parser ke estimasi pendahuluan.
- **Alasan:** Parser final mengecualikan angka nonklinis secara lebih ketat,
  konteks kanonik memakai corpus chunk, dan definisi rinci parser pendahuluan
  tidak tersedia. Selisih ini merupakan keterbatasan yang harus dibawa ke
  analisis berikutnya, bukan sasaran optimasi.

## 2026-10-13 — Retrieval BM25 tetap Tahap 4

- **Keputusan:** Membekukan `bm25_fixed_v1` dengan `k1=1,5`, `b=0,75`,
  `epsilon=0,25`, dan ruang pencarian hanya chunk dalam `doc_id` pasien yang
  sudah dipilih.
- **Keputusan:** Query memakai token Unicode NFKC/casefold dan menghapus
  stopword Sastrawi ditambah `apa`, `bagaimana`, `yang`, `ini`, serta `pasien`.
  Stopword corpus tidak dihapus. Tie skor dipecahkan menurut halaman dan indeks
  chunk.
- **Keputusan:** Kondisi normal memakai peringkat 1–3 dan kondisi terdegradasi
  memakai peringkat 4–6 dari ranking yang sama. Qrel strict ditentukan langsung
  oleh `(doc_id, page_number, chunk_index)` QA.
- **Alasan:** Seluruh pilihan ditetapkan oleh protokol sebelum metrik dev/test
  dihitung, sehingga retrieval sama untuk semua metode dan stress test dapat
  dibandingkan secara terkontrol.

## 2026-10-13 — Pemisahan konteks LLM dan label evaluasi

- **Keputusan:** File `contexts_<condition>_<split>.jsonl` hanya memuat
  pertanyaan, token query, dan tiga chunk hasil retrieval. Jawaban gold, qrel,
  dan metrik disimpan terpisah.
- **Alasan:** Mencegah kebocoran label ke input LLM dan memastikan seluruh
  metode berikutnya memakai konteks fixed yang sama.

## 2026-10-13 — Hasil retrieval tidak dituning

- **Temuan:** Secara keseluruhan, Recall@3 strict qrel adalah 35,55% pada
  kondisi normal dan 16,08% pada kondisi terdegradasi. Cakupan kemunculan angka
  gold masing-masing 44,06% dan 38,08%.
- **Keputusan:** Mempertahankan konfigurasi tanpa penyesuaian setelah hasil test
  terlihat dan melaporkan nilai rendah apa adanya.
- **Alasan:** Pertanyaan dataset berupa template umum sehingga retrieval rendah
  merupakan karakteristik penting data, bukan alasan untuk tuning pada test.
  Modul retriever tetap umum dan dapat digunakan kembali untuk query expansion
  atau hierarchical retrieval bila diperlukan.

