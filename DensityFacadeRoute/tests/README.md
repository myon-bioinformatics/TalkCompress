# DensityFacadeRoute tests

**D 所有の pytest は実質ゼロ。**

- 層単体 → リポ直下 `tests/test_*.py`（A/B/C/E）
- D の CLI 回帰（`--hist-state` / `--final-zh-de` と `--mode` / 改行）→ `tests/test_density_facade_route.py`
- 層またぎ（pipeline / compare / budget / window / …）→ `tests/integration/`（結合・総合）

このディレクトリにテストモジュールは置かない。
