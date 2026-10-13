# Tahap 3 — Modul Angka dan Validasi Metrik

## Protokol anti-kebocoran

Aturan awal `numbers_v1` dikembangkan menggunakan contoh sintetis dan audit dev.
Sesudah validasi pertama, pemeriksaan contoh **dev** menemukan tiga cacat format:
tanda negatif berspasi, tahun sitasi majemuk, dan operand kedua pola `3x150`.
Audit dev berikutnya menemukan parser masih dapat mulai pada digit kedua kode
alfanumerik (`P97`, `B12`) dan sitasi multi-baris. Koreksi tidak didasarkan pada
contoh atau arah hasil test, dicatat berturut-turut sebagai `numbers_v1.1` dan
`numbers_v1.2`, serta setiap perubahan diikuti rerun validasi penuh. Dua puluh
contoh pemeriksaan tetap berasal dari dev saja.

Sebanyak **104 unit test** lulus pada versi final; jumlah ini melampaui syarat
minimal 30 kasus.

## Aturan yang dibekukan

- Koma adalah desimal: `1705,8 → 1705.8`.
- Titik dengan kelompok tiga digit adalah pemisah ribuan: `1.705,8 → 1705.8`
  dan `2.000 → 2000`.
- Titik lain adalah desimal: `1.5 → 1.5`.
- Persen dipertahankan sebagai poin persentase: `15% → 15`.
- Rentang menghasilkan dua angka; tanda hubung kompak tidak menjadi tanda
  negatif untuk ujung kedua.
- Nomor daftar, halaman berlabel, nomor tunggal satu baris, nomor bagian, tahun
  sitasi berpola jelas, dan komponen kode PES dikecualikan dari angka biasa.
- Kode PES dinormalisasi ke bentuk `NI-2.1`, `NC-4.1`, atau `NB-1.1`.
- Pencocokan menggunakan selisih absolut ≤0,01 atau selisih relatif simetris
  ≤0,5% dengan penyebut nilai absolut terbesar. Unit tidak menjadi bagian dari
  keputusan cocok, sesuai definisi metrik penelitian.

Konfigurasi mesin-baca tersedia di `configs/numbers.yaml` dan implementasi di
`src/numbers.py`.

## Perubahan penanda Tahap 2

- Tahap 2 provisional: **418/858** QA (`stage2_candidate_v1`).
- Validasi pertama sebelum koreksi format dev: **346/858** QA (`numbers_v1`).
- Validasi setelah koreksi pertama: **344/858** QA (`numbers_v1.1`).
- Versi final: **322/858** QA
  (`numbers_v1.2`).
- ID, kebijakan deduplikasi, konteks, dan split tidak berubah pada regenerasi.

## Validasi angka gold

| Split | QA | Jawaban berangka | Kemunculan angka | Ada di laporan | Ada di chunk gold | Semua angka di laporan | Semua angka di chunk |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Dev | 175 | 67 | 777 | 753/777 (96,91%) | 516/777 (66,41%) | 63/67 (94,03%) | 30/67 (44,78%) |
| Test | 683 | 255 | 2868 | 2864/2868 (99,86%) | 1929/2868 (67,26%) | 251/255 (98,43%) | 111/255 (43,53%) |
| Keseluruhan | 858 | 322 | 3645 | 3617/3645 (99,23%) | 2445/3645 (67,08%) | 314/322 (97,52%) | 141/322 (43,79%) |

Secara keseluruhan, proporsi kemunculan angka gold yang ada di laporan adalah
**99,23%** dan
proporsi jawaban berangka yang seluruh angkanya ada di laporan adalah
**97,52%**.
Nilai tersebut dibandingkan dengan temuan pendahuluan sekitar 99% dan 98% tanpa
menjadikannya target optimasi. Cakupan chunk gold adalah
**67,08%**,
dibandingkan perkiraan awal sekitar 76% (selisih
**8,92 poin persentase**). Selisih ini
masuk akal karena parser final mengeluarkan angka sitasi, penomoran, dan
komponen kode PES, sedangkan definisi rinci perhitungan pendahuluan tidak
tersedia. Selain itu, Tahap 2 menetapkan teks corpus chunk sebagai konteks
kanonik. Angka final dipakai apa adanya dan parser tidak dituning ke estimasi
pendahuluan.

### Kategori angka

| Kategori | Dev | Test | Total |
| --- | --- | --- | --- |
| Energi/kkal | 34 | 145 | 179 |
| Persentase | 195 | 738 | 933 |
| Nilai laboratorium | 49 | 231 | 280 |
| Antropometri/z-score | 72 | 216 | 288 |
| Berat/tinggi badan | 18 | 34 | 52 |
| Lainnya | 409 | 1504 | 1913 |

## Validasi kode PES

| Split | Jawaban dengan kode | Kemunculan kode | Ada di laporan | Ada di chunk gold |
| --- | --- | --- | --- | --- |
| Dev | 24 | 95 | 92/95 (96,84%) | 70/95 (73,68%) |
| Test | 89 | 351 | 350/351 (99,72%) | 254/351 (72,36%) |
| Keseluruhan | 113 | 446 | 442/446 (99,10%) | 324/446 (72,65%) |

Kode PES diperlakukan terpisah dari angka biasa. Angka `2` dan `1` dalam
`NI-2.1` tidak masuk ke denominator metrik numerik.

## Keterbatasan

- Penyaringan bersifat konservatif dan tidak menjamin semua nomor regulasi,
  nomor referensi bebas, atau indeks dalam notasi formula terhapus.
- Kategori angka ditentukan dengan heuristik kata sekitar, sehingga kategori
  hanya cocok untuk analisis deskriptif dan bukan label klinis tervalidasi.
- Kecocokan angka sengaja tidak memeriksa kesetaraan unit; metrik ini hanya
  mengukur keberadaan nilai numerik menurut definisi penelitian.
- Perbedaan cakupan chunk dari estimasi awal tidak dapat diatribusikan pada
  satu faktor tanpa artefak dan definisi parser pendahuluan yang lengkap.

## Artefak

- `data/processed/gold_numbers.jsonl`: satu record per QA berisi seluruh mention,
  nilai ternormalisasi, kategori, unit, posisi karakter, dan kode PES.
- `reports/03_number_examples.md`: 20 contoh acak dev untuk pemeriksaan manual.
- File QA olahan diregenerasi dari sumber mentah dengan split yang sama dan
  `number_flag_version=numbers_v1.2`.

## Kesimpulan validasi

Modul memenuhi cakupan format yang diminta dan lulus 104 unit test. Perbedaan
terhadap temuan pendahuluan dilaporkan apa adanya; tidak ada contoh atau arah
hasil test yang digunakan untuk menyesuaikan parser.
