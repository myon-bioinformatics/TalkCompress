# テスト用多言語コーパス（仮配置）

`scripts/build_corpus.py` で取得・生成（seed 固定、`uv run --with ftfy python scripts/build_corpus.py`）。
ファイルごとの出典・ライセンス・件数・sha256・o200k/バイト合計は `manifest.json`。
形式は docs/corpus.md（#134）に従い、数値は `scripts/corpus_manifest.py update` で計算、`check` で検証する。

| カテゴリ | 内容 | 出典 / ライセンス |
|---|---|---|
| colloquial/{ja,en,vi,th} | Common Voice の読み上げ用文（各 400 件、`register: "read"`） | CC0 1.0 |
| tatoeba/ja（追記分） | Tatoeba の口語文 300 件（`register: "colloquial"`、#134 の 11 件はそのまま） | CC BY 2.0 FR |
| mojibake/{ja,vi} | Common Voice 文を latin-1/cp1252/SJIS/EUC-JP で誤読させた文と原文の対 | CC0 1.0（原文）|
| mixed/{ja,en} | 自作テンプレート＋コードポイント範囲から自作で組み立てた絵文字＋一部に Common Voice 文（`embedded_id`） | CC0 1.0 |

## 表示（Attribution）
- Tatoeba: Sentences from Tatoeba (https://tatoeba.org), licensed under CC BY 2.0 FR (https://creativecommons.org/licenses/by/2.0/fr/). 各行の `id` は Tatoeba の文 ID で、`https://tatoeba.org/sentences/show/<id>` の寄稿者に帰属する。
- Common Voice: CC0-1.0（表示不要）。

## レコード形式
各行は #134 の `{id,text,lang,tier,source,license,author,url}` に加え、実測の `o200k`・`bytes` と補助欄（`register`、mojibake の `orig`/`orig_id`/`kind`/`ftfy_*`、mixed の `embedded_id`）。Common Voice 行の `url` は取得元ファイル、`author` は "Common Voice contributors"、`id` は `cv-<lang>-<本文 sha1 先頭 12 桁>`。
#134 の規則（1 ファイル = 1 source）のため、Tatoeba の口語文は colloquial/ja ではなく tatoeba/ja に入れている。`colloquial` の中身は読み上げ文（`register: "read"`）。

## tier と件数
- tier は `scripts/build_corpus.py` の `tier()` で判定: 1 文かつ 200 コードポイント以下 → short、5 文以下かつ 1000 コードポイント以下 → medium、それ以外 → long（文末記号 。！？.!? で数える）。mojibake は原文 `orig` で判定。
- 件数は各ファイル 400 件で固定（Tatoeba 追記分は 300 件）。mojibake/ja は 1 ファイル上限 256KB に近いため、増やす場合はファイルを分ける。

## 注意
- AI が元の文に戻せるかは **未測定**。mojibake の `ftfy_exact` / `ftfy_o200k` は ftfy による機械復元の実測値。
- Common Voice は読み上げ用の文で、自発発話の書き起こしではない。自由ライセンスの日本語話し言葉コーパス（CSJ 等は非自由）は見つからず不採用。
