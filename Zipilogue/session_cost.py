"""Account for shared-dictionary setup and recovery over a whole session.

No tokenizer or model is loaded. Supply the target tokenizer's count callable
to measure tokens; the default explicitly measures UTF-8 bytes.
"""
from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass
import json

from .rulebook import RuleBook


def utf8_bytes(text: str) -> int:
    return len(text.encode("utf-8"))


@dataclass(frozen=True)
class TurnCost:
    original: int
    encoded: int
    recovery: int
    exact_roundtrip: bool


def measure_session(
    book: RuleBook,
    messages: Sequence[str],
    *,
    count: Callable[[str], int] = utf8_bytes,
    unit: str = "utf8_bytes",
    recovery_messages: Sequence[str] | None = None,
) -> dict:
    """Measure a frozen rulebook, sent once, followed by encoded messages.

Recovery messages are actual caller-supplied retransmissions (one per turn,
empty when absent). A failed exact roundtrip is reported, never counted as
successful merely because the encoded payload is short. Counts are per
message, without transport framing; token callbacks must use unit='tokens'.
The dictionary is the compact export JSON, including its metadata. This is
an offline accounting experiment, not an LLM quality or transport benchmark.
"""
    if recovery_messages is None:
        recovery_messages = [""] * len(messages)
    if len(recovery_messages) != len(messages):
        raise ValueError("one recovery message is required per turn")

    def cost(text: str) -> int:
        value = count(text)
        if type(value) is not int or value < 0:
            raise ValueError("count must return a nonnegative integer")
        return value

    # Snapshot: neither observation nor auto-adoption changes the experiment.
    payload = book.export_rules()
    wire = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    peer = RuleBook(auto_adopt=False)
    peer.import_rules(json.loads(wire), merge=False)
    setup = cost(wire)
    turns = []
    raw_total = 0
    compressed_total = setup
    break_even = None
    exact = True
    for index, (text, recovery) in enumerate(zip(messages, recovery_messages), 1):
        encoded = book.encode_with_rules(text)
        turn = TurnCost(cost(text), cost(encoded), cost(recovery),
                        peer.decode_with_rules(encoded) == text)
        turns.append(asdict(turn))
        raw_total += turn.original
        compressed_total += turn.encoded + turn.recovery
        exact = exact and turn.exact_roundtrip
        if break_even is None and compressed_total < raw_total:
            break_even = index
    return {
        "unit": unit,
        "setup": setup,
        "turns": turns,
        "original_total": raw_total,
        "compressed_total": compressed_total,
        "net_saved": raw_total - compressed_total,
        "first_saving_turn": break_even,
        "exact_roundtrip": exact,
        "beneficial": exact and compressed_total < raw_total,
    }


def main() -> None:
    """Small reproducible tile/dictionary reuse experiment."""
    book = RuleBook(auto_adopt=False)
    phrase = "please run the regression tests before merging"
    book.declare(phrase, "r1")
    messages = [phrase] * 32
    print(json.dumps({
        "one_turn": measure_session(book, messages[:1]),
        "repeated": measure_session(book, messages),
        "with_recovery": measure_session(
            book, messages, recovery_messages=[phrase] * len(messages)),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
