結論：絵文字・記号の実コストは文字種の一律規則では決まらず、encoding別ルックアップ表を基本とし未知文字列は実際にencodeする方式が最も簡単です。o200kにはcl100kより安い絵文字が存在しますが、複雑なZWJ列は依然高価です。英語名より安い置換候補は確認できました。ただし意味を復元できるか、圧縮として品質を保てるかは未検証です。AI可読性: 未測定。
# トークナイザ実測

実施日: 2026-11-07 JST。公開Unicodeデータと公開tiktokenのみ使用。対象リポジトリ・利用者PC・PRは読み書きしていません。成果物はこのノートとcheap-symbols.jsonlのみ。
## 環境
Python: 3.14.8 (main, Oct  3 2026, 01:04:31) [Clang 22.1.3 ]
tiktoken: 0.14.0
UnicodeカテゴリDB: 16.0.0
encoding: o200k_base, cl100k_base, p50k_base, r50k_base
## 入力と方法
Unicode Emoji 17.0固定版: https://unicode.org/Public/17.0.0/emoji/emoji-test.txt
SHA-256: 1d8a944f88d7952f7ef7c5167fef3c67995bcae24543949710231b03a201acda
全行数（コメント除外）: 5225。status内訳: {'fully-qualified': 3944, 'unqualified': 243, 'minimally-qualified': 1029, 'component': 9}。主要集計母数はfully-qualified 3944件。componentは母数から分離。latestは18.0の可変データを返したため採用せず、安定固定版17.0を使用。
全mergeable rankをバイト列として走査（special tokenは除外）。valid UTF-8のみ文字分類。emoji_baseはemoji-testの構成文字からASCII・以下のcomponentを除いた集合。componentはZWJ、FE0E/FE0F、肌色、地域指標、keycap結合、tag文字。containsは部分文字を含むという意味で、複合語や先頭空白も含む。分類は非排他的。Emoji Unicode propertyそのものとは区別する。invalid UTF-8項目にもemojiのバイト接頭辞はあるがemoji文字として数えない。
tiktokenはUTF-8 byte BPEであり、SentencePiece風の文字列 `<0xNN>` がそのまま格納されているわけではない。以下のbyte-fallbackは「全pieceが単独UTF-8 decode不可」の操作的分類。2〜3バイトの共有接頭辞も含み、純粋な1バイトfallbackとは異なる。strict_all_single_bytesを別集計する。dedicatedは全入力が1個のvalid UTF-8 token、composed-from-dedicated-partsは複数tokenが全て単独decode可能、mixedはvalid/invalidが混在。decoded pieceのreprと生バイトhexを併記して置換文字で情報を失わない。専用という語は予約special tokenという意味ではない。
NFC正規化せず全例をencode_ordinaryで独立測定。NFC比較は後掲。文脈・前後空白でBPE境界は変化するため単独コストは文中の保証ではない。
## 主要結果の読み方
母数はUnicode Emoji 17.0 fully-qualifiedの3944件。

|encoding|1 token|2 tokens|3 tokens以上|全piece単独UTF-8不可|全pieceが1 byte|
|---|---:|---:|---:|---:|---:|
|o200k_base|23|846|3075|1805|15|
|cl100k_base|0|186|3758|2764|26|
|p50k_base|0|167|3777|2764|33|
|r50k_base|0|167|3777|2764|33|

o200k対cl100k（同じ3944列）: {"o_cheaper": 3281, "equal": 660, "o_more_expensive": 3}。全語彙で絵文字とZWJを一緒に含むvalid UTF-8 tokenは4 encodingとも0。公式列に一致する複数コードポイントtokenはo200kの❤️だけ（1件）、他は0。したがって「複雑なZWJを丸ごと1 tokenで保持」は今回の全走査では見つからなかった。

