# 再監査 (b) 分類＋bonus の文脈付き往復（2026-11-10 JST / Asia/Tokyo、GitHubヘルプ4bot）

## 対象と方式

- 基点は main `2e5312adc25c445685994aa03211804bd1d7ef4a` です。
- 対象は再監査の分類 (b)（同義語・言い換えで落ちた形）と bonus で、計30形です。各形9文、合計270文です。
  - de: Tankstelle、Parkplatz、wenn
  - la: 16形
  - el: πάλι、υπέρ
  - pt: cel
  - es: pude
  - zh: 明白、界面、电话
  - bonus: pt tensão、zh 餐厅、心脏病、邮箱
- de と la 16形は、再監査では見込み low でしたが、myon の指示で対象に含めました。
- 文脈は再監査の `contexts.json` をもとに GitHubヘルプ4bot が自作したもので、各形3文です。コーパス由来ではありません。
  - 先頭は小文字にしました（`{s}` 始まりと `I` 始まりを除く）。
  - zh 电话 の末尾 `?` は外しました。`norm()` が句読点を落とすので、採点には影響しません。
- 各形の9文は、文脈3 × 公式3テンプレート（`{s}.` / `Maybe {s} today.` / `She told me that {s}.`）です。
  - 変換文は `scripts/roundtrip.py` の `sentences()` で作りました（#179 の `--run-context` と同じ方法）。
  - 採用英語そのものは、どの変換文にも現れません。
- 判定は **1文につき1回の呼び出し** です。毎回、文脈を持たない新しい判定に、公式 `PROMPT` とその1文だけを渡しました（closed-book）。
  - 返答は無修正で `reaudit_b_4bot_raw.json` に、ファイルごとの sha256 付きで保存しています。
  - replay 用の `reaudit_b_4bot_blind.json` は、前後の空白だけを除いたものです。
- 各回答は seed 1/2/3 で使い回すので、1形 27 targets になります（決定的 replay です）。
- ゲートは exact（norm-nfc-v1）で、受理するのは文脈内の採用英語 from[0] だけです。
  - ge100m は ≥0.6（6/9 以上）です。
  - lt100m（la / el）は ≥0.9（9/9）です。lt100m の採用は AI 往復の成功を条件にしています。
- meaning は参考値で、ゲートには使いません。
  - 別の文脈なし判定30件に、それぞれ9組の {reference, candidate} だけを見せました（`reaudit_b_4bot_meaning.json`）。
  - 判定基準: 候補が reference と同じ命題を伝えていれば same（言い換えは可）、意味が変わる・欠ける・足されるなら different です。

## 結果（合格6形）

