# テスト用多言語コーパス（仮配置）

`scripts/build_corpus.py` で取得・生成（seed 固定、`uv run --with ftfy python scripts/build_corpus.py`）。
ファイルごとの出典・ライセンス・件数・sha256・o200k/バイト合計は `manifest.json`。
置き場所と manifest 形式は仮で、GitHubヘルプ2bot の設計が決まれば合わせる。

| カテゴリ | 内容 | 出典 / ライセンス |
|---|---|---|
| colloquial/{ja,en,vi,th} | Common Voice の読み上げ用文（各 400 件、`register: "read"`）。ja には Tatoeba の口語文 300 件（`register: "colloquial"`）も同居し、行の `source` で区別 | CC0-1.0 / CC BY 2.0 FR |
| mojibake/{ja,vi} | Common Voice 文を latin-1/cp1252/SJIS/EUC-JP で誤読させた文と原文の対 | CC0-1.0（原文）|
| mixed/{ja,en} | 自作テンプレート＋コードポイント範囲から自作で組み立てた絵文字＋一部に Common Voice 文（`embedded_id`） | CC0-1.0 |

## 表示（Attribution）
- Tatoeba: Sentences from Tatoeba (https://tatoeba.org), licensed under CC BY 2.0 FR (https://creativecommons.org/licenses/by/2.0/fr/). 各行の `id` は Tatoeba の文 ID で、`https://tatoeba.org/sentences/show/<id>` の寄稿者に帰属する。
- Common Voice: CC0-1.0（表示不要）。

## レコード形式
各行は #134 の `{id,text,lang,tier,source,license,author,url}` に加え、実測の `o200k`・`bytes` と補助欄（`register`、mojibake の `orig`/`orig_id`/`kind`/`ftfy_*`、mixed の `embedded_id`）。Common Voice 行の `url` は取得元ファイル、`id` は `cv-<lang>-<本文 sha1 先頭 12 桁>`。
カテゴリ名 `colloquial` には読み上げ文も含まれる（`register` 欄で区別）。

## 注意
- AI が元の文に戻せるかは **未測定**。mojibake の `ftfy_exact` / `ftfy_o200k` は ftfy による機械復元の実測値。
- Common Voice は読み上げ用の文で、自発発話の書き起こしではない。自由ライセンスの日本語話し言葉コーパス（CSJ 等は非自由）は見つからず不採用。