o200kの1 token公式絵文字23件:
```jsonl
```
具体例（o200k / cl100k）: 😀は1 / 2、❤️は1 / 3、👍は1 / 3、✅は1 / 2。👍🏽は3 / 6、家族👨‍👩‍👧‍👦は11 / 18、虹旗🏳️‍🌈は6 / 9、日本旗🇯🇵は4 / 6、keycap 1️⃣は2 / 5。→は両方1、☃は両方2。同じBMP内でもコストは異なる。→をright arrowに、✅をcheck mark buttonに展開する場合の節約候補はある一方、❤対loveはo200kで1対1なので節約なし。
最大コスト公式列:
```jsonl
```
以下の集計JSONで欠けたキーは0（Counterの省略）。語彙contains_emoji_baseはemoji-test由来の独自定義であり、地域指標はcontains_component側。公式emoji完全一致数とは同義でない。

## 公式絵文字集計
```json
  "o200k_base": {
    "1": 23,
    "dedicated": 23,
    "2": 846,
    "byte-fallback": 1805,
    "3+": 3075,
    "composed-from-dedicated-parts": 40,
    "mixed": 2076,
    "strict_all_single_bytes": 15
  },
  "cl100k_base": {
    "2": 186,
    "byte-fallback": 2764,
    "3+": 3758,
    "mixed": 1174,
    "strict_all_single_bytes": 26,
    "composed-from-dedicated-parts": 6
  },
  "p50k_base": {
    "2": 167,
    "byte-fallback": 2764,
    "3+": 3777,
    "mixed": 1174,
    "strict_all_single_bytes": 33,
    "composed-from-dedicated-parts": 6
  },
  "r50k_base": {
    "2": 167,
    "byte-fallback": 2764,
    "3+": 3777,
    "mixed": 1174,
    "strict_all_single_bytes": 33,
    "composed-from-dedicated-parts": 6
  }
}
```
## 全語彙走査結果
```json
  "o200k_base": {
    "total_mergeable": 199998,
    "valid_utf8_entries": 198436,
    "contains_punctuation": 21222,
    "contains_symbol_category": 2417,
    "invalid_utf8_entries": 1562,
    "contains_component": 58,
    "contains_emoji_base": 74,
    "exact_official_surface": 41,
    "exact_fully_qualified": 23,
    "emoji_multi_codepoint": 1
  },
  "cl100k_base": {
    "total_mergeable": 100256,
    "valid_utf8_entries": 99483,
    "contains_punctuation": 23162,
    "contains_symbol_category": 2655,
    "invalid_utf8_entries": 773,
    "contains_emoji_base": 21,
    "exact_official_surface": 6,
    "contains_component": 1
  },
  "p50k_base": {
    "total_mergeable": 50280,
    "valid_utf8_entries": 49936,
    "contains_punctuation": 762,
    "contains_symbol_category": 275,
    "invalid_utf8_entries": 344,
    "contains_emoji_base": 12,
    "exact_official_surface": 6,
    "contains_component": 1
  },
  "r50k_base": {
    "total_mergeable": 50256,
    "valid_utf8_entries": 49912,
    "contains_punctuation": 762,
    "contains_symbol_category": 275,
    "invalid_utf8_entries": 344,
    "contains_emoji_base": 12,
    "exact_official_surface": 6,
    "contains_component": 1
  }
}
```

