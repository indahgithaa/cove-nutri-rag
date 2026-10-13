# CoVe Nutri-RAG

Kode penelitian untuk mengevaluasi Retrieval-Grounded Chain-of-Verification
(RG-CoVe) dalam mitigasi halusinasi numerik pada sistem question answering
asuhan gizi klinis berbasis RAG.

## Setup lokal (Windows PowerShell)

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pytest
```

Data klinis, keluaran eksperimen, model, rahasia, dan cache tidak dilacak Git.
Instruksi pipeline lengkap akan ditambahkan setelah tahap implementasi terkait
selesai dan disetujui.

