"""Answer command for qa_fidelity (G4): prompt on stdin, answer on stdout.

Talks to a local llama.cpp server (``llama-server``) through its OpenAI-compatible
chat endpoint. Stdlib only, no API key. The default endpoint is localhost.
Only finish_reason=stop with nonempty final text is accepted; truncated or
reasoning-only responses fail explicitly rather than being scored as answers.

Start the server yourself, for example::

    llama-server -m /path/to/model.gguf --port 8080

Then pass this script to qa_fidelity::

    uv run python shared/qa_fidelity.py --source src.txt --compressed out.txt \\
        --cmd "uv run python shared/llama_cmd.py"

Set ``LLAMA_URL`` to change the endpoint (default ``http://127.0.0.1:8080/v1/chat/completions``).
Set ``LLAMA_MAX_TOKENS`` to change the answer limit (default 128). A limit hit
shows up as finish_reason=length and is rejected, not scored.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

try:
    from shared.qa_fidelity import final_answer
except ImportError:
    from qa_fidelity import final_answer

DEFAULT_URL = "http://127.0.0.1:8080/v1/chat/completions"


class AnswerValidationError(ValueError):
    """A valid response carried no completed textual answer (CLI exit 3)."""


def extract_answer(payload: dict) -> str:
    """Reject unfinished, missing or non-text answers before scoring."""
    choice = payload["choices"][0]
    reason = choice["finish_reason"]
    if reason in ("length", "content_filter", "tool_calls", "function_call"):
        raise AnswerValidationError(f"answer did not complete: {reason!r}")
    if reason != "stop":
        raise ValueError(f"unexpected finish_reason: {reason!r}")
    content = choice["message"]["content"]
    if content is None:
        raise AnswerValidationError("no completed final answer")
    if not isinstance(content, str):
        raise ValueError("answer content must be text")
    answer = final_answer(content)
    if not answer:
        raise AnswerValidationError("no completed final answer")
    return answer


def ask_llama(prompt: str, url: str = DEFAULT_URL, timeout: int = 300) -> str:
    body = json.dumps(
        {
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0,
            "max_tokens": int(os.environ.get("LLAMA_MAX_TOKENS", "128")),
            "stream": False,
        }
    ).encode("utf-8")
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    return extract_answer(payload)


def main() -> int:
    prompt = sys.stdin.read()
    url = os.environ.get("LLAMA_URL", DEFAULT_URL)
    timeout = int(os.environ.get("LLAMA_TIMEOUT", "300"))  # long answers on CPU can exceed 5 minutes
    try:
        answer = ask_llama(prompt, url, timeout=timeout)
    except AnswerValidationError as exc:
        sys.stderr.write(f"answer validation failed: {exc}\n")
        return 3
    except (urllib.error.URLError, TimeoutError) as exc:  # server not running or not reachable: a measurement failure
        sys.stderr.write(f"llama-server unreachable: {getattr(exc, 'reason', str(exc))}\n")
        return 2
    sys.stdout.write(answer)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

