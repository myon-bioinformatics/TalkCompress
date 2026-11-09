# 非日本語の文字顔・旧来の反応表記: o200k測定

## 成果物と対象

- データ: `kaomoji-i18n-o200k.jsonl`。全行がデータ行のUTF-8 JSONL。
- TalkCompress HEAD: **84e5dca0028d90db73254af33ac2d9d3ce545790**。
- Python **3.14.8**、Unicode DB **16.0.0**、tiktoken **0.14.0**、encoding **o200k_base**。
- 出典取得日: **2026-11-07 JST**。変化するWebページの同日取得内容を使ったスナップショット調査。出典側の永久版IDは未取得。
- **530行 = 完全一致で重複排除したbare 487形 + 先頭ASCII空白probe 43行**。
- 日本固有のkaomoji一覧、2channel一覧、Unicode pictographの一覧は採取していない。Orzなど日本起源でも、日本以外での用法が出典に明記された形はその用法として収録。文字の発祥と利用地域は同じではない。
- 全世界の顔文字を網羅したものではない。多数のWestern ASCIIは明示ライセンス付き辞書、その他はWikipedia等と少数の事実例。
- **AI可読性: 未測定。意味保存: 未測定。利用頻度・各地域での普及率: 未測定。**

## 測定方法

`/workspace/tc-emoji-5bot/TesseraTalk/tessera_talk.py` の `estimate_tokens(raw)` と `len(tiktoken.get_encoding("o200k_base").encode(raw))` を同じraw文字列へ適用。tokenizerの前にNFC化、trim、幅変換、ハイフン置換はしない。UTF-8 byte数もraw入力から算出。`estimate_tokens` 自身のNFC化とNFD補正は現行mainのまま。

`pretokens` は推定器内部に合わせたNFC後の `_pretokens`。`normalized_text` も保存し、元入力の `text` / `codepoints` と混同しない。`estimate_minus_measured` は E−T。`locale` / `regions` / `source` / `license` は複数帰属を失わないため配列。`provenance` に出典名、著者、URL、ライセンス、取得日、原文一致か反復規則からの変種かを保存した。意味ラベルは最短の説明であり唯一の意味や安全な置換先ではない。

`context=leading-space` は測定者が1個のU+0020を追加した別のraw入力。bareとの統合はしない。同じbareを複数出典が記述している場合は新しい行を増やさず、地域・意味・出典を同じ行に追加した。例: `555` はThaiの笑いとChineseの泣きを両方保持する。

再現補助: `kaomoji-i18n-measure-5bot.py` と `kaomoji-i18n-meta-5bot.json`。スクリプトは外部JSの実行をせず、MIT辞書の文字列配列を `ast.literal_eval` で抽出した。書き込みは `open('x')` のため、既存成果物への上書きを拒否する。再計測時は出力先を別名にする必要がある。スクリプト内の上流ツール出力assetへのパスはこのbox用で、アップロード後の自己完結した再現手順ではない。JSONL自体に入力と測定値・全出典を持たせた。

全530行の今回結果: **E=T 210行、E<T 277行、E>T 43行**。意図的に集めた辞書と代表例に対する集計であり、自然文・地域別の推定精度を表す割合ではない。

## 地域別収録行数

同じ表記が複数地域にある場合は各行に複数タグを付けた。したがって下表は**非排他的な地域タグ別件数**で、縦合計は530行と一致しない。blank / length / case / ASCIIハイフンとU+2011の差を保った。

| 地域・区分 | bare | leading-space | 合計 |
|---|---:|---:|---:|
| その他の地域表記 | 12 | 0 | 12 |
| アゼルバイジャン | 1 | 1 | 2 |
| アラビア語圏・RTL | 3 | 3 | 6 |
| タイ | 9 | 4 | 13 |
| ヘブライ語・RTL | 19 | 4 | 23 |
| ベトナム | 6 | 4 | 10 |
| ロシア・スラヴ | 9 | 4 | 13 |
| 中国大陸 | 6 | 1 | 7 |
| 中国語圏（CN/TW/HK） | 19 | 5 | 24 |
| 北欧・欧州 | 3 | 2 | 5 |
| 国際・文字種借用 | 3 | 2 | 5 |
| 歴史・BBS/USENET | 16 | 1 | 17 |
| 西洋・汎用ASCII | 371 | 11 | 382 |
| 韓国 | 19 | 7 | 26 |

中国語圏は原資料がCN/TW/HKへの伝播を述べる広域タグ。各形のCN/TW/HK別の利用実証を得たという意味ではない。`)))` はruに加えuk、azでの記載を保持。「北欧・欧州」のÖ/Üは欧州のdiacritic例であり、北欧固有との断定ではない。「国際・文字種借用」は使用文字の由来と利用者地域を混同しないため独立させた。

