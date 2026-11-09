# Unicode外の歴史的記法・補助体系の追加実測

測定日時: 2026-11-07T17:11:12.113751+09:00 (JST)
TalkCompress HEAD: `3c29092e21a5cf503d71382ef23433c63fbba6e8` / Python 3.14.8 / tiktoken 0.14.0 / o200k_base
計 21,681 category×exact-text 行、文字列として 21,652 種。

AI 可読性: **未測定**。意味保持・復元・図形理解は未測定。

|カテゴリ|件数|o200k平均|過小/一致/過大|MAE|
|---|---:|---:|---|---:|
|abc_synthetic_example|2|95.000|0/1/1|4.500|
|bliss_bci_gloss|6551|4.607|3855/2517/179|0.910|
|bliss_bci_id|6551|2.000|0/6551/0|0.000|
|braille_ascii|64|1.000|2/62/0|0.031|
|braille_dots_notation|64|1.344|0/64/0|0.000|
|braille_unicode_cell|64|2.969|63/0/1|1.000|
|mdc_documentation_fragment|280|7.471|44/52/184|1.850|
|mdc_sign_code|6800|2.394|54/6746/0|0.009|
|mdc_transliteration|1198|2.124|858/326/14|0.867|
|oracc_atf_example|8|44.750|8/0/0|6.875|
|tex_short_example|99|36.182|80/13/6|5.384|

## 分布・代表例

### abc_synthetic_example
- o200k分布: `{"44": 1, "146": 1}`
- delta = estimate−o200k: `{"0": 1, "9": 1}`
- 安い例（o200k→bytes）: `[{"text": "X:1\nL:1/8\nM:4/4\n%%score (S A)\nK:C\n[V:S]G2 cc3 ||\n[V:A]E2E (EFG) ||", "o200k": 44, "estimate": 44, "utf8_bytes": 66}, {"text": "X:1\nL:1/8\nM:4/4\n%%score (S A) (T B)\nK:C\n[V:S](EFGCF2) (EF) | (E2D2) C4 | (f2e)c ||\n[V:A](C4CB,) C2 | (C2B,2) C4 | (c2G)E ||\n[V:T](G,4 A,F,) (G,F,) | G,2>F,2 E,4 | f(e c2) ||\n[V:B](C,D, E,2 D,2) (C,A,,) | G,,4 C,4 | c(G E2) ||\n", "o200k": 146, "estimate": 155, "utf8_bytes": 226}]`
- 高い例（o200k降順→bytes昇順）: `[{"text": "X:1\nL:1/8\nM:4/4\n%%score (S A) (T B)\nK:C\n[V:S](EFGCF2) (EF) | (E2D2) C4 | (f2e)c ||\n[V:A](C4CB,) C2 | (C2B,2) C4 | (c2G)E ||\n[V:T](G,4 A,F,) (G,F,) | G,2>F,2 E,4 | f(e c2) ||\n[V:B](C,D, E,2 D,2) (C,A,,) | G,,4 C,4 | c(G E2) ||\n", "o200k": 146, "estimate": 155, "utf8_bytes": 226}, {"text": "X:1\nL:1/8\nM:4/4\n%%score (S A)\nK:C\n[V:S]G2 cc3 ||\n[V:A]E2E (EFG) ||", "o200k": 44, "estimate": 44, "utf8_bytes": 66}]`

