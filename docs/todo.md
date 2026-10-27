# TODO

- **D (DensityZip):** 決定名（2026-10-27）。旧仮名 DispatchHub から改称。横断オーケストレーション + density 指標ファサード（Hub は使わない）。合意台帳は C / ShorthandEdge が所有。Zipilogue (A) / MorphoZip (E) と名前を混同しない。

- **D pytest ≈ 0:** DensityZip 専用スイートは持たない。層単体は `tests/test_*.py`（A–E）、またぎは `tests/integration/`（結合・総合）。同一ケースの二重断言は層単体 1 箇所＋integration に揃える。`DensityZip/tests/` は README のみ。

- **B live MT:** `--translate-engine=deep` needs `uv sync --group translate` (`deep-translator`). `argos` is documented but not in the default lock (heavy packs).

- **A Zipilogue 実験方針（2026-10-27）:** 軽量ローカルモデル（**llama.cpp または同等の軽量 GGUF** スタック；同クラス。既定では重いフル精度サーバは使わない）で継続会話を回し、間隔をおいてエージェントが独自の共有表現・スラング（RuleBook 成長）を発明するかを観察する。二者だけの脆い構成より、**複数エージェントを並列のグループ**として回す方を優先。実装（ランナー等）は未着手・方針メモのみ。


- [ ] E 前置詞 for→`4`: 数字 four との揺らぎを在庫ビットとは別に評価。`for` へ戻すか検討（現状 `4`）。
