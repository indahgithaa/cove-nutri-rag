"""Validate returned Kaggle result JSONL against its frozen Stage 5 jobs."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.llm import load_llm_config, read_jsonl, validate_result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-key", required=True)
    parser.add_argument("--results", required=True, type=Path)
    args = parser.parse_args()

    config = load_llm_config(ROOT / "configs" / "llm.yaml")
    if args.model_key not in config["models"]:
        raise ValueError(f"Unknown model key: {args.model_key}")
    jobs_path = (
        ROOT
        / config["paths"]["jobs_dir"]
        / f"stage5_smoke_{args.model_key}.jsonl"
    )
    jobs = read_jsonl(jobs_path)
    results = read_jsonl(args.results)
    if len(results) != len(jobs):
        raise ValueError(f"Expected {len(jobs)} results, got {len(results)}")
    result_by_key = {row["cache_key"]: row for row in results}
    if len(result_by_key) != len(results):
        raise ValueError("Duplicate cache keys in results")
    for job in jobs:
        if job["cache_key"] not in result_by_key:
            raise ValueError(f"Missing result for job {job['job_id']}")
        validate_result(result_by_key[job["cache_key"]], job)
    errors = sum(result["error"] is not None for result in results)
    print(
        f"RESULT_VALIDATION=PASS model={args.model_key} "
        f"rows={len(results)} errors={errors}"
    )
    if errors:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