o200kがcl100kより高価だった公式3例（改善一方向ではない）:
```json
[
  {
    "surface": "🏴󠁧󠁢󠁥󠁮󠁧󠁿",
    "o200k": 26,
    "cl100k": 21
  },
  {
    "surface": "🏴󠁧󠁢󠁳󠁣󠁴󠁿",
    "o200k": 26,
    "cl100k": 21
  },
  {
    "surface": "🏴󠁧󠁢󠁷󠁬󠁳󠁿",
    "o200k": 26,
    "cl100k": 21
  }
]
```
## 安価候補
cheap-symbols.jsonlは、全公式行、追加例、Unicode全域のSo/Sk/Sm/Scおよび非ASCII句読点、語彙内の文字以外を主体とする記号列（最大64コードポイント）を測定し、1 token／英語glossより安い／o200kがcl100kより安い、のいずれかを満たしたもの。意味同値や実用圧縮成功を保証しない。Unicode正式名称は通常の言い換えより長い場合があり、名称との比較だけで節約率を主張しない。英語glossの出典は公式emoji名、追加例の人手対訳、その他はUnicode名。
encoding別収録数: {"o200k_base": 13491, "cl100k_base": 9797, "p50k_base": 8577, "r50k_base": 8577}
## 再現用小例
```python
import tiktoken
e = tiktoken.get_encoding("o200k_base")
s = "👨‍👩‍👧‍👦"
ids = e.encode_ordinary(s)
print(ids)
print([e.decode_single_token_bytes(i) for i in ids])
```
以下は全追加例の実測。token_ids・piece repr・piece bytes・分類・英語gloss比較を含む。
```jsonl
```
## NFC・文脈の比較
```jsonl
```
## 所見と公開参考
- 一律「BMPなら1 token」「見た目1文字なら安い」は成立しない。異体字、ZWJ、肌色、国旗、tag列は共有バイト接頭辞や個別文字の組合せとなる。後掲語彙一覧でZWJと絵文字を一緒に含むtokenの有無を全走査で確認できる。
- 記号を語句の略記として使うことには節約候補があるが、多義性・解釈・復元誤りを検証する別評価が必要。モデルの内部表現・知能・圧縮悪用の成功までは測っていない。愛を表す❤とloveのように、すでに英単語1 tokenで節約しない例もある。家族ZWJをfamilyへ置換する逆方向の方が安い例に注意。
- ルックアップ表（encoding、文字列、正規化条件、token数、ids、gloss、バージョン、元データhash）を推奨。未知列は実encode。近似規則は未収録データの暫定説明に限定。各コードポイントのコスト加算は既存mergeや共有バイトのため正確でない。全Unicode列は無限に組み合わせられるので全列挙ではなく公式列＋観測列＋任意入力の実encodeのハイブリッドがよい。
- TalkCompressの既知背景（今回再測定せず）: estimate_tokensはNFC後に推定、emojiコストはコードポイント加算とbase＋VS16の一部lookup、結合文字判定はU+0300–036F。今回のNFC比較は入口を合わせる必要性を示すが、TalkCompress自体の推定誤差・コーパス出現数は本担当では再計測していない。
- 公開実装tiktoken: https://github.com/openai/tiktoken （README実読: https://raw.githubusercontent.com/openai/tiktoken/main/README.md ）。byte BPEの実装・生バイト取得APIが参照元。encoding定義: https://github.com/openai/tiktoken/blob/main/tiktoken_ext/openai_public.py 。今回はインストール済み公開パッケージで計測。
- Unicode emoji-testは表示・キーボード用のqualified/unqualified列を網羅し、特殊な予約tokenやモデル理解を定義しない。仕様: https://www.unicode.org/reports/tr51/ 。
- 他社モデル・モデルへの復元プロンプト実験、私的データ、外部コーパスの再走査は未実施。API課金もなし。AI可読性: 未測定。

## 付録A: emoji/componentを含むvalid UTF-8語彙
全走査で該当した項目を列挙。tokenの存在だけでは単独encodeで必ずそのtokenが選ばれる保証はなく、安価候補JSONLではencodeを実施している。

### o200k_base
```jsonl
```

### cl100k_base
```jsonl
```

### p50k_base
```jsonl
```

### r50k_base
```jsonl
```

## 付録B: 公式全行の実測
各encodingについて全statusを列挙。fully-qualified以外も含むので主要集計より件数が多い。

### o200k_base
```jsonl
```

### cl100k_base
```jsonl
```

### p50k_base
```jsonl
```

### r50k_base
```jsonl
```
