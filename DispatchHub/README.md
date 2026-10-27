# DispatchHub（D）

語源: *dispatch*（振り分け）+ *hub*（横断の結節点）。層横断のルーター。

> **TODO（仮置き）:** 名前・責務とも provisional。後に別名・別責務へ変わりうる。現状は薄いオーケストレーション専用。

**横断オーケストレーションのみ。** 層の選択と共通入出力の表玄関。合意台帳（ledger）は持たない — ソース・オブ・トゥルースは [ShorthandEdge/ledger](../ShorthandEdge/ledger/)（C が適用）。

## ルーティング

| 指定 | 行き先 |
| --- | --- |
| `1` / `A` / `zipilogue` | Zipilogue |
| `2` / `B` / `tessera` | TesseraTalk |
| `3` / `C` / `shorthand` / `shorthand_edge` | ShorthandEdge |
| `4` / `E` / `morpho` | MorphoZip |
| `D` / `dispatch` / `dispatch_hub` | このルーター自身（pipeline には入れない） |

## 使い方

```bash
# テキスト
uv run python DispatchHub/dispatch_hub.py --layer 3 --text 'for your information'

# 層1（鍵必須）
uv run python DispatchHub/dispatch_hub.py --layer A --key secret --text 'hi'
uv run python DispatchHub/dispatch_hub.py --layer A --key secret --mode decode --text '<envelope>'

# パイプライン（同じテキストに層を順適用。A は --key 必須）
uv run python DispatchHub/dispatch_hub.py --pipeline C,E --text 'um thank you for your information'

# 層比較（C / E / B / C→E の文字数・比率を JSON Lines）
uv run python DispatchHub/dispatch_hub.py --compare --text 'I have 3 animals'

# ファイル入出力
uv run python DispatchHub/dispatch_hub.py --layer C --file in.txt --out out.txt

# stdin / JSONL 会話
printf '%s\n' '{"role":"user","text":"thank you"}' \
  | uv run python DispatchHub/dispatch_hub.py --layer C --jsonl

# MorphoZip 密度 / TesseraTalk 統計
uv run python DispatchHub/dispatch_hub.py --layer E --stats --text 'I am ready and waiting'
uv run python DispatchHub/dispatch_hub.py --layer B --stats --text 'Hello. こんにちは。'
```

主な追加フラグ: `--pipeline`, `--compare`, `--file`, `--out`, `--lexicon`, `--aad`, `--hex-nums`, `--no-rle`。

`--text` / `--file` 省略時は stdin。`--mode` は層依存（compress/expand/tag/encode/decode）。

## Round-3

- `--window N` / `--keep-system` / JSONL `--budget`（圧縮後に古い行から削除）
- `--profile NAME` / `--profile-file`（`profiles/`。CLI が上書き）
- `--min-ratio` / `--allow-weak` / `--max-loss-tokens` / `--strict-loss`
- `--pack` / `--protect-regex` / `[[keep:...]]` / `--prefer-ltr` / `--fingerprint-key`

## テスト

**D 所有の pytest は実質ゼロ。** 層単体はリポ直下 `tests/`、またぎは `tests/integration/`（結合・総合）。詳細は [`DispatchHub/tests/README.md`](tests/README.md)。

## Round-4

`--translate-min` / `--translation-bank` を B へ配線（D は変換しない）。