### bliss_bci_gloss
- o200k分布: `{"1": 670, "2": 1212, "3": 849, "4": 984, "5": 855, "6": 534, "7": 427, "8": 338, "9": 233, "10": 155, "11": 110, "12": 62, "13": 45, "14": 23, "15": 18, "16": 14, "17": 6, "18": 6, "19": 2, "20": 2, "22": 3, "24": 1, "25": 2}`
- delta = estimate−o200k: `{"-9": 1, "-8": 1, "-7": 2, "-6": 5, "-5": 26, "-4": 89, "-3": 270, "-2": 935, "-1": 2526, "0": 2517, "1": 153, "2": 24, "3": 2}`
- 安い例（o200k→bytes）: `[{"text": "CD", "o200k": 1, "estimate": 1, "utf8_bytes": 2}, {"text": "at", "o200k": 1, "estimate": 1, "utf8_bytes": 2}, {"text": "if", "o200k": 1, "estimate": 1, "utf8_bytes": 2}]`
- 高い例（o200k降順→bytes昇順）: `[{"text": "church_ruin,temple_ruin,wreck,wreckage_(church,temple,mosque)_(1)", "o200k": 25, "estimate": 20, "utf8_bytes": 65}, {"text": "church_ruin,temple_ruin,wreck,wreckage_(church,temple,mosque)_(2)", "o200k": 25, "estimate": 20, "utf8_bytes": 65}, {"text": "apparent(ly),clear(ly),evident(ly),obvious(ly),plain(ly)", "o200k": 24, "estimate": 20, "utf8_bytes": 56}]`

### bliss_bci_id
- o200k分布: `{"2": 6551}`
- delta = estimate−o200k: `{"0": 6551}`
- 安い例（o200k→bytes）: `[{"text": "8483", "o200k": 2, "estimate": 2, "utf8_bytes": 4}, {"text": "8484", "o200k": 2, "estimate": 2, "utf8_bytes": 4}, {"text": "8485", "o200k": 2, "estimate": 2, "utf8_bytes": 4}]`
- 高い例（o200k降順→bytes昇順）: `[{"text": "8483", "o200k": 2, "estimate": 2, "utf8_bytes": 4}, {"text": "8484", "o200k": 2, "estimate": 2, "utf8_bytes": 4}, {"text": "8485", "o200k": 2, "estimate": 2, "utf8_bytes": 4}]`

### braille_ascii
- o200k分布: `{"1": 64}`
- delta = estimate−o200k: `{"-1": 2, "0": 62}`
- 安い例（o200k→bytes）: `[{"text": " ", "o200k": 1, "estimate": 0, "utf8_bytes": 1}, {"text": "!", "o200k": 1, "estimate": 1, "utf8_bytes": 1}, {"text": "\"", "o200k": 1, "estimate": 1, "utf8_bytes": 1}]`
- 高い例（o200k降順→bytes昇順）: `[{"text": " ", "o200k": 1, "estimate": 0, "utf8_bytes": 1}, {"text": "!", "o200k": 1, "estimate": 1, "utf8_bytes": 1}, {"text": "\"", "o200k": 1, "estimate": 1, "utf8_bytes": 1}]`

### braille_dots_notation
- o200k分布: `{"1": 42, "2": 22}`
- delta = estimate−o200k: `{"0": 64}`
- 安い例（o200k→bytes）: `[{"text": "0", "o200k": 1, "estimate": 1, "utf8_bytes": 1}, {"text": "1", "o200k": 1, "estimate": 1, "utf8_bytes": 1}, {"text": "2", "o200k": 1, "estimate": 1, "utf8_bytes": 1}]`
- 高い例（o200k降順→bytes昇順）: `[{"text": "1234", "o200k": 2, "estimate": 2, "utf8_bytes": 4}, {"text": "1235", "o200k": 2, "estimate": 2, "utf8_bytes": 4}, {"text": "1236", "o200k": 2, "estimate": 2, "utf8_bytes": 4}]`

### braille_unicode_cell
- o200k分布: `{"1": 1, "3": 63}`
- delta = estimate−o200k: `{"-1": 63, "1": 1}`
- 安い例（o200k→bytes）: `[{"text": "⠀", "o200k": 1, "estimate": 2, "utf8_bytes": 3}, {"text": "⠁", "o200k": 3, "estimate": 2, "utf8_bytes": 3}, {"text": "⠂", "o200k": 3, "estimate": 2, "utf8_bytes": 3}]`
- 高い例（o200k降順→bytes昇順）: `[{"text": "⠁", "o200k": 3, "estimate": 2, "utf8_bytes": 3}, {"text": "⠂", "o200k": 3, "estimate": 2, "utf8_bytes": 3}, {"text": "⠃", "o200k": 3, "estimate": 2, "utf8_bytes": 3}]`

