# Verifikasi Model Tahap 5

Verifikasi dilakukan pada 13 Oktober 2026 melalui metadata Hugging Face tanpa
mengunduh bobot model.

| Model | Revision | Kuantisasi utama | Lisensi | Gated |
| --- | --- | --- | --- | --- |
| `Qwen/Qwen2.5-7B-Instruct-AWQ` | `b25037543e9394b818fdfca67ab2a00ecc7dd641` | AWQ 4-bit | Apache-2.0 | Tidak |
| `mistralai/Mistral-7B-Instruct-v0.3` | `c170c708c41dac9275d15a8fff4eca08d52bab71` | bitsandbytes 4-bit saat load | Apache-2.0 | Tidak |

Fallback Qwen memakai `Qwen/Qwen2.5-7B-Instruct` revision
`a09a35458c702b33eeacc393d103063234e8bc28` dengan NF4 bitsandbytes. Fallback
Mistral memakai model/revision yang sama dengan konfigurasi utama dan NF4.

Sumber:

- https://huggingface.co/Qwen/Qwen2.5-7B-Instruct-AWQ
- https://huggingface.co/Qwen/Qwen2.5-7B-Instruct
- https://huggingface.co/mistralai/Mistral-7B-Instruct-v0.3
- https://docs.vllm.ai/en/v0.8.5/features/quantization/supported_hardware.html
- https://docs.vllm.ai/en/v0.8.5.post1/serving/engine_args.html

AWQ dan bitsandbytes didukung vLLM 0.8.5 pada arsitektur Turing, yaitu kelas GPU
yang mencakup T4. Seluruh decoding memakai temperature 0, seed 42, dan maksimum
256 token keluaran; konteks model dibatasi 4096 token agar sesuai memori T4.

