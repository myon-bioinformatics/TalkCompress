"""結合・総合テスト（cross-layer）。

DispatchHub (D) は仮の薄いルーターであり、**D 専用の pytest スイートは持たない**。
ここにあるのは「またぎ」（pipeline C→E、compare、budget/window/profile/auto、
CLI 配線など）を測るプロジェクト級の結合・総合テスト。

層単体の断言は `tests/test_*.py`（A/B/C/E）および各サブプロジェクト側へ。
"""