### mdc_documentation_fragment
- o200k分布: `{"1": 2, "2": 13, "3": 92, "4": 28, "5": 27, "6": 26, "7": 17, "8": 11, "9": 12, "10": 5, "11": 4, "12": 8, "13": 7, "14": 5, "15": 2, "16": 2, "17": 1, "18": 1, "19": 1, "21": 1, "22": 3, "27": 2, "28": 1, "32": 1, "38": 1, "40": 1, "41": 1, "46": 1, "49": 1, "60": 1, "61": 1, "67": 1}`
- delta = estimate−o200k: `{"-7": 1, "-4": 2, "-3": 6, "-2": 5, "-1": 30, "0": 52, "1": 118, "2": 14, "3": 17, "4": 14, "5": 3, "6": 6, "7": 3, "8": 1, "10": 1, "11": 2, "12": 1, "13": 2, "16": 1, "26": 1}`
- 安い例（o200k→bytes）: `[{"text": "-", "o200k": 1, "estimate": 1, "utf8_bytes": 1}, {"text": "!\n", "o200k": 1, "estimate": 1, "utf8_bytes": 2}, {"text": "X-", "o200k": 2, "estimate": 2, "utf8_bytes": 2}]`
- 高い例（o200k降順→bytes昇順）: `[{"text": "-D35:n-wn-n:m-t:Z6:k-Hr*Z1-N25:t*Z1-D35:n-b\\98**s{{582,0,100}}**K5\\R13\\red{{898,184,82}}-t-W-T14-D37-A1:Z2-!\n", "o200k": 67, "estimate": 79, "utf8_bytes": 109}, {"text": "-di-n:f-A-H-t:N17-N38:10*10*10*10*10-sTA:E15{{15,0,98}}**100\\R321{{0,295,55}}-n-t^^^mwt-n:nb-b-s-n:t-B1-!\n", "o200k": 61, "estimate": 72, "utf8_bytes": 106}, {"text": "-!\nU2:ir-A-A-n:A1-r:a-C2B-ms-s-B3-G17A-s-f:N5-r-x:p-D46:t-K23\\red:F51B*F51B-n-mH&&&(n:n:n)-wr:r:t-E4-I12", "o200k": 60, "estimate": 86, "utf8_bytes": 104}]`

### mdc_sign_code
- o200k分布: `{"1": 1, "2": 4230, "3": 2527, "4": 11, "5": 3, "6": 20, "7": 8}`
- delta = estimate−o200k: `{"-2": 10, "-1": 44, "0": 6746}`
- 安い例（o200k→bytes）: `[{"text": "nn", "o200k": 1, "estimate": 1, "utf8_bytes": 2}, {"text": "A1", "o200k": 2, "estimate": 2, "utf8_bytes": 2}, {"text": "A2", "o200k": 2, "estimate": 2, "utf8_bytes": 2}]`
- 高い例（o200k降順→bytes昇順）: `[{"text": "US1A6BEXTU", "o200k": 7, "estimate": 5, "utf8_bytes": 10}, {"text": "US1X6AEXTU", "o200k": 7, "estimate": 5, "utf8_bytes": 10}, {"text": "US1E28AEXTU", "o200k": 7, "estimate": 5, "utf8_bytes": 11}]`

