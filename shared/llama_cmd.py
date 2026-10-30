"""Answer command for qa_fidelity (G4): prompt on stdin, answer on stdout.

Talks to a local llama.cpp server (``llama-server``) through its OpenAI-compatible
chat endpoint. Stdlib only, no API key, no network beyond the local host.

Start the server yourself, for example::

    llama-server -m /path/to/model.gguf --port 8080

Then pass this script to qa_fidelity::

    uv run python shared/qa_fidelity.py --source src.txt --compressed out.txt \\
        --cmd "uv run python shared/llama_cmd.py"

Set ``LLAMA_URL`` to change the endpoint (default ``http://127.0.0.1:8080/v1/chat/completions``).
"""

from __future__ import annotations

import json
import os
import sys
import urllib.request

DEFAULT_URL = "http://127.0.0.1:8080/v1/chat/completions"


def ask_llama(prompt: str, url: str = DEFAULT_URL, timeout: int = 300) -> str:
    body = json.dumps(
        {
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0,
            "max_tokens": 128,
            "stream": False,
        }
    ).encode("utf-8")
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    return str(payload["choices"][0]["message"]["content"]).strip()


def main() -> int:
    prompt = sys.stdin.read()
    url = os.environ.get("LLAMA_URL", DEFAULT_URL)
    sys.stdout.write(ask_llama(prompt, url))
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
