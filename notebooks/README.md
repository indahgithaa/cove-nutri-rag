# Inferensi Kaggle Tahap 5

Notebook ini menjalankan smoke test RAG standar pada lima QA dev yang sama untuk
dua model. Bundle memuat potongan laporan klinis, sehingga **wajib** diunggah
sebagai dataset/notebook Kaggle privat dan tidak boleh dipublikasikan.

## Alur

1. Jalankan `python scripts/prepare_smoke_jobs.py` dan
   `python scripts/make_kaggle_bundle.py` secara lokal.
2. Unggah `results/kaggle/stage5_smoke_bundle.zip` sebagai Kaggle Dataset privat.
3. Buat notebook privat, aktifkan Internet dan GPU T4, lalu buka
   `notebooks/run_llm.ipynb` dari bundle atau unggah notebook tersebut.
4. Sesuaikan `BUNDLE_ZIP` dengan path Kaggle Dataset, kemudian jalankan semua
   cell. Kedua model dijalankan berurutan dalam subprocess terpisah.
5. Unduh empat file dari `/kaggle/working/cove_stage5/results/`: dua JSONL hasil
   dan dua manifest runtime. Letakkan di `results/runs/` repository lokal.

Backend utama adalah vLLM. Jika vLLM gagal, runner otomatis mencoba Transformers
dengan quantisasi NF4 bitsandbytes dan mencatat model, revision, backend, serta
kuantisasi aktual pada setiap hasil. Cache dibaca dari file output; job yang
sudah selesai tidak dipanggil ulang.

Metode multi-langkah nantinya mengikuti pola yang sama: kode lokal membuat job
langkah berikutnya dari hasil langkah sebelumnya, retrieval tambahan tetap
dijalankan lokal, kemudian job baru dibawa kembali ke Kaggle.

