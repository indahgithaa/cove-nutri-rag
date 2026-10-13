"""Create a deterministic private-upload bundle for the Stage 5 smoke test."""

from __future__ import annotations

import hashlib
import json
import sys
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.llm import load_llm_config


CONFIG_PATH = ROOT / "configs" / "llm.yaml"
OUTPUT_PATH = ROOT / "results" / "kaggle" / "stage5_smoke_bundle.zip"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> None:
    config = load_llm_config(CONFIG_PATH)
    jobs_dir = Path(config["paths"]["jobs_dir"])
    paths = [
        Path("notebooks/run_llm.ipynb"),
        Path("notebooks/kaggle_runner.py"),
        Path("notebooks/README.md"),
        Path("notebooks/requirements-kaggle.txt"),
        Path("configs/llm.yaml"),
        Path("src/__init__.py"),
        Path("src/llm.py"),
        jobs_dir / "stage5_smoke_manifest.json",
    ] + [
        jobs_dir / f"stage5_smoke_{model_key}.jsonl"
        for model_key in config["models"]
    ]
    missing = [str(path) for path in paths if not (ROOT / path).exists()]
    if missing:
        raise FileNotFoundError(f"Bundle inputs are missing: {missing}")

    payloads = {
        str(path).replace("\\", "/"): (ROOT / path).read_bytes() for path in paths
    }
    manifest = {
        "privacy": "Upload as a private Kaggle dataset/notebook; do not publish.",
        "files": {
            name: {"bytes": len(data), "sha256": sha256(data)}
            for name, data in sorted(payloads.items())
        },
    }
    payloads["bundle_manifest.json"] = (
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(OUTPUT_PATH, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, data in sorted(payloads.items()):
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, data)
    print(f"BUNDLE={OUTPUT_PATH.relative_to(ROOT)}")
    print(f"FILES={len(payloads)}")
    print(f"BYTES={OUTPUT_PATH.stat().st_size}")
    print(f"SHA256={sha256(OUTPUT_PATH.read_bytes())}")


if __name__ == "__main__":
    main()

