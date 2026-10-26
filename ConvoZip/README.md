# ConvoZip（D）

**横断オーケストレーション。** 層の選択と共通入出力の表玄関。

## ルーティング

| 指定 | 行き先 |
| --- | --- |
| `1` / `A` / `zipilogue` | Zipilogue |
| `2` / `B` / `tessera` | TesseraTalk |
| `3` / `C` / `shorthand` | ShorthandLab |
| `4` / `E` / `morpho` | MorphoZip |

## 使い方

```bash
# テキスト
uv run python ConvoZip/convo_zip.py --layer 3 --text 'for your information'

# 層1（鍵必須）
uv run python ConvoZip/convo_zip.py --layer A --key secret --text 'hi'
uv run python ConvoZip/convo_zip.py --layer A --key secret --mode decode --text '<envelope>'

# パイプライン（同じテキストに層を順適用。A は --key 必須）
uv run python ConvoZip/convo_zip.py --pipeline C,E --text 'um thank you for your information'

# 層比較（C / E / B / C→E の文字数・比率を JSON Lines）
uv run python ConvoZip/convo_zip.py --compare --text 'I have 3 animals'

# ファイル入出力
uv run python ConvoZip/convo_zip.py --layer C --file in.txt --out out.txt

# stdin / JSONL 会話
printf '%s\n' '{"role":"user","text":"thank you"}' \
  | uv run python ConvoZip/convo_zip.py --layer C --jsonl

# MorphoZip 密度 / TesseraTalk 統計
uv run python ConvoZip/convo_zip.py --layer E --stats --text 'I am ready and waiting'
uv run python ConvoZip/convo_zip.py --layer B --stats --text 'Hello. こんにちは。'
```

主な追加フラグ: `--pipeline`, `--compare`, `--file`, `--out`, `--lexicon`, `--aad`, `--hex-nums`, `--no-rle`。

`--text` / `--file` 省略時は stdin。`--mode` は層依存（compress/expand/tag/encode/decode）。
