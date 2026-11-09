# 中国語（zh）往復回答表の由来と制約

`zh_blind.json` は Grok Bot が変換後の文だけを読んで通常の英語に復元した186件の回答表です（SHA256 `bd799e8b…464a8`、テストで固定）。この作業では回答を一切変更していません。
任務文に英語なしの例示形（多谢 / 早 / 再见 / 晚安）が含まれ、同じアシスタントが TalkCompress の作業もしているため、完全なブラインド評価ではありません（#161 / #164 と同種の開示）。

## 方法
- 対象: origin/main `84e5dca` の `zh_de_phrases.json` で `lang=zh` のエントリ全62件（ユニーク形62、共有形なし）。
- `tense_matrix.build()` に zh エントリはないため `--lang zh` では何も選ばれません。`roundtrip.run()` に custom entries（`from[0]` → `to`）を渡し、`uv run python scripts/roundtrip_replay.py zh` を `--cmd` として実行しました。
- 複数の英語ソースを持つ11エントリは `from[0]` だけで採点しています。
- 既存の3テンプレート、seeds `[1, 2, 3]`、min_trials=9、zh は ge100m なので閾値0.6、`norm-nfc-v1` 採点。558件完了、タイムアウト・実行エラーとも0。試行回数・合否は `scripts/roundtrip.py` が生成し、手編集していません。
- 各 seed は同じ確定回答を再生します。9件は独立した9回のライブ推論ではありません。自由文での追加の AI 可読性は未測定です。
- 形が英語として読めることと、登録した英語ソースに厳密一致で戻ることは別です。`norm` はハイフンを除去するため、high-speed / bookstore のような綴り違いも不一致になります（厳密ゲートのまま適用）。

