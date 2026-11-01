# 不明語・文字化けの残し方（shared/asr_normalize.py）

音声入力（ASR）や口語入力で出てくる「聞き取れない語」「知らない固有名詞」「文字化け」を、
o200k_base のトークン数（第一）とバイト数（第二）が増えない形で残すための規則。stdlib のみで、依存は増やさない。

## 規則
1. 発音が似ている語・未知語は **元のつづり**（つづりが分からなければローマ字）で、**空白を詰めて 1 語** にする。括弧では包まない。
   - 例: `mini match` → `minimatch`、`Talk Compress` → `TalkCompress`。大文字小文字は元のまま（CamelCase 化はしない）。
   - カタカナ・ハングル・デーヴァナーガリー・タイ文字・IPA への書き換えや括弧付けは、27 語の実測で原つづりより同数か多かった（audio-tok/script_test.md）。
2. **不確実な語だけ** 後ろに `(?)` を付けて `語(?)` にする（+1 tok。XML PI と衝突する `<?語?>` は +2〜3 tok）。既定では前後が語でない `[語?]` だけをそろえる（`array[i?]` は残す）。`語{0.42}`（数式 `x{0.5}` と衝突。0.6 未満なら付け、以上なら外す）、`(語?)`、`{a|b|c}` は `confidence=True` / `paren=True` / `alternatives=True` の opt-in。
3. 文字化けは **まず復元**する。UTF-8 を cp1252 / latin-1 で読んだもの（二重化けも 2 回まで）、UTF-8 を cp932 で読んだもの（縺・繧 系）を戻す。cp1252 で未定義のバイト（0x81 など）が U+FFFD になっていても候補を総当たりして戻す。UTF-8 として厳密に読めない連続は戻さない。1 文字にしか戻らない連続は、よく出る先頭文字（Â Ã â ã Ð など）か C1 制御文字を含むときだけ戻す（`café…–` は残す）。1 文字に戻る 2 文字の連続でも、結果が titlecase の合字（`Ç…`→ǅ）や記号から作られる拡張ラテン大文字（`Ä€`→Ā）なら戻さない（小文字の `Ä…`→ą、`Å‚`→ł は戻す）。
4. 復元できない U+FFFD の連続（間の空白も含む）は **U+FFFD 1 文字** にまとめる。NUL などの制御文字・私用領域は意味を持ちうるので残す。半角カナは普通の日本語なので化けと判定しない。

`normalize_asr(text)` は 3 → 4 → 2 の順に適用する。圧縮器（ShorthandEdge / MorphoZip など）の前段で使う想定で、既存の圧縮器の出力は変えない。

## 実測（o200k_base, tok/バイト）
`uv run python scripts/measure_asr_normalize.py`

| ケース | 入力 tok/B | 出力 tok/B | 出力 |
|---|---|---|---|
| 不確実 [語?] | 10/41 | 8/40 | `I pushed it to talkcompress(?) yesterday` |
| 候補 {a|b} | 15/69 | 8/40 | `I pushed it to TalkCompress(?) yesterday` |
| 信頼度 | 12/43 | 8/40 | `I pushed it to TalkCompress(?) yesterday` |
| 分かち書き | 9/38 | 8/35 | `we use minimatch and dependabot now` |
| 化け cp1252 | 77/197 | 17/87 | `日本語のテキストです。ありがとうございます。café — “hi” ok` |
| 化け latin-1 | 112/164 | 17/87 | `日本語のテキストです。ありがとうございます。café — “hi” ok` |
| 化け cp932 | 86/150 | 21/84 | `日本語�キストです。ありがと�ござ�ます。café � “hi� ok` |
| 復元不能 | 7/24 | 5/14 | `ok �� end` |

原文 J: 17/87
talk compress: 分割 2 / join_word talkcompress 2 / lower talkcompress 2
mini match: 分割 2 / join_word minimatch 2 / lower minimatch 2
depend a bot: 分割 3 / join_word dependabot 2 / lower dependabot 2
iron mate: 分割 2 / join_word ironmate 2 / lower ironmate 2
play wright: 分割 3 / join_word playwright 1 / lower playwright 1

U+FFFD 連続: {1: 1, 3: 1, 8: 1} / 空白まじり 3 個: 3

（表は paren / alternatives / confidence をすべて True にして測定。既定では前後が語でない `[語?]` だけを変換）

- U+FFFD の連続は o200k では何個でも 1 tok なので、まとめる効果はトークンでは「間の空白・制御文字が消える分」、バイトでは 3 B/個。
- cp932 化けは元のバイトが一部失われているため完全には戻らない（失われた文字は U+FFFD 1 個になる）。それでも 86 → 21 tok。
  失われたバイトを 0x80-0xFF で総当たりする案も試したが、ひらがなの末尾バイトはどれを入れても有効な UTF-8 になる（い/ぁ/う… の区別がつかない）ため誤復元が増え、採用しなかった。テスト `test_cp932_byte_loss_limit` で現状を固定している。

## 適用範囲
- `normalize_asr` / `normalize_uncertain` / `clean_mojibake` は **ASR の書き起こし（自然文）専用**。コード・ログ・数式・JSON には適用しないこと。`[i?]` などは前後の語でガードしているが、ラテン 2 文字の並び（`Ã©` など）や U+FFFD の集約は内容に関係なく書き換わる。

## AI 可読性・往復
- 復元（cp1252 / latin-1）はテストの例で原文と完全一致（バイト単位の往復）。
- `語(?)` を LLM が「不確実語」と解釈できるか: **未測定**。
- 1 語に詰めた未知語（`dependabot` など）を LLM が元の固有名詞と同一視できるか: **未測定**。
