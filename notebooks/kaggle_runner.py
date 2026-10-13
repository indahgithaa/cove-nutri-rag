"""Run one model's JSONL jobs on Kaggle with resumable result caching."""

from __future__ import annotations

import argparse
import gc
import json
import sys
import time
import traceback
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.llm import (
    RESULT_SCHEMA_VERSION,
    load_llm_config,
    load_result_cache,
    merge_results,
    pending_jobs,
    read_jsonl,
    validate_job,
    write_jsonl,
)


def chat_prompts(tokenizer, jobs: list[dict]) -> list[str]:
    return [
        tokenizer.apply_chat_template(
            [{"role": "user", "content": job["prompt"]}],
            tokenize=False,
            add_generation_prompt=True,
        )
        for job in jobs
    ]


def result_record(
    job: dict,
    *,
    model_id: str,
    revision: str,
    text: str,
    prompt_tokens: int,
    completion_tokens: int,
    elapsed_seconds: float,
    backend: str,
    quantization: str,
    finish_reason: str,
    error: str | None = None,
    batch_elapsed_seconds: float | None = None,
) -> dict:
    result = {
        "schema_version": RESULT_SCHEMA_VERSION,
        "job_id": job["job_id"],
        "cache_key": job["cache_key"],
        "qa_id": job["qa_id"],
        "model_key": job["model_key"],
        "model_id": model_id,
        "revision": revision,
        "method": job["method"],
        "condition": job["condition"],
        "step": job["step"],
        "prompt_version": job["prompt_version"],
        "text": text,
        "prompt_tokens": int(prompt_tokens),
        "completion_tokens": int(completion_tokens),
        "elapsed_seconds": round(float(elapsed_seconds), 6),
        "backend": backend,
        "quantization": quantization,
        "finish_reason": finish_reason,
        "error": error,
    }
    if batch_elapsed_seconds is not None:
        result["batch_elapsed_seconds"] = round(float(batch_elapsed_seconds), 6)
        result["time_measurement"] = "amortized_batch_time"
    else:
        result["time_measurement"] = "per_request_wall_time"
    return result


def run_vllm(jobs: list[dict], model: dict, config: dict) -> list[dict]:
    from transformers import AutoTokenizer
    from vllm import LLM, SamplingParams

    tokenizer = AutoTokenizer.from_pretrained(
        model["tokenizer_id"],
        revision=model["tokenizer_revision"],
        trust_remote_code=bool(config["engine"]["trust_remote_code"]),
    )
    prompts = chat_prompts(tokenizer, jobs)
    engine_args = {
        "model": model["model_id"],
        "revision": model["revision"],
        "tokenizer": model["tokenizer_id"],
        "tokenizer_revision": model["tokenizer_revision"],
        "quantization": model["quantization"],
        "dtype": config["engine"]["dtype"],
        "gpu_memory_utilization": float(config["engine"]["gpu_memory_utilization"]),
        "max_model_len": int(config["decoding"]["max_model_len"]),
        "seed": int(config["decoding"]["seed"]),
        "trust_remote_code": bool(config["engine"]["trust_remote_code"]),
        "enforce_eager": True,
        "disable_log_stats": True,
        "max_num_seqs": len(jobs),
    }
    if model["load_format"] != "auto":
        engine_args["load_format"] = model["load_format"]
    llm = LLM(**engine_args)
    sampling = SamplingParams(
        temperature=float(config["decoding"]["temperature"]),
        top_p=float(config["decoding"]["top_p"]),
        max_tokens=int(config["decoding"]["max_new_tokens"]),
        seed=int(config["decoding"]["seed"]),
    )
    started = time.perf_counter()
    outputs = llm.generate(prompts, sampling, use_tqdm=True)
    elapsed = time.perf_counter() - started
    amortized = elapsed / len(jobs)
    results = []
    for job, output in zip(jobs, outputs):
        candidate = output.outputs[0]
        results.append(
            result_record(
                job,
                model_id=model["model_id"],
                revision=model["revision"],
                text=candidate.text.strip(),
                prompt_tokens=len(output.prompt_token_ids),
                completion_tokens=len(candidate.token_ids),
                elapsed_seconds=amortized,
                batch_elapsed_seconds=elapsed,
                backend="vllm",
                quantization=model["quantization"],
                finish_reason=candidate.finish_reason or "unknown",
            )
        )
    del llm
    gc.collect()
    return results


