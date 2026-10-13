from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.llm import (
    JOB_SCHEMA_VERSION,
    RESULT_SCHEMA_VERSION,
    build_job,
    load_llm_config,
    load_result_cache,
    merge_results,
    model_fingerprint,
    pending_jobs,
    read_jsonl,
    render_rag_prompt,
    select_smoke_qas,
    stable_hash,
    validate_job,
    validate_result,
    write_jsonl,
)


ROOT = Path(__file__).resolve().parents[1]


def sample_job(**overrides) -> dict:
    values = {
        "qa_id": 7,
        "model_key": "model_a",
        "method": "V",
        "condition": "normal",
        "step": "answer",
        "prompt_version": "vanilla_v1",
        "prompt": "Jawab berdasarkan konteks.",
        "config_fingerprint": "a" * 64,
        "metadata": {"split": "dev", "chunk_ids": ["a", "b", "c"]},
    }
    values.update(overrides)
    return build_job(**values)


def sample_result(job: dict, **overrides) -> dict:
    values = {
        "schema_version": RESULT_SCHEMA_VERSION,
        "job_id": job["job_id"],
        "cache_key": job["cache_key"],
        "qa_id": job["qa_id"],
        "model_key": job["model_key"],
        "model_id": "org/model",
        "revision": "b" * 40,
        "method": job["method"],
        "condition": job["condition"],
        "step": job["step"],
        "prompt_version": job["prompt_version"],
        "text": "Jawaban.",
        "prompt_tokens": 20,
        "completion_tokens": 3,
        "elapsed_seconds": 0.5,
        "backend": "vllm",
        "quantization": "awq",
        "finish_reason": "stop",
        "error": None,
    }
    values.update(overrides)
    return values


def test_llm_config_is_frozen_and_has_two_families() -> None:
    config = load_llm_config(ROOT / "configs" / "llm.yaml")
    assert config["decoding"]["temperature"] == 0
    assert {model["family"] for model in config["models"].values()} == {
        "qwen2.5",
        "mistral",
    }
    assert all(len(model["revision"]) == 40 for model in config["models"].values())


def test_model_fingerprint_is_deterministic_and_model_specific() -> None:
    config = load_llm_config(ROOT / "configs" / "llm.yaml")
    qwen = model_fingerprint("qwen25_7b_awq", config)
    assert qwen == model_fingerprint("qwen25_7b_awq", config)
    assert qwen != model_fingerprint("mistral_7b_v03_bnb4", config)


def test_stable_hash_ignores_dictionary_order() -> None:
    assert stable_hash({"a": 1, "b": 2}) == stable_hash({"b": 2, "a": 1})


def test_prompt_has_exactly_three_labeled_chunks() -> None:
    chunks = [{"text": f"teks {index}"} for index in range(3)]
    prompt = render_rag_prompt("{context}\nQ: {question}", "Apa?", chunks)
    assert all(f"[K{index}]" in prompt for index in (1, 2, 3))
    assert "Q: Apa?" in prompt


def test_prompt_rejects_wrong_chunk_count() -> None:
    with pytest.raises(ValueError, match="exactly three"):
        render_rag_prompt("{context} {question}", "Apa?", [{"text": "satu"}])


def test_job_id_is_stable_but_cache_changes_with_prompt() -> None:
    first = sample_job(prompt="A")
    second = sample_job(prompt="B")
    assert first["job_id"] == second["job_id"]
    assert first["cache_key"] != second["cache_key"]
    assert first["schema_version"] == JOB_SCHEMA_VERSION


def test_job_rejects_evaluation_metadata() -> None:
    with pytest.raises(ValueError, match="evaluation-only"):
        sample_job(metadata={"gold_answer": "rahasia"})


def test_job_jsonl_roundtrip(tmp_path: Path) -> None:
    path = tmp_path / "jobs.jsonl"
    jobs = [sample_job(qa_id=1), sample_job(qa_id=2)]
    write_jsonl(path, jobs)
    assert read_jsonl(path) == jobs


def test_pending_jobs_skips_cached_result() -> None:
    jobs = [sample_job(qa_id=1), sample_job(qa_id=2)]
    cache = {jobs[0]["cache_key"]: sample_result(jobs[0])}
    assert pending_jobs(jobs, cache) == [jobs[1]]


def test_cache_rejects_conflicting_duplicates(tmp_path: Path) -> None:
    job = sample_job()
    path = tmp_path / "results.jsonl"
    first = sample_result(job)
    second = sample_result(job, text="Berbeda")
    path.write_text(
        json.dumps(first) + "\n" + json.dumps(second) + "\n", encoding="utf-8"
    )
    with pytest.raises(ValueError, match="Conflicting"):
        load_result_cache(path)


def test_merge_results_preserves_job_order() -> None:
    jobs = [sample_job(qa_id=2), sample_job(qa_id=1)]
    results = [sample_result(jobs[1]), sample_result(jobs[0])]
    merged = merge_results(jobs, {}, results)
    assert [row["qa_id"] for row in merged] == [2, 1]


def test_result_must_match_job() -> None:
    job = sample_job()
    with pytest.raises(ValueError, match="does not match"):
        validate_result(sample_result(job, qa_id=99), job)


def test_successful_result_requires_text() -> None:
    job = sample_job()
    with pytest.raises(ValueError, match="empty text"):
        validate_result(sample_result(job, text=""), job)


def test_smoke_selection_is_deterministic_and_numeric_only() -> None:
    rows = [
        {"id": index, "has_number": index % 2 == 0} for index in range(20)
    ]
    first = select_smoke_qas(rows, sample_size=5, seed=42, numeric_only=True)
    second = select_smoke_qas(reversed(rows), sample_size=5, seed=42, numeric_only=True)
    assert first == second
    assert all(row["has_number"] for row in first)


def test_notebook_is_valid_and_runs_both_models() -> None:
    notebook_path = ROOT / "notebooks" / "run_llm.ipynb"
    notebook = json.loads(notebook_path.read_text(encoding="utf-8"))
    source = "\n".join(
        line for cell in notebook["cells"] for line in cell.get("source", [])
    )
    assert notebook["nbformat"] == 4
    assert "qwen25_7b_awq" in source
    assert "mistral_7b_v03_bnb4" in source
    assert "privat" in source