### mdc_transliteration
- o200k分布: `{"1": 278, "2": 641, "3": 185, "4": 65, "5": 19, "6": 3, "7": 3, "8": 3, "12": 1}`
- delta = estimate−o200k: `{"-3": 4, "-2": 159, "-1": 695, "0": 326, "1": 14}`
- 安い例（o200k→bytes）: `[{"text": "1", "o200k": 1, "estimate": 1, "utf8_bytes": 1}, {"text": "2", "o200k": 1, "estimate": 1, "utf8_bytes": 1}, {"text": "3", "o200k": 1, "estimate": 1, "utf8_bytes": 1}]`
- 高い例（o200k降順→bytes昇順）: `[{"text": "Hr-bHdty-nTr-aA-nb-pt", "o200k": 12, "estimate": 11, "utf8_bytes": 21}, {"text": "Imn-Hr-xpS-f", "o200k": 8, "estimate": 7, "utf8_bytes": 12}, {"text": "imn-Hr-xpS-f", "o200k": 8, "estimate": 7, "utf8_bytes": 12}]`

### oracc_atf_example
- o200k分布: `{"15": 1, "16": 2, "19": 2, "31": 1, "99": 1, "143": 1}`
- delta = estimate−o200k: `{"-22": 1, "-15": 1, "-5": 1, "-4": 1, "-3": 1, "-2": 3}`
- 安い例（o200k→bytes）: `[{"text": "1.   a\na+1. e\n2'.  i", "o200k": 15, "estimate": 11, "utf8_bytes": 20}, {"text": "&P123123=UET 3,2\n1. a & e", "o200k": 16, "estimate": 14, "utf8_bytes": 25}, {"text": "&P123123=UET 3,2\n1. a , e", "o200k": 16, "estimate": 14, "utf8_bytes": 25}]`
- 高い例（o200k降順→bytes昇順）: `[{"text": "&P348865 = SpTU 5, 283\n#project: cams\n#atf: lang akk-x-ltebab\n#atf: use unicode\n\n@tablet\n\n@obverse\n1.\tṭup-pi! E₂ ep-šu₂ sip-pu rak-su E₂ rug-gu-bu\n2.\t{giš}IG SAG.KUL kun-nu KI{+ti₃} {id₂}har ša₂ {d}NA₃\n$ single ruling\n3.\t40?# ina 1 KUŠ₃ US₂ AN.TA {tu₁₅}SI.SA₂ DA E₂ ša₂ ", "o200k": 143, "estimate": 121, "utf8_bytes": 305}, {"text": "&P348658 = SpTU 2, 055\n#project: cams\n#atf: lang akk-x-ltebab\n#atf: use unicode\n\n@tablet\n\n@obverse\n1.\tṭup-pi A.ŠA₃ ki-šub-ba#-[a ...]\n2.\t{id₂}har-ri ša₂ {d}MUATI? x [...]\n3.\tša₂ qe₂-reb UNUG#[{ki}]", "o200k": 99, "estimate": 84, "utf8_bytes": 213}, {"text": "&P555555 = Some Publication 32\n@obverse\n1. 1(diš) udu ba-ug₇\n$ reverse blank", "o200k": 31, "estimate": 26, "utf8_bytes": 79}]`

