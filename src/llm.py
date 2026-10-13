"""Model-agnostic LLM job, result, and cache utilities."""

from __future__ import annotations

import hashlib
import json
import random
from pathlib import Path
from typing import Iterable, Mapping, Sequence

import yaml


LLM_CONFIG_VERSION = "llm_v1"
JOB_SCHEMA_VERSION = "llm_job_v1"
RESULT_SCHEMA_VERSION = "llm_result_v1"

JOB_REQUIRED = {
    "schema_version",
    "job_id",
    "cache_key",
    "qa_id",
    "model_key",
    "method",
    "condition",
    "step",
    "prompt_version",
    "prompt",
    "config_fingerprint",
    "metadata",
}
RESULT_REQUIRED = {
    "schema_version",
    "job_id",
    "cache_key",
    "qa_id",
    "model_key",
    "model_id",
    "revision",
    "method",
    "condition",
    "step",
    "prompt_version",
    "text",
    "prompt_tokens",
    "completion_tokens",
    "elapsed_seconds",
    "backend",
    "quantization",
    "finish_reason",
    "error",
}


def canonical_json(payload: object) -> str:
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def stable_hash(payload: object) -> str:
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


def load_llm_config(path: Path) -> dict:
    config = yaml.safe_load(path.read_text(encoding="utf-8"))
    if config["version"] != LLM_CONFIG_VERSION:
        raise ValueError(
            f"Unsupported LLM config {config['version']!r}; "
            f"expected {LLM_CONFIG_VERSION!r}"
        )
    if config["seed"] != config["decoding"]["seed"]:
        raise ValueError("Top-level and decoding seeds must match")
    if config["decoding"]["temperature"] != 0:
        raise ValueError("The frozen experiment requires temperature=0")
    if len(config["models"]) != 2:
        raise ValueError("Exactly two smoke-test models are required")
    for key, model in config["models"].items():
        if model["revision"] == "main" or len(model["revision"]) != 40:
            raise ValueError(f"Model {key!r} must use a 40-character revision")
        if model["gated"]:
            raise ValueError(f"Model {key!r} must not be gated")
        if model["license"] != "apache-2.0":
            raise ValueError(f"Unexpected model license for {key!r}")
    return config


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def write_jsonl(path: Path, rows: Iterable[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = "".join(canonical_json(row) + "\n" for row in rows)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(text, encoding="utf-8", newline="\n")
    temporary.replace(path)


def render_rag_prompt(template: str, question: str, chunks: Sequence[dict]) -> str:
    if len(chunks) != 3:
        raise ValueError(f"RAG prompt requires exactly three chunks, got {len(chunks)}")
    context = "\n\n".join(
        f"[K{index}] {chunk['text'].strip()}"
        for index, chunk in enumerate(chunks, start=1)
    )
    return template.format(context=context, question=question.strip()).strip()


def model_fingerprint(model_key: str, config: Mapping) -> str:
    return stable_hash(
        {
            "version": config["version"],
            "model_key": model_key,
            "model": config["models"][model_key],
            "decoding": config["decoding"],
            "engine": config["engine"],
        }
    )


def build_job(
    *,
    qa_id: int,
    model_key: str,
    method: str,
    condition: str,
    step: str,
    prompt_version: str,
    prompt: str,
    config_fingerprint: str,
    metadata: dict,
) -> dict:
    identity = {
        "qa_id": qa_id,
        "model_key": model_key,
        "method": method,
        "condition": condition,
        "step": step,
        "prompt_version": prompt_version,
    }
    job_id = stable_hash(identity)[:24]
    cache_key = stable_hash(
        {
            **identity,
            "job_id": job_id,
            "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
            "config_fingerprint": config_fingerprint,
        }
    )
    job = {
        "schema_version": JOB_SCHEMA_VERSION,
        "job_id": job_id,
        "cache_key": cache_key,
        **identity,
        "prompt": prompt,
        "config_fingerprint": config_fingerprint,
        "metadata": metadata,
    }
    validate_job(job)
    return job


def validate_job(job: Mapping) -> None:
    missing = JOB_REQUIRED - set(job)
    if missing:
        raise ValueError(f"Job is missing fields: {sorted(missing)}")
    if job["schema_version"] != JOB_SCHEMA_VERSION:
        raise ValueError("Unsupported job schema")
    if not isinstance(job["qa_id"], int) or not job["prompt"].strip():
        raise ValueError("Job qa_id and prompt are invalid")
    forbidden = {"gold_answer", "dataset_context", "gold_chunk_id", "qrel"}
    if forbidden & set(job["metadata"]):
        raise ValueError("Job metadata contains evaluation-only fields")


def validate_result(result: Mapping, job: Mapping | None = None) -> None:
    missing = RESULT_REQUIRED - set(result)
    if missing:
        raise ValueError(f"Result is missing fields: {sorted(missing)}")
    if result["schema_version"] != RESULT_SCHEMA_VERSION:
        raise ValueError("Unsupported result schema")
    if result["prompt_tokens"] < 0 or result["completion_tokens"] < 0:
        raise ValueError("Token counts cannot be negative")
    if result["elapsed_seconds"] < 0:
        raise ValueError("Elapsed time cannot be negative")
    if result["error"] is None and not result["text"].strip():
        raise ValueError("Successful result cannot contain empty text")
    if job is not None:
        for field in (
            "job_id",
            "cache_key",
            "qa_id",
            "model_key",
            "method",
            "condition",
            "step",
            "prompt_version",
        ):
            if result[field] != job[field]:
                raise ValueError(f"Result field {field!r} does not match job")


def load_result_cache(path: Path) -> dict[str, dict]:
    cache: dict[str, dict] = {}
    for result in read_jsonl(path):
        validate_result(result)
        key = result["cache_key"]
        if key in cache and cache[key] != result:
            raise ValueError(f"Conflicting cached results for {key}")
        cache[key] = result
    return cache


def pending_jobs(jobs: Sequence[dict], cache: Mapping[str, dict]) -> list[dict]:
    for job in jobs:
        validate_job(job)
    return [job for job in jobs if job["cache_key"] not in cache]


def merge_results(
    jobs: Sequence[dict], cache: Mapping[str, dict], new_results: Iterable[dict]
) -> list[dict]:
    merged = dict(cache)
    job_by_key = {job["cache_key"]: job for job in jobs}
    for result in new_results:
        key = result["cache_key"]
        if key not in job_by_key:
            raise ValueError(f"Result does not belong to the job file: {key}")
        validate_result(result, job_by_key[key])
        merged[key] = result
    missing = [job["job_id"] for job in jobs if job["cache_key"] not in merged]
    if missing:
        raise ValueError(f"Jobs still missing results: {missing}")
    return [merged[job["cache_key"]] for job in jobs]


def select_smoke_qas(
    rows: Sequence[dict], *, sample_size: int, seed: int, numeric_only: bool
) -> list[dict]:
    eligible = [row for row in rows if not numeric_only or row["has_number"]]
    eligible.sort(key=lambda row: row["id"])
    if len(eligible) < sample_size:
        raise ValueError("Not enough eligible QA rows for smoke test")
    selected = random.Random(seed).sample(eligible, sample_size)
    return sorted(selected, key=lambda row: row["id"])