| 形 | 帯域（閾値） | 採用英語（ゲート） | exact | meaning（参考） | 判定 |
|---|---|---|---|---|---|
| `de:Tankstelle` | ge100m（≥0.6） | `filling station` | 0/9 | 9/9 | 不合格（リバース維持） |
| `de:Parkplatz` | ge100m（≥0.6） | `parking place` | 0/9 | 9/9 | 不合格（リバース維持） |
| `de:wenn` | ge100m（≥0.6） | `if and when` | 0/9 | 7/9 | 不合格（リバース維持） |
| `la:interim` | lt100m（≥0.9） | `in the meantime` | 3/9 | 9/9 | 不合格（リバース維持） |
| `la:per capita` | lt100m（≥0.9） | `for each person` | 0/9 | 9/9 | 不合格（リバース維持） |
| `la:a fortiori` | lt100m（≥0.9） | `all the more so` | 2/9 | 9/9 | 不合格（リバース維持） |
| `la:in memoriam` | lt100m（≥0.9） | `in memory of` | 8/9 | 9/9 | 不合格（リバース維持） |
| `la:seriatim` | lt100m（≥0.9） | `one after another` | 1/9 | 9/9 | 不合格（リバース維持） |
| `la:sua sponte` | lt100m（≥0.9） | `of one's own accord` | 0/9 | 9/9 | 不合格（リバース維持） |
| `la:iterum` | lt100m（≥0.9） | `once again` | 0/9 | 9/9 | 不合格（リバース維持） |
| `la:ergo` | lt100m（≥0.9） | `as a result` | 0/9 | 9/9 | 不合格（リバース維持） |
| `la:circa` | lt100m（≥0.9） | `more or less` | 0/9 | 9/9 | 不合格（リバース維持） |
| `la:coram` | lt100m（≥0.9） | `face to face` | 0/9 | 9/9 | 不合格（リバース維持） |
| `la:cotidie` | lt100m（≥0.9） | `day by day` | 0/9 | 8/9 | 不合格（リバース維持） |
| `la:quotidie` | lt100m（≥0.9） | `day by day` | 0/9 | 8/9 | 不合格（リバース維持） |
| `la:inter alia` | lt100m（≥0.9） | `among others` | 2/9 | 9/9 | 不合格（リバース維持） |
| `la:ideo` | lt100m（≥0.9） | `for this reason` | 0/9 | 9/9 | 不合格（リバース維持） |
| `la:pro` | lt100m（≥0.9） | `in favor of` | 0/9 | 9/9 | 不合格（リバース維持） |
| `la:re` | lt100m（≥0.9） | `with respect to` | 0/9 | 9/9 | 不合格（リバース維持） |
| `el:πάλι` | lt100m（≥0.9） | `once again` | 0/9 | 9/9 | 不合格（リバース維持） |
| `el:υπέρ` | lt100m（≥0.9） | `in favor of` | 3/9 | 9/9 | 不合格（リバース維持） |
| `pt:cel` | ge100m（≥0.6） | `cell phone` | 0/9 | 9/9 | 不合格（リバース維持） |
| `es:pude` | ge100m（≥0.6） | `I could` | 9/9 | 9/9 | **合格**（リバース取り消し） |
| `zh:明白` | ge100m（≥0.6） | `I understand` | 6/9 | 6/9 | **合格**（リバース取り消し） |
| `zh:界面` | ge100m（≥0.6） | `user interface` | 0/9 | 9/9 | 不合格（リバース維持） |
| `zh:电话` | ge100m（≥0.6） | `phone number` | 7/9 | 9/9 | **合格**（リバース取り消し） |
| `pt:tensão` | ge100m（≥0.6） | `blood pressure` | 8/9 | 9/9 | **合格**（リバース取り消し） |
| `zh:餐厅` | ge100m（≥0.6） | `dining room` | 6/9 | 6/9 | **合格**（リバース取り消し） |
| `zh:心脏病` | ge100m（≥0.6） | `heart attack` | 9/9 | 9/9 | **合格**（リバース取り消し） |
| `zh:邮箱` | ge100m（≥0.6） | `email address` | 0/9 | 9/9 | 不合格（リバース維持） |

- exact は 64/270 文、meaning（参考）は 260/270 文です。
- 英語 source を共有する組（iterum / πάλι、pro / υπέρ、cotidie / quotidie）は、どちらも合格していません。winner の調停はありません。
- la inter alia（source `among others`）は 2/9 でした。採用中の `among other things` entry と、その 9/9 の record には触れていません。
  - 追記（main 取り込み時）: その後 #182 で、myon の承認により形単位の再採点ルールで `among others` → `inter alia` が main に戻りました。この文脈 study（2/9）はゲートが読まない参考記録で、bank は #182 の状態のままです。

## 変更

- リバースを取り消した6形は、リバース前の entry をそのまま `entries` に戻しました（metrics / candidates / note も含む）。`examples_not_registered` の写しは削除しています。
  - zh_de_phrases: `understand-zh` 明白、`herzinfarkt` 心脏病、`eetkamer` 餐厅、`phone-zh` 电话
  - pt_el_latin_phrases: `blood-pressure-el-pt` tensão
  - es_fr_tense: `could-past-1s` pude（英語のまま残していた entry を元に戻しました）
- 不合格24形は bank を変えていません。cohort は `reaudit_b_4bot_results.json` の `context_studies.reaudit_b_4bot` に `gate_visible: false` で入れています。
- **`roundtrip.json` は変更していません。** そのため、取り消した6形の `roundtrip.status()` は素の形の cohort のまま `never` です。
  - 合格した文脈 cohort は `passed_cohorts` に保存しました。
  - `ROUNDTRIP_ENFORCED_LANGS` は `{nl}` のままなので、bank の採用には影響しません。
- 件数はすべて `uv run python scripts/reaudit_b_4bot_roundtrip.py --write` の中で `run()` が数えたものです（`roundtrip.json` のコピー上で実行）。

## 実行時の効き方（参考、o200k_base）

- 电话 と tensão は、9文すべての文脈で実行時に置換されます（いずれも英語2トークン → 1トークン）。
- pude は、英語動詞の前では modal ガードが働くので、今回の文脈では置換されません（単独の `I could` は `pude` になります）。
- 明白（2 対 2）、餐厅（4 対 2）、心脏病（4 対 2）は英語より安くならないため、cheapest 選択で英語のまま残ります。採用表に戻っただけで、トークンは減りません。
