"""Prepare deterministic Stage 5 smoke-test jobs for both models."""

from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.llm import (
    build_job,
    canonical_json,
    load_llm_config,
    model_fingerprint,
    read_jsonl,
    render_rag_prompt,
    select_smoke_qas,
    stable_hash,
    write_jsonl,
)


CONFIG_PATH = ROOT / "configs" / "llm.yaml"


def main() -> None:
    config = load_llm_config(CONFIG_PATH)
    paths = config["paths"]
    qas = read_jsonl(ROOT / paths["dev_qa"])
    contexts = {
        row["id"]: row for row in read_jsonl(ROOT / paths["dev_contexts"])
    }
    template = (ROOT / paths["prompt"]).read_text(encoding="utf-8")
    smoke = config["smoke_test"]
    selected = select_smoke_qas(
        qas,
        sample_size=int(smoke["sample_size"]),
        seed=int(smoke["seed"]),
        numeric_only=bool(smoke["numeric_only"]),
    )
    jobs_dir = ROOT / paths["jobs_dir"]
    manifest = {
        "config_version": config["version"],
        "selection": {
            "split": smoke["split"],
            "condition": smoke["condition"],
            "numeric_only": smoke["numeric_only"],
            "seed": smoke["seed"],
            "qa_ids": [qa["id"] for qa in selected],
        },
        "models": {},
    }

    for model_key in config["models"]:
        fingerprint = model_fingerprint(model_key, config)
        jobs = []
        for qa in selected:
            context = contexts[qa["id"]]
            if context["condition"] != smoke["condition"]:
                raise AssertionError("Smoke context condition does not match config")
            prompt = render_rag_prompt(
                template, qa["question"], context["chunks"]
            )
            jobs.append(
                build_job(
                    qa_id=qa["id"],
                    model_key=model_key,
                    method=smoke["method"],
                    condition=smoke["condition"],
                    step="answer",
                    prompt_version="vanilla_v1",
                    prompt=prompt,
                    config_fingerprint=fingerprint,
                    metadata={
                        "split": qa["split"],
                        "question_type": qa["question_type"],
                        "source_context_file": Path(paths["dev_contexts"]).name,
                        "chunk_ids": [chunk["chunk_id"] for chunk in context["chunks"]],
                    },
                )
            )
        output = jobs_dir / f"stage5_smoke_{model_key}.jsonl"
        write_jsonl(output, jobs)
        manifest["models"][model_key] = {
            "job_file": str(output.relative_to(ROOT)).replace("\\", "/"),
            "jobs": len(jobs),
            "model_fingerprint": fingerprint,
            "jobs_sha256": stable_hash(jobs),
        }

    manifest_path = jobs_dir / "stage5_smoke_manifest.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(f"SMOKE_QA_IDS={manifest['selection']['qa_ids']}")
    for model_key, details in manifest["models"].items():
        print(
            f"{model_key}: jobs={details['jobs']} "
            f"sha256={details['jobs_sha256']}"
        )
    print(f"MANIFEST={manifest_path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()

