# that の扱い（補文標識の削除・指示詞・関係詞）

採点: o200k_base、文中想定で先頭スペース付き（`' '+s`）。採用条件は英語より**トークンが厳密に少ない**こと。

## 採用した規則（MorphoZip E 層）
- **非 NP 目的語動詞**（think / hope / say / believe / feel / guess / suppose。活用形を含む）+ `that` + 節主語（代名詞・限定詞・there など）→ `that` を削除する。
- **NP 目的語動詞**（know / see / tell / show / find / hear / realize。活用形を含む）+ `that` → 直後が「代名詞主語（I/U/you/he/she/it/we/they）+ 動詞」の場合だけ削除する。
- **削除位置のコンマ**: 付けない。
  - `I think that he is going` = 6 tok / 25 B
  - `I think he is going` = 5 / 20
  - `I think, he is going` = 6 / 21（英語と同数で、厳密減にならない）
  - コンマなしは厳密減で、コンマありは英語と同数。
- **関係詞 that → que**（#23 の判定器）は変更しない。

## 指示詞 that / those → the は見送り
`the` は英語より厳密に少なくならないため、採用条件を満たさない。
- `' that'` = 1 tok / 5 B、`' those'` = 1 / 6、`' the'` = 1 / 4。
- `that book` と `the book` はどちらも 2 tok。`those books` と `the books` もどちらも 2 tok。
- いずれもトークン同数で、バイトだけ減る。既存の `that→eso`（1 tok / 4 B）も同数のまま残っている。
- the 化すると指示の意味（遠称・特定）も失われる。

## 意図的な破壊テスト
(a) は `that` だけを削除、(b) は `that` と直後の 1 語を削除したもの。

| 原文 (tok/B) | (a) | (b) | 所見 |
|---|---|---|---|
| I think that he is going (6/25) | I think he is going (5/20) | I think is going (4/17) | (a) は無損失。(b) は主語が消え、誰が行くのか不明 |
| I know that people are here (6/28) | I know people are here (5/23) | I know are here (4/16) | (a) は「人々を知っている」と NP 目的語に誤読されうる（曖昧化）。このため規則では削除しない。(b) は非文 |
| I know that she left (5/21) | I know she left (4/16) | I know left (3/12) | (a) は無損失（代名詞主語+動詞で節と確定）。(b) は主語が消える |
| She said that we will go (6/25) | She said we will go (5/20) | She said will go (4/17) | (a) は無損失。(b) は主語が消え、「彼女が行く」とも読める |
| I see that the door is open (7/28) | I see the door is open (6/23) | I see door is open (5/19) | (a) は「ドアを見る」と節の両読み（園路文）だが、規則では削除しない。(b) は限定詞が消える |
| I told her that I left (6/23) | I told her I left (5/18) | I told her left (4/16) | (a) は無損失（今回の規則は動詞直後の that のみが対象で、目的語を挟む例は未対応）。(b) は「彼女に left と伝えた」のように崩れる |
| I hope that it works (5/21) | I hope it works (4/16) | I hope works (3/13) | (a) は無損失。(b) は非文 |

まとめ:
- (a) で意味が損なわれうるのは、NP 目的語動詞の直後に名詞句が来る場合だけ。今回の規則はこの場合を除外している。
- (b) は常に主語か限定詞を失うため、採用しない。

## AI 可読性（未検証）
LLM は補文標識のない英語（I think he is going）を通常の英語として問題なく読めるはずだ、という見込み。一方 (b) 型の欠落は主語の推測を強いるため、誤読が増えると考えられる。いずれも推測で、モデルを使った読解評価はまだ行っていない。