### tex_short_example
- o200k分布: `{"1": 1, "5": 1, "7": 2, "8": 3, "9": 1, "10": 2, "11": 2, "12": 2, "15": 2, "17": 4, "18": 2, "19": 2, "20": 3, "21": 2, "22": 2, "23": 4, "24": 10, "25": 4, "27": 2, "28": 1, "29": 2, "30": 2, "32": 1, "34": 1, "35": 1, "36": 1, "37": 2, "38": 1, "39": 1, "40": 1, "41": 3, "42": 1, "44": 1, "48": 1, "49": 2, "50": 1, "51": 1, "53": 3, "54": 3, "55": 1, "56": 1, "58": 1, "62": 2, "64": 1, "68": 2, "71": 1, "75": 1, "77": 1, "81": 3, "83": 1, "88": 1, "93": 1, "185": 1}`
- delta = estimate−o200k: `{"-25": 1, "-22": 2, "-18": 2, "-17": 1, "-15": 2, "-14": 1, "-12": 1, "-11": 3, "-10": 4, "-9": 1, "-8": 6, "-7": 4, "-6": 8, "-5": 11, "-4": 9, "-3": 6, "-2": 11, "-1": 7, "0": 13, "1": 2, "2": 3, "3": 1}`
- 安い例（o200k→bytes）: `[{"text": "a", "o200k": 1, "estimate": 1, "utf8_bytes": 1}, {"text": "A =\\!= B", "o200k": 5, "estimate": 3, "utf8_bytes": 8}, {"text": "x^{\\Huge y}z", "o200k": 7, "estimate": 6, "utf8_bytes": 12}]`
- 高い例（o200k降順→bytes昇順）: `[{"text": "\\begin{array}{l}\n    𝐀𝐚𝟎𝐴𝑎𝑨𝒂𝔅𝔞𝔸𝒜 \\\\\n    𝖠𝖺𝟢𝗔𝗮𝟬𝘈𝘢𝙰𝚊𝟶 \\\\\n    \\text{𝐀𝐚𝟎𝐴𝑎𝑨𝒂𝔅𝔞𝔸𝒜} \\\\\n    \\text{𝖠𝖺𝟢𝗔𝗮𝟬𝘈𝘢𝙰𝚊𝟶} \\\\\n    \\mathrm{𝐀𝐚𝑨𝒂𝔅𝔞𝔸𝒜} \\\\\n\\end{array}\n", "o200k": 185, "estimate": 173, "utf8_bytes": 300}, {"text": "f(a,b)=\\begin{cases}\n    a+1&\\text{if }b\\text{ is odd} \\\\\n    a&\\text{if }b=0 \\\\\n    a-1&\\text{otherwise}\n\\end{cases} \\\\\n\\begin{rcases}\n    a &\\text{if } b \\\\\n    c &\\text{if } d\n\\end{rcases}⇒…\n", "o200k": 93, "estimate": 75, "utf8_bytes": 198}, {"text": "\\begin{array}{l}\n    \\text{``a'' b---c -- d----`e'-{-}-f} -- \\\\\n    \\text{\\it ``a'' b---c -- d----`e'-{-}-f} ``x'' \\\\\n    \\text{\\tt ``a''---} \\texttt{``a''---} \\mathtt{--} \\\\\n\\end{array}\n", "o200k": 88, "estimate": 66, "utf8_bytes": 187}]`

## 出典・許諾・取得限界

