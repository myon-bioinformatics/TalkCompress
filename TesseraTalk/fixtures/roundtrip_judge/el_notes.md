# Greek 往復回答表の由来と制約

`el_blind.json` は親担当の Grok Bot が変換後の文から通常の英語に復元して用意した21件の回答表です。この作業では提供された表を変更していません。
任務文に英語対応が含まれていたため、完全に独立したブラインド評価ではありません（Latin PR #161 と同様の制約）。ファイル名は既存 replay 方式に合わせています。

`roundtrip.run()` の custom entries に以下の9ソース→形だけを渡し、`uv run python scripts/roundtrip_replay.py el` を実行しました。CLI の `--lang el` による全時制勝者の実行ではありません。

| 英語ソース | 形 | restored / completed |
|---|---|---|
| one by one | ένα ένα | 9/9 |
| I will find | βρω | 0/9 |
| I am going to find | βρω | 0/9 |
| once again | πάλι | 0/9 |
| more or less | πάνω κάτω | 9/9 |
| in favor of | υπέρ | 0/9 |
| with respect to | ως προς | 9/9 |
| I will take | πάρω | 0/9 |
| I am going to take | πάρω | 0/9 |

既存の3テンプレート、seeds `[1, 2, 3]`、min_trials=9、lt100m閾値0.9、`norm-nfc-v1` 採点を使用。81件完了、タイムアウト・実行エラーとも0。
`lang:form` ごとの記録なので βρω / πάρω はそれぞれ18件です。試行回数・合否は `scripts/roundtrip.py` が生成し、手編集していません。
各 seed は同じ確定回答を再生します。9/18件は独立した新規AI呼び出しの回数ではありません。

失敗時の復元核は βρω→I find、πάλι→again、υπέρ→in favor、πάρω→I take。
形自体を英語へ読めることと、元の特定の英語に厳密一致で戻ることは別です。自由文・多言語コーパスを用いた追加の可読性評価は未測定です。

main では more or less / in favor of / with respect to の採用形は Latin の circa / pro / re のままで、これらのエントリはこの変更では動かしていません。
#161 後の想定 Greek 勝者では πάνω κάτω と ως προς は通過、**υπέρ は不通過**です。#161 には push せず、担当者へ結果を報告します。

バンク変更後は `uv run python scripts/calibrate_estimate.py --write` で較正表も正式に再生成しています。訓練語の減少により Greek 4文字 fallback は2→1となり、除去済み βρω / πάλι / πάρω や Latin iterum の単体推定値は main 時点と異なります。除去の判断はAI復元結果に基づきます。main 時点のラベル対cheapestの測定と、変更後の較正表の値を混同しないでください。採用中の代替 acharei / tomaré はいずれも2 tokensのままです。
