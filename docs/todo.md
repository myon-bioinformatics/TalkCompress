# TODO

- **D (DispatchHub):** 仮置き。後に別名・別責務へ変わりうる。現状は薄いルーター専用（合意台帳は C / ShorthandEdge が所有）。

- **D pytest ≈ 0:** DispatchHub 専用スイートは持たない。層単体は `tests/test_*.py`（A–E）、またぎは `tests/integration/`（結合・総合）。同一ケースの二重断言は層単体 1 箇所＋integration に揃える。`DispatchHub/tests/` は README のみ。

- **B live MT:** `--translate-engine=deep` needs `uv sync --group translate` (`deep-translator`). `argos` is documented but not in the default lock (heavy packs).
