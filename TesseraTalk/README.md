# TesseraTalk（B）

**層2 — 機械 + 高度な人間。** 文ごとに言語が切り替わるモザイク。LTR + 。！？ を当面の前提。

**重み:** 翻訳によるトークン削減。**EN + ZH + JA は開始セットであり、ハードな言語天井ではない。** スコープには Romance（es / fr / pt / it）、Germanic（de / nl / en）、Greek（el）、および ja / zh が入る。自然に短い形（翻訳由来の略語含む）は許容。C の合意台帳パッチ（under→下 など）は **適用しない**。

## できること

- 文分割（`.!?。？！…`）
- Unicode スクリプト + 軽い語彙／表記キューによるヒューリスティック LID（Romance / Germanic / Greek 含む）
- `compress` → モザイク / `expand` → 平文 / `tag` → `[lang] …`
- **RLE モザイク（既定オン）**: 連続する同言語では言語タグを省略し継承

  ```
  en:Hello.|World.|ja:こんにちは。
  ```

  `expand` は旧形式 `lang:sent|lang:sent` と RLE の両方を受理。`--no-rle` で常にフルタグ。
- `--stats` で文数・言語ヒストグラム（JSON → stderr）
- **翻訳トークン最短（opt-in）**: `--translate-min` / `translate_min=True`

  文ごとに `fixtures/translations.json` の候補を `estimate_tokens` で比較し、**厳密に短いときだけ**採用。既定は **fixture エンジン**（pytest 決定的・オフライン）。C 台帳とは別経路。

- **ライブ MT（opt-in）**: `--translate-engine=argos|deep`

  対象言語（Romance / Germanic / el / ja / zh）へ **並列翻訳**し、`estimate_tokens` の短さ＋**揺らぎ（曖昧さ）ペナルティ**で選ぶ。最短でも意味がぶれる語（例: `set` / `table`）は、少し長いが明確な候補や原文に負けることがある。

  | engine | 依存 | 備考 |
  | --- | --- | --- |
  | `fixture`（既定） | なし | バンクのみ。CI / pytest 用（決定的・オフライン） |
  | `deep` | `uv sync --group translate`（`deep-translator`） | 並列・ネットワーク |
  | `argos` | 別途 `argostranslate` + 言語パック | 並列・オフライン可だが重い。default sync には入れない |

  未インストール時は静かにバンク／原文へフォールバック（例外にしない）。

```bash
uv run python TesseraTalk/tessera_talk.py tag --text 'Hello. こんにちは. Hola. Guten Tag. Γεια σου.'
uv run python TesseraTalk/tessera_talk.py compress --text 'Hello. World. こんにちは。'
uv run python TesseraTalk/tessera_talk.py compress --no-rle --text 'Hello. World.'
uv run python TesseraTalk/tessera_talk.py expand --text 'en:Hello.|World.|ja:こんにちは。'
uv run python TesseraTalk/tessera_talk.py compress --stats --text 'Hello. こんにちは。'
uv run python TesseraTalk/tessera_talk.py compress --translate-min --text 'Good morning. Please reply as soon as possible.'
uv run python TesseraTalk/tessera_talk.py compress --translate-min --allow-langs es,fr,de,el --text 'I would be grateful if you could assist me with this issue.'
# optional live (needs --group translate):
# uv run python TesseraTalk/tessera_talk.py compress --translate-min --translate-engine deep --text 'Hello friends.'
```

## prefer-ltr / script_mix

`--prefer-ltr` biases Latin+CJK mixes without kana toward `en` rather than `zh`. `script_mix(text)` returns script counts/ratios; included in `--stats` JSON.

## `estimate_tokens` の範囲と検証状態

`estimate_tokens` はコミット済みの校正表と文字範囲に基づく **stdlib の推定器**であり、実 tokenizer の計測値ではありません。翻訳候補の順位にも使うため、推定の変更は選択される表現を変える可能性があります。