## 出典とライセンス・帰属

Wikipedia/Wiktionaryの文章・選択を利用した部分は、各ページのcontributorsへ帰属。ページURLは履歴への入口も兼ねる。抽出・重複統合・ラベル要約・測定値追加という変更を行った。該当する派生部分は **CC BY-SA 4.0** として扱い、ライセンス条件を保持する。

- CC BY-SA 4.0: https://creativecommons.org/licenses/by-sa/4.0/
- Wikimediaの再利用条件（今回参照）: https://foundation.wikimedia.org/wiki/Policy:Terms_of_Use#7._Licensing_of_Content
- MIT辞書の原ライセンス全文・copyright noticeを **`kaomoji-i18n-emoticon-MIT-LICENSE.txt`** に保持した。辞書を含むデータを配布する際はこのファイルも同梱する。
- 「不明」の出典は公開閲覧できることを再利用許諾と取り違えていない。短い慣用形の用例という事実を少数採録し、本文、独自の長い説明、全辞書、画像をコピーしていない。これらの表記自体への独占権の有無を法的に保証するものではない。商用配布や単一ライセンス化の前に必要なら別途確認し、不明行を除外できるよう各行にタグを残した。
- この成果物全体や不明出典までをMIT/CC0だとは宣言しない。複数出典を持つ行についても個々のprovenanceを保持する。

