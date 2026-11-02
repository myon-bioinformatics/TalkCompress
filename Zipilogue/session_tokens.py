"""Compare UTF-8 and GGUF-tokenizer session costs; never infer task quality.

Run from the repository root. See docs/session-token-cost.md for provenance and
message-boundary policy. Runtime uses only the Python standard library.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import urllib.request

from scripts.fetch_l3_model import prepare
from .rulebook import RuleBook
from .session_cost import measure_session


class LlamaTokenizer:
    """llama.cpp /tokenize adapter with an auditable, per-text token-ID cache."""

    def __init__(self, url: str, timeout: float = 30):
        self.url = url
        self.timeout = timeout
        self.records: dict[str, list[int]] = {}

    def __call__(self, text: str) -> int:
        if text not in self.records:
            body = json.dumps({"content": text, "add_special": False,
                               "parse_special": False, "with_pieces": False}).encode("utf-8")
            req = urllib.request.Request(self.url, data=body,
                                         headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                payload = json.load(response)
            tokens = payload.get("tokens")
            if not isinstance(tokens, list) or any(type(t) is not int or t < 0 for t in tokens):
                raise ValueError("/tokenize must return a list of nonnegative integer token IDs")
            if not text and tokens:
                raise ValueError("empty text must cost zero without special tokens")
            self.records[text] = tokens
        return len(self.records[text])


def comparison(book: RuleBook, messages: list[str], count) -> dict:
    """Both units use identical frozen rules, message order, and retry policy."""
    result = {}
    for unit, counter in (("utf8_bytes", None), ("tokens", count)):
        options = {} if counter is None else {"count": counter, "unit": unit}
        scenarios = {}
        for name, texts, retries in (
            ("one_turn", messages[:1], None),
            ("repeated", messages, None),
            ("full_resend", messages, messages),
        ):
            report = measure_session(book, texts, recovery_messages=retries, **options)
            report["encoded_total"] = sum(t["encoded"] for t in report["turns"])
            report["recovery_total"] = sum(t["recovery"] for t in report["turns"])
            scenarios[name] = report
        result[unit] = scenarios
    return result


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--fixture", type=Path, default=Path("examples/session-cost.json"))
    parser.add_argument("--model", default="qwen-0.5b")
    parser.add_argument("--model-path", type=Path, required=True)
    parser.add_argument("--runtime-id", required=True, help="pinned llama.cpp commit or image digest")
    parser.add_argument("--url", default="http://127.0.0.1:8080/tokenize")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    fixture_bytes = args.fixture.read_bytes()
    fixture = json.loads(fixture_bytes)
    book = RuleBook(auto_adopt=False)
    for long, short in fixture["rules"]:
        book.declare(long, short)
    messages = fixture["messages"]
    if not isinstance(messages, list) or not messages or any(not isinstance(t, str) for t in messages):
        parser.error("fixture messages must be a nonempty list of strings")
    report = {
        "schema_version": 1,
        "dataset_origin": "synthetic fixed messages; real tokenizer counts only",
        "implementation_sha256": {
            name: hashlib.sha256(Path(name).read_bytes()).hexdigest()
            for name in ("Zipilogue/session_tokens.py", "Zipilogue/session_cost.py",
                         "Zipilogue/rulebook.py", "shared/l3_models.json")
        },
        "status": "unmeasured",
        "fixture_sha256": hashlib.sha256(fixture_bytes).hexdigest(),
        "fixture": fixture,
        "model_id": args.model,
        "runtime_id": args.runtime_id,
        "endpoint": args.url,
        "policy": {"add_special": False, "parse_special": False,
                   "boundaries": "dictionary and each message/retransmission tokenized separately",
                   "excludes": ["chat template", "history replay", "transport headers", "generation"]},
        "semantic_understanding": {"status": "unmeasured", "success_rate": None},
        "task_success": {"status": "unmeasured", "success_rate": None},
        "costs": None,
    }
    tokenizer = LlamaTokenizer(args.url)
    code = 1
    try:
        report["model_provenance"] = prepare(args.model, args.model_path)
        report["costs"] = comparison(book, messages, tokenizer)
        report["status"] = "measured"
        code = 0
    except (Exception, SystemExit) as exc:
        report["error"] = f"{type(exc).__name__}: {exc}"
    finally:
        report["tokenizations"] = [{"text": text, "ids": ids} for text, ids in tokenizer.records.items()]
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
