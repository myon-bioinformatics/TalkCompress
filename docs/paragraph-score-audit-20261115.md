# 段落往復ベンチ `score_answer` の採点監査（2026-11-15、t1232u）

対象は `scripts/paragraph_roundtrip.py` の `score_answer` が出す 3 指標（exact / semantic_rule /
notation_tolerant）。PR #183 の 3 シード（`66f3070`）の raw 回答はそのまま使い、raw・pack・items・sources は
変更していない。3 シード × 3 方式 × 全文の gold/回答ペア（整列後 2312 行）を、規則の判定と私（GitHubヘルプ5bot）の
手作業の判定とで突き合わせた。行ごとの判定と理由は作業ディレクトリの `score_audit_cases.tsv` にある
（リポジトリには入れていない）。

## 方法

1. 3 指標すべて一致の 1922 行のうち、原文と回答の文字列が異なる 114 行を全件見た。差は句読点・引用符・
   空白（`\u2009`、`\xa0`）・コンマだけで、exact の誤合格（FP）はなかった。
2. 3 指標のどれかで不一致の 390 行は、トークン単位の差分（210 種）を一つずつ型に分類した
   （同じ差分は同じ型）。行の型は、内容変化（CHG）が一つでもあれば「正しい不一致」、
   なければ判定モデル型（SYN/SRC/NAME/ORDER）、それもなければ規則型とした。
3. FN は「意味は同じなのに不一致」、FP は「意味が変わったのに合格」。数は gold 文の数。

## FN/FP の型別件数（監査前 → 監査後、exact/semantic_rule/notation_tolerant）

| 型 | 文 | FN 前 | FN 後 | 例 |
|---|---:|---|---|---|
| 規則: 行の切れ目のずれ（内容同一） | 4 | 4/4/4 | 0/0/0 | en-pd-02\|BEF s3（`Mr.` の後で改行） |
| 規則: 前置詞+冠詞の縮約（pt do/pro） | 8 | 8/8/8 | 8/0/0 | pt-flores-02 `pro`→`para o`、pt-flores-01 `do`→`de` |
| 規則: ギリシャ語アクセント欠落 | 7 | 7/7/7 | 7/7/0 | el-flores-01 `μελη`→`μέλη` |
| 規則: 文字と数字の空白 | 5 | 5/5/5 | 5/5/0 | cs-flores-02 `minimálně100` |
| 規則: ラテン語ローマ数字 ↔ 数詞 | 4 | 4/4/4 | 4/4/0 | la-caesar-04 `XV`→`quindecim` |
| 規則: CJK 後の括弧ラテン文字注記 | 4 | 4/4/4 | 4/4/0 | zh-flores-03\|BEF s3 `利金斯 (Liggins)`→`利金斯` |
| 規則: towards/toward | 3 | 3/3/3 | 3/3/0 | en-flores-01\|CEF |
| 規則: 単位名 ↔ 記号 | 2 | 2/2/2 | 2/2/0 | ja-flores-02 `100～250 m`→`100～250メートル` |
| 既存で許容: 冠詞・指示詞（+縮約） | 25 | 25/0/0 | 25/0/0 | en-flores-03 `the Auckland's`→`Auckland's` |
| 既存で許容: 空白・全角括弧 | 17 | 17/0/0 | 17/0/0 | zh-flores-03 `从 1959 年`→`从1959年` |
| 既存で許容: 引用符・アポストロフィ | 15 | 15/15/0 | 15/15/0 | en-flores-03 `father’s` |
| 既存で許容: 数詞・per cent（+冠詞） | 9 | 9/9/0 | 9/9/0 | en-flores-05 `eighteen`→`18` |
| 既存で許容: 英語の縮約 | 1 | 1/0/0 | 1/0/0 | en-flores-06 `They are`→`They're` |
| 判定モデル: 同義語・言い換え | 175 | 175/175/175 | 同じ | de `Antwort`→`Reaktion`、pl `zaczął`→`rozpoczął` |
| 判定モデル: 原文側の誤りを判定役が校正 | 72 | 72/72/72 | 同じ | fr `PEC`→`CEP`、ja `欧州委員会`→`CEP` |
| 判定モデル: 固有名詞の音訳・表記 | 18 | 18/18/18 | 同じ | el `Μαρτελί`→`Μαρτέλι`、cs `Gillard`→`Gillardová` |
| 判定モデル: 語順 | 3 | 3/3/3 | 同じ | ja `エリザベス女王2世`→`エリザベス2世女王` |
| 判定モデル: ラテン語の分かち書き | 1 | 1/1/1 | 同じ | la-caesar-04 `non numquam`→`nonnumquam` |
| 正しい不一致: 内容の変化 | 14 | FP 0/0/0 | FP 0/0/0 | en `at least`→`about`、pl/cs 接続詞 `a` の脱落 |
| 正しい不一致: コーデック由来 | 3 | FP 0/0/0 | FP 0/0/0 | en-pd-04\|BEF（圧縮文の `&:"` が `And:` に） |

exact は意図的に厳格なので、表記型の FN が exact に残るのは仕様どおり。

