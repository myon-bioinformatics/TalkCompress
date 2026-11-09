# ドイツ語（de）往復回答表の由来と制約

`de_blind.json` は Grok Bot が変換後の文だけを読んで通常の英語に復元した255件の回答表です。この作業では採点後に回答を書き換えていません。

同じアシスタントが TalkCompress の往復任務もしているため、完全なブラインド評価ではありません（#161 / #164 / #169 と同種の開示）。

## 方法
- 対象: origin/main の de 採用 138エントリ / 85ユニーク形。
- first-entry-per-form（tense_matrix → zh_de_phrases → es_fr_tense）。
- `roundtrip.run(..., entries=...)` + `roundtrip_replay.py de`、seeds [1,2,3]、テンプレート3種、norm-nfc-v1、閾値0.6。
- 765件完了（85×9）、タイムアウト・実行エラー 0。件数は run() が数え手編集なし。
- ドイツ語単純過去は英語の単純過去へ復元（nl_blind の Nam→I took に準拠）。bank が現在完了ソースに紐づけている共有面は不一致になり 0/9。
- `que` 面は That … と読み、#168 の que sa/dà と同じ失敗様式。
- 複合語は一般的な英語訳。filling station / parking place / if and when は同意近傍訳で不一致。

## 結果
通過32 / 不通過53（すべて0/9）。不通過は tense_matrix 50形を ROUNDTRIP_REVERSED、zh_de 3形と es_fr fand を examples_not_registered へ。
