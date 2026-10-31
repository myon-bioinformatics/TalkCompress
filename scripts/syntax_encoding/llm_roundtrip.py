"""Opt-in local-model experiment with pinned input and append-only JSONL receipts.

Importing this module never imports llama_cpp, opens weights, or runs inference.
Historical #103 numbers used a different protocol and are not re-scored here.
"""
import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

if __package__:
    from .cases import SVOC
else:
    from cases import SVOC

FORMATS = {
    "make happy(him)": lambda s, v, o, c: f"{s} {v} {c}({o}).",
    "make(happy(him))": lambda s, v, o, c: f"{s} {v}({c}({o})).",
    "make him:happy": lambda s, v, o, c: f"{s} {v} {o}:{c}.",
    "make him=happy": lambda s, v, o, c: f"{s} {v} {o}={c}.",
    "make_happy him": lambda s, v, o, c: f"{s} {v}_{c} {o}.",
}
SYSTEM = "Compressed English notation: 'V C(O)' or 'V(C(O))' or 'V O:C' or 'V O=C' or 'V_C O' all mean 'V O C' (e.g. 'I make happy(him).' = 'I make him happy.'). Rewrite the sentence as normal English. Output only the sentence."
MODEL_CONFIG = {"n_ctx": 1024, "seed": 0, "n_threads": 2, "n_gpu_layers": 0, "verbose": False}
GENERATION_CONFIG = {"temperature": 0, "max_tokens": 24}
PROTOCOL = "syntax-roundtrip/2-full-completion"


def sha256_file(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def normalized_words(text):
    # Whole response, not just its first line. ASCII-only synthetic corpus.
    return re.sub(r"[^a-z\s]", "", text.lower()).split()


def inspect_completion(response, gold):
    """Return unscorable rather than a hit for truncated/malformed completions."""
    try:
        choices = response["choices"]
        if len(choices) != 1:
            raise ValueError("expected exactly one choice")
        choice = choices[0]
        reason = choice["finish_reason"]
        content = choice["message"]["content"]
    except (KeyError, IndexError, TypeError, ValueError) as error:
        return {"status": "error", "exact_match": None,
                "error": {"type": type(error).__name__, "message": str(error)}}
    complete = reason == "stop" and isinstance(content, str) and bool(content.strip())
    return {
        "status": "complete" if complete else "incomplete",
        "finish_reason": reason,
        "content": content,
        "exact_match": normalized_words(content) == normalized_words(gold) if complete else None,
    }


def write_record(stream, record):
    stream.write(json.dumps(record, ensure_ascii=False, allow_nan=False) + "\n")
    stream.flush()


def run_experiment(args):
    """Only called after explicit CLI opt-in and successful model preflight."""
    expected = len(SVOC) * len(FORMATS)
    here = Path(__file__).resolve().parent
    model = None
    counts = {"attempted": 0, "complete": 0, "exact_matches": 0, "incomplete": 0, "errors": 0}
    run_error = None
    # Never overwrite historical evidence. Each invocation needs a new filename.
    with args.output.open("x", encoding="utf-8") as stream:
        write_record(stream, {
            "kind": "run", "schema": PROTOCOL, "created_at": datetime.now(timezone.utc).isoformat(),
            "expected_trials": expected,
            "model": {"filename": args.model.name, "bytes": args.model.stat().st_size,
                      "sha256": args.verified_sha256, "expected_sha256": args.model_sha256,
                      "source_caller_stated": args.model_source},
            "python": sys.version,
            "source_sha256": {name: sha256_file(here / name) for name in ("llm_roundtrip.py", "cases.py")},
            "cases_sha256": hashlib.sha256(json.dumps(SVOC, ensure_ascii=False).encode()).hexdigest(),
            "system_prompt": SYSTEM, "system_prompt_sha256": hashlib.sha256(SYSTEM.encode()).hexdigest(),
            "model_config": MODEL_CONFIG, "generation_config": GENERATION_CONFIG,
            "scoring": "finish_reason=stop; nonempty full output; lowercase ASCII word sequence",
        })
        try:
            import llama_cpp
            write_record(stream, {"kind": "runtime", "llama_cpp_python": getattr(llama_cpp, "__version__", "unknown")})
            model = llama_cpp.Llama(model_path=str(args.model), **MODEL_CONFIG)
            write_record(stream, {"kind": "model_metadata", "metadata": getattr(model, "metadata", {}),
                                  "chat_format": getattr(model, "chat_format", None)})
            for name, formatter in FORMATS.items():
                for index, case in enumerate(SVOC):
                    gold = f"{case[0]} {case[1]} {case[2]} {case[3]}."
                    prompt = formatter(*case)
                    row = {"kind": "trial", "notation": name, "case_index": index,
                           "input": prompt, "gold": gold}
                    counts["attempted"] += 1
                    try:
                        response = model.create_chat_completion(
                            [{"role": "system", "content": SYSTEM}, {"role": "user", "content": prompt}],
                            **GENERATION_CONFIG,
                        )
                        # Validate serializability before retaining a malformed provider value.
                        json.dumps(response, allow_nan=False)
                        row["response"] = response
                        row.update(inspect_completion(response, gold))
                    except Exception as error:
                        row.update(status="error", exact_match=None,
                                   error={"type": type(error).__name__, "message": str(error)})
                    if row["status"] == "complete":
                        counts["complete"] += 1
                        counts["exact_matches"] += bool(row["exact_match"])
                    elif row["status"] == "incomplete":
                        counts["incomplete"] += 1
                    else:
                        counts["errors"] += 1
                    write_record(stream, row)
        except Exception as error:
            run_error = {"type": type(error).__name__, "message": str(error)}
            write_record(stream, {"kind": "run_error", **run_error})
        finally:
            if model is not None:
                try:
                    model.close()
                except Exception as error:
                    run_error = {"type": type(error).__name__, "message": str(error)}
                    write_record(stream, {"kind": "shutdown_error", **run_error})
        complete = counts["complete"] == expected and run_error is None
        write_record(stream, {"kind": "summary", **counts, "expected_trials": expected,
                              "complete": complete})
    return 0 if complete else 2


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", action="store_true", help="Explicitly permit local model inference")
    parser.add_argument("--model", type=Path, help="Existing local GGUF; no default or download")
    parser.add_argument("--model-sha256", help="Expected 64-character SHA-256 from trusted model provenance")
    parser.add_argument("--model-source", help="Caller-stated source URL/revision; recorded, never fetched")
    parser.add_argument("--output", type=Path, help="New JSONL evidence path; existing files are rejected")
    args = parser.parse_args(argv)
    if not args.run:
        parser.error("model measurement is manual only; pass --run explicitly")
    if args.model is None or args.output is None or not args.model_sha256 or not args.model_source or not args.model_source.strip():
        parser.error("--model, --model-sha256, --model-source and --output are required with --run")
    if not re.fullmatch(r"[0-9a-fA-F]{64}", args.model_sha256):
        parser.error("--model-sha256 must contain exactly 64 hexadecimal characters")
    args.model_sha256 = args.model_sha256.lower()
    if not args.model.is_file():
        parser.error("--model must be an existing local file")
    if args.output.exists():
        parser.error("--output already exists; historical evidence is never overwritten")
    args.verified_sha256 = sha256_file(args.model)
    if args.verified_sha256 != args.model_sha256:
        parser.error("model SHA-256 mismatch; no model was loaded")
    try:
        return run_experiment(args)
    except OSError as error:
        parser.error(str(error))


if __name__ == "__main__":
    raise SystemExit(main())