def run_transformers(jobs: list[dict], model: dict, config: dict) -> list[dict]:
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

    model_id = model["fallback_model_id"]
    revision = model["fallback_revision"]
    tokenizer = AutoTokenizer.from_pretrained(
        model_id,
        revision=revision,
        trust_remote_code=bool(config["engine"]["trust_remote_code"]),
    )
    quantization = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.float16,
        bnb_4bit_use_double_quant=True,
    )
    llm = AutoModelForCausalLM.from_pretrained(
        model_id,
        revision=revision,
        device_map="auto",
        torch_dtype=torch.float16,
        quantization_config=quantization,
        trust_remote_code=bool(config["engine"]["trust_remote_code"]),
    )
    llm.eval()
    results = []
    for job, prompt in zip(jobs, chat_prompts(tokenizer, jobs)):
        encoded = tokenizer(prompt, return_tensors="pt").to(llm.device)
        started = time.perf_counter()
        with torch.inference_mode():
            generated = llm.generate(
                **encoded,
                do_sample=False,
                max_new_tokens=int(config["decoding"]["max_new_tokens"]),
                pad_token_id=tokenizer.eos_token_id,
            )
        elapsed = time.perf_counter() - started
        new_tokens = generated[0, encoded["input_ids"].shape[1] :]
        text = tokenizer.decode(new_tokens, skip_special_tokens=True).strip()
        finish_reason = (
            "length"
            if len(new_tokens) >= int(config["decoding"]["max_new_tokens"])
            else "stop"
        )
        results.append(
            result_record(
                job,
                model_id=model_id,
                revision=revision,
                text=text,
                prompt_tokens=int(encoded["input_ids"].shape[1]),
                completion_tokens=int(len(new_tokens)),
                elapsed_seconds=elapsed,
                backend="transformers",
                quantization=model["fallback_quantization"],
                finish_reason=finish_reason,
            )
        )
    del llm
    gc.collect()
    torch.cuda.empty_cache()
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--jobs", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--model-key", required=True)
    parser.add_argument(
        "--backend", choices=("auto", "vllm", "transformers"), default="auto"
    )
    args = parser.parse_args()

    config = load_llm_config(args.config)
    if args.model_key not in config["models"]:
        raise ValueError(f"Unknown model key: {args.model_key}")
    model = config["models"][args.model_key]
    jobs = read_jsonl(args.jobs)
    if not jobs:
        raise ValueError("Job file is empty")
    for job in jobs:
        validate_job(job)
        if job["model_key"] != args.model_key:
            raise ValueError("Job model key does not match requested model")

    cache = load_result_cache(args.output)
    pending = pending_jobs(jobs, cache)
    print(f"jobs={len(jobs)} cached={len(jobs)-len(pending)} pending={len(pending)}")
    if not pending:
        print("All jobs already cached; no inference performed.")
        return

    preferred = config["engine"]["preferred_backend"]
    requested = preferred if args.backend == "auto" else args.backend
    try:
        if requested == "vllm":
            generated = run_vllm(pending, model, config)
        else:
            generated = run_transformers(pending, model, config)
    except Exception:
        if args.backend != "auto" or requested == "transformers":
            raise
        print("vLLM failed; switching to the configured Transformers fallback.")
        traceback.print_exc()
        gc.collect()
        try:
            import torch

            torch.cuda.empty_cache()
        except Exception:
            pass
        generated = run_transformers(pending, model, config)

    complete = merge_results(jobs, cache, generated)
    write_jsonl(args.output, complete)
    runtime = {
        "model_key": args.model_key,
        "jobs": len(jobs),
        "cached_before_run": len(jobs) - len(pending),
        "generated_this_run": len(generated),
        "backend": sorted({row["backend"] for row in complete}),
        "model_ids": sorted({row["model_id"] for row in complete}),
        "revisions": sorted({row["revision"] for row in complete}),
        "prompt_tokens": sum(row["prompt_tokens"] for row in complete),
        "completion_tokens": sum(row["completion_tokens"] for row in complete),
        "elapsed_seconds_sum": round(
            sum(row["elapsed_seconds"] for row in complete), 6
        ),
    }
    runtime_path = args.output.with_suffix(".runtime.json")
    runtime_path.write_text(
        json.dumps(runtime, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps(runtime, ensure_ascii=False, indent=2))
    print(f"RESULTS={args.output}")


if __name__ == "__main__":
    main()