## 結果（通過37 / 不通過25、不通過はすべて0/9）
| 英語ソース(from[0]) | 形 | restored/completed | 判定 | 復元 | runtime_pair_loaded(main) | 処置 |
|---|---|---|---|---|---|---|
| thank you very much | 多谢 | 0/9 | 不通過 | Thanks a lot | yes | 削除（英語のまま） |
| good morning | 早 | 9/9 | 通過 | Good morning | no | 維持 |
| see you later | 再见 | 0/9 | 不通過 | Goodbye | no | 削除（英語のまま） |
| good night | 晚安 | 9/9 | 通過 | Good night | no | 維持 |
| wait a moment | 稍等 | 0/9 | 不通過 | Just a moment | no | 削除（英語のまま） |
| I understand | 明白 | 0/9 | 不通過 | Understood | no | 削除（英語のまま） |
| what time is it | 几点 | 0/9 | 不通過 | What time | yes | 削除（英語のまま） |
| see you tomorrow | 明天见 | 9/9 | 通過 | See you tomorrow | no | 維持 |
| of course | 当然 | 9/9 | 通過 | Of course | no | 維持 |
| high speed | 高速 | 0/9 | 不通過 | High-speed | yes | 削除（英語のまま） |
| short term | 短期 | 0/9 | 不通過 | Short-term | no | 削除（英語のまま） |
| green tea | 绿茶 | 9/9 | 通過 | Green tea | no | 維持 |
| black tea | 红茶 | 9/9 | 通過 | Black tea | no | 維持 |
| driving licence | 驾照 | 0/9 | 不通過 | Driver's license | no | 削除（英語のまま） |
| police station | 警局 | 9/9 | 通過 | Police station | no | 維持 |
| post office | 邮局 | 9/9 | 通過 | Post office | no | 維持 |
| blood pressure | 血压 | 9/9 | 通過 | Blood pressure | no | 維持 |
| heart attack | 心脏病 | 0/9 | 不通過 | Heart disease | no | 削除（英語のまま） |
| operating system | 操作系统 | 9/9 | 通過 | Operating system | no | 維持 |
| dining room | 餐厅 | 0/9 | 不通過 | Restaurant | no | 削除（英語のまま） |
| high school | 高中 | 9/9 | 通過 | High school | no | 維持 |
| middle school | 初中 | 9/9 | 通過 | Middle school | no | 維持 |
| primary school | 小学 | 0/9 | 不通過 | Elementary school | no | 削除（英語のまま） |
| subway station | 地铁站 | 9/9 | 通過 | Subway station | no | 維持 |
| living room | 客厅 | 9/9 | 通過 | Living room | no | 維持 |
| speed limit | 限速 | 9/9 | 通過 | Speed limit | no | 維持 |
| human rights | 人权 | 9/9 | 通過 | Human rights | no | 維持 |
| social media | 社媒 | 9/9 | 通過 | Social media | no | 維持 |
| open source | 开源 | 9/9 | 通過 | Open source | yes | 維持 |
| soy sauce | 酱油 | 9/9 | 通過 | Soy sauce | no | 維持 |
| fried rice | 炒饭 | 9/9 | 通過 | Fried rice | no | 維持 |
| high speed rail | 高铁 | 0/9 | 不通過 | High-speed rail | yes | 削除（英語のまま） |
| convenience store | 便利店 | 9/9 | 通過 | Convenience store | no | 維持 |
| shopping mall | 商场 | 9/9 | 通過 | Shopping mall | no | 維持 |
| department store | 百货 | 9/9 | 通過 | Department store | no | 維持 |
| book store | 书店 | 0/9 | 不通過 | Bookstore | no | 削除（英語のまま） |
| drug store | 药店 | 0/9 | 不通過 | Pharmacy | no | 削除（英語のまま） |
| super market | 超市 | 0/9 | 不通過 | Supermarket | no | 削除（英語のまま） |
| business card | 名片 | 9/9 | 通過 | Business card | no | 維持 |
| business trip | 出差 | 9/9 | 通過 | Business trip | no | 維持 |
| email address | 邮箱 | 0/9 | 不通過 | Mailbox | no | 削除（英語のまま） |
| phone number | 电话 | 0/9 | 不通過 | Phone | yes | 削除（英語のまま） |
| flash drive | U盘 | 0/9 | 不通過 | USB flash drive | no | 削除（英語のまま） |
| source code | 源码 | 9/9 | 通過 | Source code | no | 維持 |
| user interface | 界面 | 0/9 | 不通過 | Interface | no | 削除（英語のまま） |
| front end | 前端 | 0/9 | 不通過 | Frontend | no | 削除（英語のまま） |
| full stack | 全栈 | 9/9 | 通過 | Full stack | yes | 維持 |
| knowledge base | 知识库 | 9/9 | 通過 | Knowledge base | no | 維持 |
| vector database | 向量库 | 0/9 | 不通過 | Vector store | no | 削除（英語のまま） |
| large language model | 大模型 | 0/9 | 不通過 | Large model | yes | 削除（英語のまま） |
| chain of thought | 思维链 | 9/9 | 通過 | Chain of thought | yes | 維持 |
| fine tuning | 微调 | 0/9 | 不通過 | Fine-tuning | yes | 削除（英語のまま） |
| rate limit | 限流 | 0/9 | 不通過 | Rate limiting | no | 削除（英語のまま） |
| high availability | 高可用 | 9/9 | 通過 | High availability | no | 維持 |
| disaster recovery | 灾备 | 9/9 | 通過 | Disaster recovery | no | 維持 |
| technical debt | 技术债 | 9/9 | 通過 | Technical debt | no | 維持 |
| continuous integration | 持续集成 | 9/9 | 通過 | Continuous integration | no | 維持 |
| round trip | 往返 | 9/9 | 通過 | Round trip | no | 維持 |
| postal code | 邮编 | 9/9 | 通過 | Postal code | no | 維持 |
| screen shot | 截图 | 0/9 | 不通過 | Screenshot | no | 削除（英語のまま） |
| black box | 黑箱 | 9/9 | 通過 | Black box | no | 維持 |
| white paper | 白皮书 | 9/9 | 通過 | White paper | no | 維持 |

不通過25件のうち候補リストを持つのは 驾照（Führerschein）、心脏病（hartaanval / Herzinfarkt）、餐厅（eetkamer）の3件だけです。o200k では英語 from[0] に対しそれぞれ 3 対 3、3・4 対 2、3 対 3 で、英語に勝つ候補はありません。よって次点勝者への置き換えはなく、25件すべて live エントリを削除して `examples_not_registered` に移しました（英語のまま）。

## ラベルと実行時
main で `zh_de_phrase_pairs()` に読み込まれる zh エントリは62件中10件だけです（estimate_tokens で厳密に減る場合のみ読み込むため）。残り52件はラベルだけで、実行時には発火しません。
10件のうち7件（多谢・几点・高速・高铁・电话・大模型・微调）が不通過で、通過は 开源・全栈・思维链 の3件です。この3件も実行時に読み込まれるのはハイフン付きソース（open-source / full-stack / chain-of-thought）だけで、採点に使った from[0]（スペース区切り）では発火しません。

## 較正表
バンク変更後に `uv run python scripts/calibrate_estimate.py --write` で `o200k_calib.json` を正式に再生成しました。削除した候補の訓練語 eetkamer / führerschein / herzinfarkt の3例外が消えただけで、`zh_de_phrase_pairs()` の出力は再生成前後で同一です。

de / en / nl のエントリ25件（zh 候補を持つ en 4件・de 3件を含む）は書き換えていません（テストでハッシュ固定）。
