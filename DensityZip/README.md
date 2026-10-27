# DensityZip（D）

語源: *density*（密度指標）+ *Zip*（圧縮の結節）。層横断のオーケストレーションと **density** 指標の表玄関。

> **決定名（2026-10-27）:** 旧仮名 DispatchHub を **DensityZip** に確定。Hub / Convo / Dispatch は使わない。

**横断オーケストレーション + density 指標ファサード。** 層の選択・共通入出力の表玄関。合意台帳（ledger）は持たない — ソース・オブ・トゥルースは [ShorthandEdge/ledger](../ShorthandEdge/ledger/)（C が適用）。

### Zip 名の区別（混同しない）

| ID | フルネーム | 役割 |
| --- | --- | --- |
| A | **Zipilogue** | 層1 — 共有ルール台帳 / 任意封筒（density ではない） |
| D | **DensityZip** | 横断 — density 指標ファサード + 層オーケストレーション（本モジュール） |
| E | **MorphoZip** | 層4 — 形態・代名詞在庫ビット・文法最小 |

散文では単独の「Zip」だけ書かず、常にフルネームを使う。モジュールは `DensityZip/density_zip.py`（汎用 `zip` という識別子は避ける）。

### density の所有分担

- **D（本モジュール）:** `--compare` / `--budget` / `--stats` 配線で token 寄り（budget・`content_token_loss`、B の `estimate_tokens` を通した表出）と bit 寄り（E の `density()` / `pronoun_bit_cost` 集約）を横断表示するファサード
- **B TesseraTalk:** `estimate_tokens` / `--translate-min` の本体
- **E MorphoZip:** `pronoun_inventory_bits` / `pronoun_bit_cost` / `density()` の本体
- **C ShorthandEdge:** 合意台帳

## ルーティング

| 指定 | 行き先 |
| --- | --- |
| `1` / `A` / `zipilogue` | Zipilogue |
| `2` / `B` / `tessera` | TesseraTalk |
| `3` / `C` / `shorthand` / `shorthand_edge` | ShorthandEdge |
| `4` / `E` / `morpho` / `morpho_zip` | MorphoZip |
| `D` / `density` / `density_zip` | このルーター自身（pipeline には入れない） |

## 使い方

```bash
# テキスト
uv run python DensityZip/density_zip.py --layer 3 --text 'for your information'

# 層1（鍵必須）
uv run python DensityZip/density_zip.py --layer A --key secret --text 'hi'
uv run python DensityZip/density_zip.py --layer A --key secret --mode decode --text '<envelope>'

# パイプライン（同じテキストに層を順適用。A は --key 必須）
uv run python DensityZip/density_zip.py --pipeline C,E --text 'um thank you for your information'

# 層比較（C / E / B / C→E の文字数・比率を JSON Lines）
uv run python DensityZip/density_zip.py --compare --text 'I have 3 animals'

# ファイル入出力
uv run python DensityZip/density_zip.py --layer C --file in.txt --out out.txt

# stdin / JSONL 会話
printf '%s\n' '{"role":"user","text":"thank you"}' \
  | uv run python DensityZip/density_zip.py --layer C --jsonl

# MorphoZip 密度 / TesseraTalk 統計（D 経由で表出）
uv run python DensityZip/density_zip.py --layer E --stats --text 'I am ready and waiting'
uv run python DensityZip/density_zip.py --layer B --stats --text 'Hello. こんにちは。'
```

主な追加フラグ: `--pipeline`, `--compare`, `--file`, `--out`, `--lexicon`, `--aad`, `--hex-nums`, `--no-rle`。

`--text` / `--file` 省略時は stdin。`--mode` は層依存（compress/expand/tag/encode/decode）。

## Round-3

- `--window N` / `--keep-system` / JSONL `--budget`（圧縮後に古い行から削除）
- `--profile NAME` / `--profile-file`（`profiles/`。CLI が上書き）
- `--min-ratio` / `--allow-weak` / `--max-loss-tokens` / `--strict-loss`
- `--pack` / `--protect-regex` / `[[keep:...]]` / `--prefer-ltr` / `--fingerprint-key`

## テスト

**D 所有の pytest は実質ゼロ。** 層単体はリポ直下 `tests/`、またぎは `tests/integration/`（結合・総合）。詳細は [`DensityZip/tests/README.md`](tests/README.md)。

## Round-4

`--translate-min` / `--translation-bank` / `--translate-engine` を B へ配線（D は変換しない。engine 既定は fixture）。