- BCI AV 2026-09-12の公式ID/glossテキストは6,551レコード（空行を除外、ID重複なし）。IDと英語glossを別入力として測定。glossのunderscore/カンマ/括弧を変更しない。SVG/画像は取得せず、label/IDのtoken数を図形理解と取り違えない。
- 必須BCI帰属: The Blissymbolics Communication International Authorized Vocabulary (BCI-AV) is available at www.blissymbolics.org. The BCI-AV and other BCI Blissymbol products are copyright Blissymbolics Communication International (BCI) and made available under the Creative Commons BY 4.0 licence.
- BCI公式許諾: https://blissymbolics.org/index.php/licensing （HTML snapshot同梱）。CC BY 4.0 https://creativecommons.org/licenses/by/4.0/ 。変更内容はフィールド抽出・重複統合・token/estimate等の測定metadata追加。
- MdC: JSesh READMEが signs_description.xml を明示的にCC BY 4.0で提供すると記載。符号・転写キー・説明中のhieroglyph mode部分文字列だけを測定。図形・フォントは未取得。断片は境界が不完全なことがあり、MdCレンダラでの文法検証や、特定古代文書の完全な再現を保証しない。
- rosmord/MDC-texts の文献.glyはREADMEが「明確な場合は各テキスト内に許諾」とする一方、確認したデモ2ファイルには明示許諾が見当たらず、そこからの一括収録を見送った。CC BYを推奨していることを、全ファイルへのライセンス付与と解釈しない。
- ORACC: 公開ATF documentationの索引に掲載された8例を収録。文書は既定CC BY-SA 3.0。原ページのlive取得は500/504またはTLS証明書検証エラーで失敗したため、WebSearchのindexed quotationを転記。元HTMLを取得したとは記載せず、hashもlocal excerpt snapshotであると明記。コードブロックの外側の空行は含めていない。Oraccと文書作成者の帰属、CC BY-SA 3.0を保持。異なる条件の個別プロジェクト資料は未取得。
- 点字: liblouis en-us-brf.dis のNorth American六点Braille ASCII 64セル。元ASCII・点番号列・Unicode点字の3表現を測定。原ファイルはLGPL-2.1-or-laterの明示ヘッダ。元テーブル・COPYING・COPYING.LESSERを同梱。一般的な英語/日本語文章の点訳・縮約の妥当性や触覚による理解は未測定。
- ABC: MIT abcjsのslur位置確認用の合成テスト2例のみ。曲データベースや商用楽譜は未取得。
- TeX: MIT KaTeXのvisual test corpusから200 codepoints以下の99例を抽出（同一文字列は統合）。YAMLはsafe_loadで読み、取得コードは実行していない。長い大規模式128例全体の網羅ではない。
- ソースごとに異なる許諾を保持する。リポジトリ全体のMIT表示だけでCC BY-SAやLGPL由来データをMITに再許諾したことにはできない。再配布時は同梱原本と帰属/NOTICEを残す。
- 入力はNFC/NFD変換・stripなし、encode_ordinaryでbareと先頭ASCII space1個を別測定。estimate内部の正規化は現行実装どおり。前後文脈・専門家の意味解釈・全ての古代文字/数式/記法は未検証。
- /workspace/TalkCompress・利用者PC不使用。実装変更・PR・commit・pushなし。

## 取得ソース一覧

- abcjs-slurs.js: https://raw.githubusercontent.com/paulrosen/abcjs/main/tests/visual/slurs.test.js / MIT / SHA256 `a59dadc6412ba38347eac2fadb18bbbe121f7e8e57861c870fc7b5de9c224d4c`
- bci-id-gloss.txt: https://www.blissymbolics.net/BCI-AV_2026-09-12/BCI-AV_SKOG_2026-09-12_id_to_gloss_map.txt / CC-BY-4.0 / SHA256 `77a16fdb2339b8b756ee3155913b056e765a0bc0dc6b418afd49585c7efc5001`
- brf.dis: https://raw.githubusercontent.com/liblouis/liblouis/master/tables/en-us-brf.dis / LGPL-2.1-or-later / SHA256 `47ff9400f4b8a0206b0c1942e13c32b539d17ec099dcd1097873a1b9f5cb8b3c`
- jsesh-signs.xml: https://raw.githubusercontent.com/rosmord/jsesh/master/jsesh/src/main/resources/jsesh/glyphs/resources/signs_description.xml / CC-BY-4.0 / SHA256 `4701c34ee0012c50b0a291027c0ed48b4389404a4cb92a81808fcc4d4c85d8cd`
- katex-expressions.txt: https://raw.githubusercontent.com/KaTeX/KaTeX/main/test/screenshotter/ss_data.yaml / MIT / SHA256 `a5b1fb7b123dea398d04ffddef530a26af9e5f099244be2675f11aceb3f5baba`
- oracc-indexed-excerpts.json: https://oracc.museum.upenn.edu/doc/help/editinginatf/primer/index.html / CC-BY-SA-3.0 / SHA256 `9fd647226bb32a084cf7c6c7e8719717039f199027d0be3aa6b17a3bcd4a716a`

JSONL SHA256: `2dce367c60a2637a4df477b8c877c41a87adcdf366c08b273c42c128bf1cce20`

## 再検証

全21,681行のJSON parse・重複キー・token IDs・bare/leading-space実測・estimate・delta・bytes・帰属情報を独立再計算: PASS。全体: {'exact': 16332, 'over': 385, 'under': 4964}。実装変更なしのためリポジトリpytestは未実行。