[#108](https://github.com/myon-bioinformatics/TalkCompress/pull/108) の補正は、ポーランド語・チェコ語だけを検出して適用するものではありません。歴史的な定数名 `_LATIN_EXT_A` の範囲は **U+0100–U+024F（Latin Extended-A と Extended-B）**です。対応する長さの校正表がない class `s` の語で、`ceil(len/4)` に該当文字数を加算します。たとえば `œuvre`、マクロンやピンインの文字も対象になり得ます。校正表・登録済み例外・既存 suffix 規則が優先されます。

- #108 で追加された `ı İ ğ Ğ ş Ş đ Đ` は、この加算から除外します。既存のトルコ語・ベトナム語の例を保つための限定的な例外であり、それらの言語全般の精度を保証しません。
- U+1E00–U+1EFF を含む混合語は既存の class `v` が優先され、class `s` の補正は重ねません。これは文字範囲による分類であって、言語判定ではありません。

### #108 の報告をどう扱うか

52 語での調整、誤差の偏り −65 → +8、train 2464/2464、heldout 593/600、順位逆転 0、natural 誤差合計 55 → 54 は **元 PR 本文の著者報告・独立未検証の履歴**です。この調整の全入力・生の tokenizer 出力・実行条件の検証記録は追加されていません。これらの数値を、例外追加後の現行コードを再検証した結果とは扱いません。`tests/test_estimate_pl_cs.py` の参照値も著者報告を残したもので、許容幅を満たすことは一般的な精度の証明ではありません。この修正のローカル検証では再調整、実 tokenizer 計測、辞書取得を行っていません。

`tests/test_estimate_pl_cs.py` の既定テストは推定式・例外・表の優先順位をオフラインで検査します。同ファイル内の実 tokenizer と照合する参考テストは、明示的に `TALKCOMPRESS_RUN_TOKENIZER_CHECKS=1` を指定した場合だけ動きます（tiktoken がインストール済みでも既定は skip）。この手動照合はキャッシュがなければ辞書を取得し得るため、今回のオフライン検証とは分けます。このフラグは、このテストに対する opt-in であり、リポジトリ内の他の計測経路を制御するものではありません。

リポジトリ全体の pytest には実 tokenizer を使う既存の検査があり、`tests/conftest.py` の token-agreement 集計も含めて辞書取得が起こり得ます。上記フラグは全体をオフライン化する設定ではありません。

```bash
# 任意の実 tokenizer 照合。辞書取得が起こり得るため、必要なときだけ明示実行。
TALKCOMPRESS_RUN_TOKENIZER_CHECKS=1 uv run python -m pytest tests/test_estimate_pl_cs.py::test_tr_vi_match_o200k
```

## C との境界

| | B TesseraTalk | C ShorthandEdge |
| --- | --- | --- |
| 短縮の主因 | 文の翻訳でトークンが減るなら採用 | 登録済み略語・合意台帳 lex |
| 略語 | 翻訳結果として自然に出るもの OK | パッチ／台帳で明示登録 |
| under→下 等 | しない（翻訳バンク経由のみ） | 台帳で適用 |
| 言語スコープ | Romance / Germanic / Greek + ja/zh（EN+ZH+JA は開始セット） | 台帳ベースは EN+ZH+JA 寄り、cognate 可 |

## Round notes

翻訳バンクに ES/FR/PT/IT/DE/NL/EL を拡充。`--translate-min` は DensityZip 経由でも可。`--translate-engine=deep|argos` は並列多言語→長さ＋揺らぎで採用。

### `es_fr_tense.json` の `to` について

`to` / `lang` は名目ラベルで、実際の置換は runtime cheapest（token→utf8→len）が `candidates` から選びます。ラベルは runtime 勝者に合わせてあり（例: take→`πάρω`(el), find→`βρω`(el)）、`tests/test_pd20_examples.py::test_bank_to_label_matches_runtime_winner` で同期を検査します。