| ID | 出典・著者（URL） | 確認したライセンス/扱い | 採録bare形数 |
|---|---|---|---:|
| mit | [emoticon/index.js](https://github.com/wooorm/emoticon/blob/main/index.js) — Titus Wormer | MIT | 322 |
| list | [List of emoticons](https://en.wikipedia.org/wiki/List_of_emoticons) — English Wikipedia contributors | CC BY-SA 4.0 | 49 |
| emoticon | [Emoticon](https://en.wikipedia.org/wiki/Emoticon) — English Wikipedia contributors | CC BY-SA 4.0 | 25 |
| lol | [LOL](https://en.wikipedia.org/wiki/LOL) — English Wikipedia contributors | CC BY-SA 4.0 | 24 |
| k | [ㅋㅋ](https://en.wikipedia.org/wiki/%E3%85%8B%E3%85%8B) — English Wikipedia contributors | CC BY-SA 4.0 | 4 |
| ko | [인터넷 신조어 목록](https://ko.wikipedia.org/wiki/%EC%9D%B8%ED%84%B0%EB%84%B7_%EC%8B%A0%EC%A1%B0%EC%96%B4_%EB%AA%A9%EB%A1%9D) — Korean Wikipedia contributors | CC BY-SA 4.0 | 2 |
| util | [Korean Text Emoticons](https://utileno.com/en/korean-emoticons/) — Utileno | 不明（公開再利用許諾を確認できず。短い慣用表現の代表例のみ） | 3 |
| orz | [失意體前屈](https://zh.wikipedia.org/wiki/%E5%A4%B1%E6%84%8F%E9%AB%94%E5%89%8D%E5%B1%88) — Chinese Wikipedia contributors | CC BY-SA 4.0 | 8 |
| jiongrz | [囧rz](https://en.wiktionary.org/wiki/%E5%9B%A7rz) — English Wiktionary contributors | CC BY-SA 4.0 | 1 |
| 233 | [233](https://zh.wiktionary.org/wiki/233) — Chinese Wiktionary contributors | CC BY-SA 4.0 | 3 |
| 555 | [555](https://en.wiktionary.org/wiki/555) — English Wiktionary contributors | CC BY-SA 4.0 | 6 |
| hhh | [hhh的意思](https://kmcha.com/cidian/hhh) — kmcha | 不明（公開再利用許諾を確認できず。短い慣用表現の代表例のみ） | 1 |
| qq | [QQ 表情大全](https://www.cnblogs.com/tzcwk/p/emoji.html) — tzc_wk | 不明（公開再利用許諾を確認できず。短い慣用表現の代表例のみ） | 3 |
| vi | [Icon =)), :)), :3, :v, ^^ là gì?](https://quantrimang.com/cuoc-song/icon-3-v-la-gi-167215) — QuanTriMang | 不明（公開再利用許諾を確認できず。短い慣用表現の代表例のみ） | 3 |
| modern | [How People Laugh Online in Different Languages](https://mymodernmet.com/laughing-online-in-different-languages/) — Larisa Crowder / My Modern Met | 不明（公開再利用許諾を確認できず。短い慣用表現の代表例のみ） | 5 |
| arab | [Positive / Negative Emoticons](https://www.saifmohammad.com/WebDocs/Arabic%20Lexicons/emoticons.txt) — Saif M. Mohammad website | 不明（公開再利用許諾を確認できず。短い慣用表現の代表例のみ） | 2 |
| he | [רגשון](https://he.wikipedia.org/wiki/%D7%A8%D7%92%D7%A9%D7%95%D7%9F) — Hebrew Wikipedia contributors | CC BY-SA 4.0 | 17 |
| brackets | [)))](https://en.wiktionary.org/wiki/)))) — English Wiktionary contributors | CC BY-SA 4.0 | 7 |
| itmo | [Russian Texting Slang Explained](https://news.itmo.ru/en/features/life_in_russia/news/13133/) — Marina Belyaeva / ITMO | 不明（公開再利用許諾を確認できず。短い慣用表現の代表例のみ） | 2 |
| mental | [16 Characters From Other Languages That Make Great Emoticons](https://www.mentalfloss.com/language/16-characters-other-languages-make-great-emoticons) — Arika Okrent / Mental Floss | 不明（公開再利用許諾を確認できず。短い慣用表現の代表例のみ） | 3 |
| duo | [Laughter Across Languages](https://blog.duolingo.com/laughter-in-different-languages/) — Stefanie Schantl / Duolingo | 不明（公開再利用許諾を確認できず。短い慣用表現の代表例のみ） | 4 |

全出典の取得日は2026-11-07 JST。上の形数は出典別の非排他的件数。
MIT index.jsの抽出スナップショットSHA-256: `728bcb15dd332140778e07388dd307aacff515f0a908c9bc7d2d35ef0fca6a86`。上流main URLなので、このhashは今回取得内容の識別用。

### ライセンス不明の出典からの採録範囲

- Utileno: `ㅇㅅㅇ`、`ㅠㅠ`、`ㅡㅡ` の短い3形だけ。
- kmcha: `hhh` の1形だけ。
- tzc_wkのQQリスト: `/wx`、`/ll`、`/xyx` の短い3aliasだけ。QQの入力aliasであり文字顔そのものではない。
- QuanTriMang: `=))`、`:))`、`:v` の3形だけ。記事本文はtimeoutし、検索で取得できた同記事の抜粋を根拠に用法を確認。本文全体の検証済みとは扱わない。
- My Modern Met: Vietnameseの `Hihihi`、`khà khà khà`、`hê hê`、Thaiの `55555`、`55555555+` の短い例だけ。
- Arabic Lexicons: `(:`、`(-:` のpositive分類だけ。Arabic圏での一般的な頻度の証明ではない。
- ITMO: `(` と `((` の悲しみ用法。後者はtwo-or-moreという明記規則による測定例。
- Mental Floss: Arabic系数字を借用した2形とThai文字を借用した1形。現地での利用を証明せず、文字種借用例として扱う。
- Duolingo: Arabic、Mandarin、Greekの短い笑い3形と、資料の反復可という規則に沿った `5555`。上のbare件数にはこの規則由来形も含む。

Korean Wiki Projectも調べたが、https://www.koreanwikiproject.com/wiki/Korean_Wiki_Project:Copyrights は **CC BY-NC-SA 3.0** と明記する。商用再利用自由なCC BY-SAとは異なるため、その辞書一覧のコピーは行わず、この成果物の採録出典として使っていない。

## 注目した今回の差 E / T

EはTalkCompress推定、Tはo200k実測。ここは全てbare入力。誤差の符号が逆のものもあり、tokenizer互換性や可読性を意味しない。

| 入力 | E | T | 分類経路 | 主な観察 |
|---|---:|---:|---|---|
| `:-)` | 1 | 2 | `p` | ASCII句読点runを一括1にする近似 |
| `:^)` | 1 | 2 | `p` | 鼻付きの旧来ASCII顔も同様 |
| `ㅇㅅㅇ` | 1 | 4 | `x` | compatibility jamoはxのrunに入りlen/4近似 |
| `ㅜㅜ` | 1 | 4 | `x` | 泣きjamoもxとして過小推定 |
| `ㅠㅠ` | 1 | 2 | `x` | 泣きjamoの種類で実測費用が違う |
| `ㅋㅋㅋ` | 1 | 2 | `x` | 反復は単なる見た目の字数ではない |
| `○&#124;￣&#124;_` | 2 | 5 | `p` | 中文圏で記録された姿勢表記。記号run近似とunderscore未捕捉 |
| `口丁乙` | 4 | 3 | `k` | kのCJK語彙/先頭処理による過大側の例 |
| `Orz` | 1 | 2 | `w` | ASCII語の辞書/長さ近似 |
| `๕๕๕` | 1 | 6 | `d` | Thai数字でもdがcより先にマッチし1/run |
| `ฮ่าฮ่าฮ่า` | 6 | 8 | `c` | Thai runは表のgreedy近似 |
| `=))` | 1 | 2 | `p` | Vietnameseで継続利用の旧Yahoo型 |
| `:v` | 2 | 1 | `p+w` | 一文字ずつはp+wだがBPEは全体1 |
| `khà khà khà` | 3 | 6 | `w+w+w` | アクセント付き笑いの語と空白文脈 |
| `٩◔̯◔۶` | 6 | 8 | `d+p+d` | Arabic系数字はd、目と結合記号はp。文字種借用の例 |

### 文脈・表記・意味の注意

- ロシア型 `)`、`))`、`)))` はbareではすべて1/1。一方 `))))))` は1/2、先頭空白付き ` )))` も1/2。括弧数に意味があり、短い形が同costでもまとめない。
- `555` はbareで1/1、`5555`は2/2。先頭空白版はそれぞれ1/2、2/3。数字3桁区切りと空白の差を保持する。
- 同じ `555` がThaiの笑い、Chineseの泣きになり得る。JSONLの同じ行に別ラベル・localeを残した。一般の数値や電話番号の意味はこの表の対象外だが、それらを否定するものではない。
- `(:` は1/1、`(-:`は1/2、Hebrewの `):` は1/1。RTLでは画面上の並びと実際の符号列を区別し、`codepoints` を必ず確認する。
- Hebrewの `חחח`、`ההה` は各1/3。Arabicの `هههههه` はbare2/2、先頭空白付き2/3。RTL文字列を反転したりbidi制御を勝手に入れたりしていない。
- Koreanの `ㅇㅅㅇ` はbare1/4、先頭空白版1/5。Hangul compatibility jamoのrunは、合成Hangulやconjoining jamoの経路とは異なる。
- `:v` はbare2/1、先頭空白版2/2。`Ö`、`Ü` はbare/先頭空白のどちらも1/1。
- ASCII `:-)` とnon-breaking hyphenの `:‑)` は別入力。大小文字、括弧数、幅、combining markを維持した。無差別な正規化で同一視しない。
- 上流MIT辞書の `:3` の識別名は `man` だが、他資料ではcat face等にも使われる。上流ラベルを意味の唯一解として採用しない。

## 見つからなかったもの・保留・制限

- 指定の `-̶_̶` を特に韓国用法として裏付ける信頼できる公開出典は、この検索では見つからなかった。未収録・未測定。見つからなかったことは不存在の証明ではない。
- 指定の **`=З)`** という正確な綴りを裏付ける採用可能な公開本文は得られなかった。検索では `=З` のcat face解説が出たが、RBC本文は401。近似の別綴りを根拠に捏造しないため未収録・未測定。
- ChineseのCN/TW/HK別の独自記号一覧は分離できていない。香港・台湾でのOrz流通を述べる資料は得たが、各形の地域別普及率は未測定。QQは公開aliasの短い代表だけで、QQ固有の全旧形式ではない。
- タイ国内固有の豊富な文字顔一覧、Arabic-letterだけで組んだ顔の現地利用を示す再利用可能な豊富な辞書は見つからなかった。英語記事のThai/Arabic文字借用例はあるが、それを現地用法と断定しない。
- mIRC固有の旧preset一覧をライセンス確認付きで採録するところまではできていない。Western ASCIIの明示MIT辞書と、BBS/Usenetの歴史資料は確保。紙面画像の字形復元やmultiline ASCII artは対象外。
- sourceが不明な大規模スクレイプ辞書や、CC BY-NC-SAの辞書全体はコピーしない。本文timeout、401、bot確認ページなどで検証できなかった箇所は上記のとおり。
- 各sourceは用例・記載の存在の根拠。起源説、全国民の習慣、統計的普及、文脈ごとの正確な感情解釈まで検証したものではない。
- 今回は測定・参照用データのみ。以前のlookup設計は変更せず、**estimate_tokens / runtime校正表を変更していない**。
- **AI可読性: 未測定。PRは開いていない。commit・push・GitHub投稿・他agentへの送信・アップロードは行っていない。**

## 作業境界

共有フォルダを最初に一覧確認したうえで、この担当の新規ファイルだけを作成。既存の他bot成果物を上書きしていない。禁止された `/workspace/TalkCompress` にはアクセスせず、ユーザーPCやmachineIdも不使用。TalkCompress checkoutのtracked差分はなし。