**FP について。** 実データで意味が変わったのに合格した文はなかった（0 件）。境界例として、
`The Hare`→`A Hare`（en-pd-01\|BEF s1、定・不定）と `this view`→`that view`（en-flores-04\|CEF 3 シード）が
semantic_rule で合格する。どちらも意味は保たれていると判定した。一方で、実データには出ていない
**潜在的な FP** が規則にあった。監査前のコードで次はすべて合格していた（新しいテストで確認）:

* `29%` ↔ `29`、`−5` ↔ `5`、`$5` ↔ `€5`（`roundtrip.norm` と `loose()` が記号を落とすため、
  **exact でも合格**）。
* 行数が同じで切れ目だけずれた段落が `paragraph_exact` になる。

否定の脱落（`not`、`can't`→`can`、`never`、pl `nie`）と数値の変更（`eighteen`→`80`、`18`→`19`、
`1,400`→`1,500`）は監査前から全指標で不一致になっており、テストで固定した。

## 修正（`scripts/paragraph_roundtrip.py`）

* `MEANING_SYMBOLS`（`% ‰ ° $ € £ ¥ + ±` と数字直前のマイナス）を全指標で保持する。exact は
  `roundtrip.norm` の一致に加えて、この記号列の一致も要求する（`roundtrip.norm` 自体は他のベンチと
  共有なので変えていない）。
* `loose()`: 英語の `can't/cannot/won't/shan't`、前置詞+冠詞の縮約表（pt/es/fr/it/de、閉じた表）。
* `notation_form(s, lang)`: 文字と数字の境界、単位名、towards/toward、ja/zh の括弧ラテン文字注記、
  la のローマ数字と数詞。`notation_equal()` でギリシャ語のアクセント欠落（4 文字以上、片側が無アクセント）。
* `regroup()`: 失敗が連続する整列ペアのうち、連結した内容が等しい最短の区間を 1 行（`merge_split`）にまとめる。
  指標ごとに exact → semantic_rule → notation_tolerant の順。区間内に一語でも違いがあれば不一致のまま。
* `paragraph_exact` は全ペアが 1-1（`merge_split`・追加・脱落なし）であることも要求する。

## 監査前後の数値（3 シード、方式あたり 771 文・180 判定、計測値）

| 方式 | 指標 | 前 | 後 |
|---|---|---|---|
| control | exact | 699 (90.66%) | 699 (90.66%) |
| control | semantic_rule | 703 (91.18%) | 703 (91.18%) |
| control | notation_tolerant | 708 (91.83%) | 716 (92.87%) |
| control | 段落 exact | 126/180 (70.00%) | 126/180 (70.00%) |
| CEF | exact | 610 (79.12%) | 610 (79.12%) |
| CEF | semantic_rule | 627 (81.32%) | 632 (81.97%) |
| CEF | notation_tolerant | 640 (83.01%) | 654 (84.82%) |
| CEF | 段落 exact | 92/180 (51.11%) | 92/180 (51.11%) |
| BEF | exact | 614 (79.64%) | 618 (80.16%) |
| BEF | semantic_rule | 636 (82.49%) | 643 (83.40%) |
| BEF | notation_tolerant | 642 (83.27%) | 657 (85.21%) |
| BEF | 段落 exact | 73/180 (40.56%) | 73/180 (40.56%) |

文単位の変化は exact +4、semantic_rule +12、notation_tolerant +37 で、下がった文は 0。

## 規則では決められず、判定モデルに回すべき型

計 269 文（監査後もすべての指標で不一致）。

1. **同義語・言い換え（175 文）**: de `Antwort`→`Reaktion`・`Anwendung`→`Applikation`、en `speed up`→`accelerate`・
   `prior to`→`before`・`in excess of`→`more than`、pl `zaczął`→`rozpoczął`・`iż`→`że`・`by`→`aby`、
   ja の助詞（`は`→`が`、`から`→`に`）と文体（`した`→`しました`）、es `Desde 2008`→`En comparación con 2008`。
   最後の例のように意味の差がわずかに出るものもあるので、閉じた同義語表では決められない。
2. **原文側の誤りの校正（72 文）**: fr `PEC`→`CEP`、ja `欧州委員会`→`CEP` と `委員会会`→`委員会`、
   pt `Eles … frios`→`Elas … frias`、zh `在…中宣誓就职`→`让…宣誓就职`（宣誓の主体が直る）、es `haya Australia`→
   `haya en Australia`、cs `v přeměnu`→`s přeměnou`。gold が誤っているので、判定モデルと原文確認の両方が要る。
3. **固有名詞の音訳・表記（18 文）**: el `Μαρτελί`↔`Μαρτέλι`、`Auckland`→`Όκλαντ`、cs `Gillard`→`Gillardová`、
   zh `马特利`→`马尔泰利`。
4. **語順（3 文）** と **ラテン語の分かち書き（1 文）**。
5. 境界例: pl/cs の接続詞 `a` の脱落（8 文）は内容変化として数えたが、意味はほぼ保たれる。
   en-pd-01 の目的語 `me` の補完、`result`→`results` も判定モデル向け。

`?` の有無（疑問文か平叙文か）は `roundtrip.norm` が句読点を落とすため全指標で同一扱いになる。
実データには出ていないので、今回は直していない（未測定）。AI 可読性は未測定。
