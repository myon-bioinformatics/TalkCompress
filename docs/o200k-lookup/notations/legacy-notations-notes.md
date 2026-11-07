結論：古い記法も見た目ではなく実際に送る文字列でコストが変わる。携帯PUAは標準絵文字とは別文字で、shortcodeや顔文字も文字列としてBPE分割される。フォントスロットとそのASCII文字は同じ意味ではない。encoding別の表＋実encodeを推奨する。意味保持・復元・圧縮品質は未検証。AI可読性: 未測定。

# 古い携帯絵文字・記法のo200k測定
取得・実施日: 2026-11-07 JST。Python 3.14.8 (main, Oct  3 2026, 01:04:31) [Clang 22.1.3 ]。tiktoken 0.14.0。Unicode DB 16.0.0。encoding o200k_base、encode_ordinary、単独文字列測定。NFC強制なし。NFCで表面が変わる行にはnfc_surface/nfc_token_count/nfc_changes_token_idsを記録。
## 方法と範囲
- piecesは単独UTF-8 decode可能なら文字列、不可能ならhex:接頭辞。生バイトはpiece_bytes_hexで必ず保持。dedicatedは全体1 tokenでUTF-8有効、composed-from-dedicated-partsは全piece有効、byte-fallbackは全piece単独復号不能、mixedはその混在。byte-fallbackには複数バイト接頭辞も含む。all_single_byte_piecesは別指標。
- 携帯: EmojiSources 17.0全722行の非空carrier欄を記録。SJISはメタデータで、UTF-8入力に直接混ぜない。PUAはemoji-dataのdocomo/au/softbank欄とUnicode対応列をFE0F除去一致で結合。SJISからPUAへの規則を推測しない。その後指定PUA範囲の未収録点も走査。範囲には未割当候補も含むため、全点が実在絵文字という意味ではない。対応不明・複数対応は明示。record_kindでSJIS対応由来と範囲走査を分離。
- EmojiSources非空carrier欄数: {'docomo': 244, 'kddi': 633, 'softbank': 469}。PUA未結合のcarrier欄数: 3。PUA不明行はsurface:nullでtoken欄なし。
- 指定WINGDING.TXTとWEBDINGS.TXTはいずれもHTTP 404。代わりにBSD-2-Clauseのdingbat-to-unicode 1.0.2公開データを使用し、両フォントの0x21–0xFF全223スロットを列挙。対応なしはnullで未測定。Microsoftフォント本体は取得・再配布していない。対応先Unicodeをsurfaceとして測定し、元のASCIIスロット文字は測っていない。これはUnicode公式の完全対応表と主張しない。
- BSD表の未対応スロット: {'wingdings': [255], 'webdings': [127]}（10進）。
- GitHub: gemoji全aliases。Slack: emoji-data全short_namesと形式例1件。Slackの現在の公式カスタム名一覧ではなくSlack-style参照表。どちらもコロンを含む文字列。
- Discord: 公開再利用可能な全一覧を確認できなかった。共通名7件と文書化された<:NAME:ID>形式の文字通りのプレースホルダー1件のみ。実在・架空IDを作らず、Discordでそのまま有効な送信文字列とは主張しない。標準emojiの実際のmessage contentはUnicodeであり、shortcode入力補助と区別する。
- CLDR: common/annotations/en.xmlとja.xmlのtype=tts全件。キーワードとannotationsDerivedは今回対象外。cpはCLDRのFE0F除去済み値をそのまま比較し、推測補完しない。mainは可変snapshotで、取得データSHA-256を下記に保持。
- その他: 一般的短い記法を独立に編集した標本。商用一覧・Wikipedia本文の転用なし。HTML実体参照はPython標準html.unescapeで対応先を取得。other-notationからemoji-test 17.0の全statusにある表面は除外。他familyの絵文字はcarrier・font対応の対照として扱う。
## family別集計
```json
{
  "ascii-emoticon": {
    "rows": 86,
    "measured": 86,
    "unmeasured": 0,
    "distribution": {
      "1": 26,
      "2": 57,
      "3+": 3
    },
    "classes": {
      "dedicated": 26,
      "composed-from-dedicated-parts": 60
    }
  },
  "carrier-emoji": {
    "rows": 2267,
    "measured": 2264,
    "unmeasured": 3,
    "distribution": {
      "1": 0,
      "2": 111,
      "3+": 2153
    },
    "classes": {
      "byte-fallback": 2264
    }
  },
  "cldr-annotation": {
    "rows": 3950,
    "measured": 3950,
    "unmeasured": 0,
    "distribution": {
      "1": 265,
      "2": 1017,
      "3+": 2668
    },
    "classes": {
      "composed-from-dedicated-parts": 3283,
      "dedicated": 265,
      "mixed": 381,
      "byte-fallback": 21
    }
  },
  "discord-shortcode": {
    "rows": 8,
    "measured": 8,
    "unmeasured": 0,
    "distribution": {
      "1": 0,
      "2": 0,
      "3+": 8
    },
    "classes": {
      "composed-from-dedicated-parts": 8
    }
  },
  "github-shortcode": {
    "rows": 1913,
    "measured": 1913,
    "unmeasured": 0,
    "distribution": {
      "1": 0,
      "2": 12,
      "3+": 1901
    },
    "classes": {
      "composed-from-dedicated-parts": 1913
    }
  },
  "html-entity": {
    "rows": 40,
    "measured": 40,
    "unmeasured": 0,
    "distribution": {
      "1": 0,
      "2": 3,
      "3+": 37
    },
    "classes": {
      "composed-from-dedicated-parts": 40
    }
  },
  "kaomoji": {
    "rows": 82,
    "measured": 82,
    "unmeasured": 0,
    "distribution": {
      "1": 3,
      "2": 2,
      "3+": 77
    },
    "classes": {
      "composed-from-dedicated-parts": 53,
      "dedicated": 3,
      "mixed": 25,
      "byte-fallback": 1
    }
  },
  "other-notation": {
    "rows": 59,
    "measured": 59,
    "unmeasured": 0,
    "distribution": {
      "1": 11,
      "2": 33,
      "3+": 15
    },
    "classes": {
      "dedicated": 11,
      "byte-fallback": 45,
      "composed-from-dedicated-parts": 3
    }
  },
  "slack-shortcode": {
    "rows": 1981,
    "measured": 1981,
    "unmeasured": 0,
    "distribution": {
      "1": 0,
      "2": 12,
      "3+": 1969
    },
    "classes": {
      "composed-from-dedicated-parts": 1981
    }
  },
  "webdings": {
    "rows": 223,
    "measured": 222,
    "unmeasured": 1,
    "distribution": {
      "1": 1,
      "2": 114,
      "3+": 107
    },
    "classes": {
      "byte-fallback": 221,
      "dedicated": 1
    }
  },
  "wingdings": {
    "rows": 223,
    "measured": 222,
    "unmeasured": 1,
    "distribution": {
      "1": 8,
      "2": 117,
      "3+": 97
    },
    "classes": {
      "byte-fallback": 214,
      "dedicated": 8
    }
  }
}
```
## 同じ対応先とのコスト比較
notation_cheaperは表面記法の方が安い。意味同値の復元実験ではない。
```json
{
  "ascii-emoticon": {
    "paired": 0,
    "notation_cheaper": 0,
    "equal": 0,
    "notation_more_expensive": 0
  },
  "carrier-emoji": {
    "paired": 1345,
    "notation_cheaper": 42,
    "equal": 158,
    "notation_more_expensive": 1145
  },
  "cldr-annotation": {
    "paired": 3950,
    "notation_cheaper": 749,
    "equal": 914,
    "notation_more_expensive": 2287
  },
  "discord-shortcode": {
    "paired": 7,
    "notation_cheaper": 0,
    "equal": 0,
    "notation_more_expensive": 7
  },
  "github-shortcode": {
    "paired": 1913,
    "notation_cheaper": 162,
    "equal": 291,
    "notation_more_expensive": 1460
  },
  "html-entity": {
    "paired": 40,
    "notation_cheaper": 0,
    "equal": 0,
    "notation_more_expensive": 40
  },
  "kaomoji": {
    "paired": 0,
    "notation_cheaper": 0,
    "equal": 0,
    "notation_more_expensive": 0
  },
  "other-notation": {
    "paired": 0,
    "notation_cheaper": 0,
    "equal": 0,
    "notation_more_expensive": 0
  },
  "slack-shortcode": {
    "paired": 1980,
    "notation_cheaper": 132,
    "equal": 262,
    "notation_more_expensive": 1586
  },
  "webdings": {
    "paired": 222,
    "notation_cheaper": 0,
    "equal": 222,
    "notation_more_expensive": 0
  },
  "wingdings": {
    "paired": 222,
    "notation_cheaper": 0,
    "equal": 222,
    "notation_more_expensive": 0
  }
}
```
## 代表例
### carrier-emoji
```jsonl
{"surface": "", "codepoints": ["U+E6E0"], "token_count": 3, "class": "byte-fallback", "carrier": "docomo", "sjis_hex": "F985", "unicode_mapped_surface": "#⃣", "unicode_mapped_token_count": 2, "gloss_en": "HASH KEY", "gloss_token_count": 2}
{"surface": "", "codepoints": ["U+EB84"], "token_count": 3, "class": "byte-fallback", "carrier": "kddi", "sjis_hex": "F489", "unicode_mapped_surface": "#⃣", "unicode_mapped_token_count": 2, "gloss_en": "HASH KEY", "gloss_token_count": 2}
{"surface": "", "codepoints": ["U+E210"], "token_count": 3, "class": "byte-fallback", "carrier": "softbank", "sjis_hex": "F7B0", "unicode_mapped_surface": "#⃣", "unicode_mapped_token_count": 2, "gloss_en": "HASH KEY", "gloss_token_count": 2}
```
### wingdings
```jsonl
{"surface": "👍", "codepoints": ["U+1F44D"], "token_count": 1, "class": "dedicated", "font_slot_hex": "43", "unicode_mapped_surface": "👍", "unicode_mapped_token_count": 1, "gloss_en": "THUMBS UP SIGN", "gloss_token_count": 5}
{"surface": "☺", "codepoints": ["U+263A"], "token_count": 1, "class": "dedicated", "font_slot_hex": "4A", "unicode_mapped_surface": "☺", "unicode_mapped_token_count": 1, "gloss_en": "WHITE SMILING FACE", "gloss_token_count": 4}
{"surface": "🖉", "codepoints": ["U+1F589"], "token_count": 3, "class": "byte-fallback", "font_slot_hex": "21", "unicode_mapped_surface": "🖉", "unicode_mapped_token_count": 3, "gloss_en": "LOWER LEFT PENCIL", "gloss_token_count": 5}
```
### webdings
```jsonl
{"surface": "✔", "codepoints": ["U+2714"], "token_count": 1, "class": "dedicated", "font_slot_hex": "61", "unicode_mapped_surface": "✔", "unicode_mapped_token_count": 1, "gloss_en": "HEAVY CHECK MARK", "gloss_token_count": 5}
{"surface": "🏆", "codepoints": ["U+1F3C6"], "token_count": 2, "class": "byte-fallback", "font_slot_hex": "25", "unicode_mapped_surface": "🏆", "unicode_mapped_token_count": 2, "gloss_en": "TROPHY", "gloss_token_count": 3}
{"surface": "🕷", "codepoints": ["U+1F577"], "token_count": 3, "class": "byte-fallback", "font_slot_hex": "21", "unicode_mapped_surface": "🕷", "unicode_mapped_token_count": 3, "gloss_en": "SPIDER", "gloss_token_count": 2}
```
### github-shortcode
```jsonl
{"surface": ":smile:", "codepoints": ["U+003A", "U+0073", "U+006D", "U+0069", "U+006C", "U+0065", "U+003A"], "token_count": 4, "class": "composed-from-dedicated-parts", "unicode_mapped_surface": "😄", "unicode_mapped_token_count": 2, "gloss_en": "grinning face with smiling eyes", "gloss_token_count": 6}
{"surface": ":heart:", "codepoints": ["U+003A", "U+0068", "U+0065", "U+0061", "U+0072", "U+0074", "U+003A"], "token_count": 3, "class": "composed-from-dedicated-parts", "unicode_mapped_surface": "❤️", "unicode_mapped_token_count": 1, "gloss_en": "red heart", "gloss_token_count": 2}
{"surface": ":thumbsup:", "codepoints": ["U+003A", "U+0074", "U+0068", "U+0075", "U+006D", "U+0062", "U+0073", "U+0075", "U+0070", "U+003A"], "token_count": 4, "class": "composed-from-dedicated-parts", "unicode_mapped_surface": "👍", "unicode_mapped_token_count": 1, "gloss_en": "thumbs up", "gloss_token_count": 3}
{"surface": ":family:", "codepoints": ["U+003A", "U+0066", "U+0061", "U+006D", "U+0069", "U+006C", "U+0079", "U+003A"], "token_count": 3, "class": "composed-from-dedicated-parts", "unicode_mapped_surface": "👪", "unicode_mapped_token_count": 2, "gloss_en": "family", "gloss_token_count": 1}
```
### slack-shortcode
```jsonl
{"surface": ":smile:", "codepoints": ["U+003A", "U+0073", "U+006D", "U+0069", "U+006C", "U+0065", "U+003A"], "token_count": 4, "class": "composed-from-dedicated-parts", "unicode_mapped_surface": "😄", "unicode_mapped_token_count": 2, "gloss_en": "SMILING FACE WITH OPEN MOUTH AND SMILING EYES", "gloss_token_count": 12}
{"surface": ":heart:", "codepoints": ["U+003A", "U+0068", "U+0065", "U+0061", "U+0072", "U+0074", "U+003A"], "token_count": 3, "class": "composed-from-dedicated-parts", "unicode_mapped_surface": "❤️", "unicode_mapped_token_count": 1, "gloss_en": "HEAVY BLACK HEART", "gloss_token_count": 5}
{"surface": ":thumbsup:", "codepoints": ["U+003A", "U+0074", "U+0068", "U+0075", "U+006D", "U+0062", "U+0073", "U+0075", "U+0070", "U+003A"], "token_count": 4, "class": "composed-from-dedicated-parts", "unicode_mapped_surface": "👍", "unicode_mapped_token_count": 1, "gloss_en": "THUMBS UP SIGN", "gloss_token_count": 5}
{"surface": ":custom_name:", "codepoints": ["U+003A", "U+0063", "U+0075", "U+0073", "U+0074", "U+006F", "U+006D", "U+005F", "U+006E", "U+0061", "U+006D", "U+0065", "U+003A"], "token_count": 4, "class": "composed-from-dedicated-parts"}
```
### discord-shortcode
```jsonl
{"surface": ":smile:", "codepoints": ["U+003A", "U+0073", "U+006D", "U+0069", "U+006C", "U+0065", "U+003A"], "token_count": 4, "class": "composed-from-dedicated-parts", "unicode_mapped_surface": "😄", "unicode_mapped_token_count": 2}
{"surface": ":heart:", "codepoints": ["U+003A", "U+0068", "U+0065", "U+0061", "U+0072", "U+0074", "U+003A"], "token_count": 3, "class": "composed-from-dedicated-parts", "unicode_mapped_surface": "❤️", "unicode_mapped_token_count": 1}
{"surface": "<:NAME:ID>", "codepoints": ["U+003C", "U+003A", "U+004E", "U+0041", "U+004D", "U+0045", "U+003A", "U+0049", "U+0044", "U+003E"], "token_count": 6, "class": "composed-from-dedicated-parts"}
```
### cldr-annotation
```jsonl
{"surface": "grinning face", "codepoints": ["U+0067", "U+0072", "U+0069", "U+006E", "U+006E", "U+0069", "U+006E", "U+0067", "U+0020", "U+0066", "U+0061", "U+0063", "U+0065"], "token_count": 3, "class": "composed-from-dedicated-parts", "unicode_mapped_surface": "😀", "unicode_mapped_token_count": 1}
{"surface": "smiling face with smiling eyes", "codepoints": ["U+0073", "U+006D", "U+0069", "U+006C", "U+0069", "U+006E", "U+0067", "U+0020", "U+0066", "U+0061", "U+0063", "U+0065", "U+0020", "U+0077", "U+0069", "U+0074", "U+0068", "U+0020", "U+0073", "U+006D", "U+0069", "U+006C", "U+0069", "U+006E", "U+0067", "U+0020", "U+0065", "U+0079", "U+0065", "U+0073"], "token_count": 6, "class": "composed-from-dedicated-parts", "unicode_mapped_surface": "😊", "unicode_mapped_token_count": 1}
{"surface": "にっこり笑う", "codepoints": ["U+306B", "U+3063", "U+3053", "U+308A", "U+7B11", "U+3046"], "token_count": 6, "class": "composed-from-dedicated-parts", "unicode_mapped_surface": "😀", "unicode_mapped_token_count": 1}
{"surface": "笑顔", "codepoints": ["U+7B11", "U+9854"], "token_count": 2, "class": "composed-from-dedicated-parts", "unicode_mapped_surface": "😄", "unicode_mapped_token_count": 2}
```
### ascii-emoticon
```jsonl
{"surface": ":)", "codepoints": ["U+003A", "U+0029"], "token_count": 1, "class": "dedicated"}
{"surface": "<3", "codepoints": ["U+003C", "U+0033"], "token_count": 2, "class": "composed-from-dedicated-parts"}
{"surface": ":-)", "codepoints": ["U+003A", "U+002D", "U+0029"], "token_count": 2, "class": "composed-from-dedicated-parts"}
{"surface": ":S", "codepoints": ["U+003A", "U+0053"], "token_count": 1, "class": "dedicated"}
```
### kaomoji
```jsonl
{"surface": "orz", "codepoints": ["U+006F", "U+0072", "U+007A"], "token_count": 1, "class": "dedicated"}
{"surface": "(^_^)", "codepoints": ["U+0028", "U+005E", "U+005F", "U+005E", "U+0029"], "token_count": 3, "class": "composed-from-dedicated-parts"}
{"surface": "(´・ω・`)", "codepoints": ["U+0028", "U+00B4", "U+30FB", "U+03C9", "U+30FB", "U+0060", "U+0029"], "token_count": 5, "class": "composed-from-dedicated-parts"}
{"surface": "¯\\_(ツ)_/¯", "codepoints": ["U+00AF", "U+005C", "U+005F", "U+0028", "U+30C4", "U+0029", "U+005F", "U+002F", "U+00AF"], "token_count": 7, "class": "composed-from-dedicated-parts"}
```
### html-entity
```jsonl
{"surface": "&hearts;", "codepoints": ["U+0026", "U+0068", "U+0065", "U+0061", "U+0072", "U+0074", "U+0073", "U+003B"], "token_count": 4, "class": "composed-from-dedicated-parts", "unicode_mapped_surface": "♥", "unicode_mapped_token_count": 1}
{"surface": "&#x2764;", "codepoints": ["U+0026", "U+0023", "U+0078", "U+0032", "U+0037", "U+0036", "U+0034", "U+003B"], "token_count": 5, "class": "composed-from-dedicated-parts", "unicode_mapped_surface": "❤", "unicode_mapped_token_count": 1}
{"surface": "&copy;", "codepoints": ["U+0026", "U+0063", "U+006F", "U+0070", "U+0079", "U+003B"], "token_count": 3, "class": "composed-from-dedicated-parts", "unicode_mapped_surface": "©", "unicode_mapped_token_count": 1}
{"surface": "&rarr;", "codepoints": ["U+0026", "U+0072", "U+0061", "U+0072", "U+0072", "U+003B"], "token_count": 3, "class": "composed-from-dedicated-parts", "unicode_mapped_surface": "→", "unicode_mapped_token_count": 1}
```
### other-notation
```jsonl
{"surface": "①", "codepoints": ["U+2460"], "token_count": 1, "class": "dedicated", "gloss_en": "CIRCLED DIGIT ONE", "gloss_token_count": 6}
{"surface": "㈱", "codepoints": ["U+3231"], "token_count": 2, "class": "byte-fallback", "gloss_en": "PARENTHESIZED IDEOGRAPH STOCK", "gloss_token_count": 8}
{"surface": "♪", "codepoints": ["U+266A"], "token_count": 1, "class": "dedicated", "gloss_en": "EIGHTH NOTE", "gloss_token_count": 4}
{"surface": "[smile]", "codepoints": ["U+005B", "U+0073", "U+006D", "U+0069", "U+006C", "U+0065", "U+005D"], "token_count": 4, "class": "composed-from-dedicated-parts", "gloss_en": null}
```

### 対応先より記法が安い実測例
```jsonl
{"family": "github-shortcode", "surface": ":wales:", "codepoints": ["U+003A", "U+0077", "U+0061", "U+006C", "U+0065", "U+0073", "U+003A"], "token_count": 3, "unicode_mapped_surface": "🏴󠁧󠁢󠁷󠁬󠁳󠁿", "unicode_mapped_token_count": 26}
{"family": "slack-shortcode", "surface": ":flag-england:", "codepoints": ["U+003A", "U+0066", "U+006C", "U+0061", "U+0067", "U+002D", "U+0065", "U+006E", "U+0067", "U+006C", "U+0061", "U+006E", "U+0064", "U+003A"], "token_count": 5, "unicode_mapped_surface": "🏴󠁧󠁢󠁥󠁮󠁧󠁿", "unicode_mapped_token_count": 26}
{"family": "cldr-annotation", "surface": "people holding hands", "codepoints": ["U+0070", "U+0065", "U+006F", "U+0070", "U+006C", "U+0065", "U+0020", "U+0068", "U+006F", "U+006C", "U+0064", "U+0069", "U+006E", "U+0067", "U+0020", "U+0068", "U+0061", "U+006E", "U+0064", "U+0073"], "token_count": 3, "unicode_mapped_surface": "🧑‍🤝‍🧑", "unicode_mapped_token_count": 10}
{"family": "carrier-emoji", "surface": "", "codepoints": ["U+E545"], "carrier": "kddi", "token_count": 2, "unicode_mapped_surface": "⏫", "unicode_mapped_token_count": 3}
```
記法が短くても、元の細かい意味・表示・肌色・字体を復元できる保証はない。

## トークナイザ寄りの所見
GitHub shortcodeは1913件中1460件で対応先より高価、162件で安価、291件は同数。Slack-styleは対応先あり1980件中1586件で高価、132件で安価、262件は同数。CLDR en/jaのtts合計3950件は749件で名前が安価、914件同数、2287件で名前が高価。HTML実体参照40例は全例が展開後より高価。PUA測定2264件は全件byte-fallback分類で1 tokenは0件。NFCで表面が変化した測定行は0件。
対応絵文字が1 tokenならshortcodeをそのまま代入するより有利になり得るが、名前の方が安い複雑列もある。PUAを特別な1文字辞書として利用できるとは考えない。顔文字の複雑な装飾・結合列は多くのtokenへ分割される一方、orzなど短いASCII列は安いことがある。Wingdingsはフォント外では元の英字スロットしか見えず、ここで測った対応Unicodeの意味を引き継ぐものではない。CLDR英語名とshortcodeの意味は注釈・対応表としての関係で、モデルの復元能力を示さない。
意味保持・復元・圧縮品質は未検証。AI可読性: 未測定。

## 出典・snapshot
- https://raw.githubusercontent.com/github/gemoji/master/db/emoji.json
  取得日2026-11-07 JST、bytes=413367、SHA-256=b174ae2aeb321b52f64adb9ff412f966a7f338839d780784dd15dcad702c2dd6
- https://raw.githubusercontent.com/iamcal/emoji-data/master/emoji.json
  取得日2026-11-07 JST、bytes=1359023、SHA-256=8736d721991e48c41c57acc46b65e5d32258a45e4bcdebcc6012f420f81e775d
- https://www.unicode.org/Public/17.0.0/ucd/EmojiSources.txt
  取得日2026-11-07 JST、bytes=13643、SHA-256=db1b517734304781702789d586801275e82bd91ff45be7d34e2dc250cc10e34d
- https://registry.npmjs.org/dingbat-to-unicode/-/dingbat-to-unicode-1.0.2.tgz
  取得日2026-11-07 JST、bytes=8230、SHA-256=3ff52fb8c0586a748aa11cbbac2f16524cf9971767f06077ff344729a69321c1
- https://raw.githubusercontent.com/github/gemoji/master/LICENSE
  取得日2026-11-07 JST、bytes=1056、SHA-256=7ea1d1fd0602e6623b9a65e791499a0ea5a2f5f60f91bfad78cbaeee19da26e6
- https://raw.githubusercontent.com/iamcal/emoji-data/master/LICENSE
  取得日2026-11-07 JST、bytes=1080、SHA-256=ee9953a79bf2132b59b1342b217f1c377b3d03d9e7713006f6c3b89eb159f1db
- https://www.unicode.org/license.txt
  取得日2026-11-07 JST、bytes=1995、SHA-256=e7a93b009565cfce55919a381437ac4db883e9da2126fa28b91d12732bc53d96
- https://raw.githubusercontent.com/unicode-org/cldr/main/LICENSE
  取得日2026-11-07 JST、bytes=3193、SHA-256=65eb33419e22a297550a811b5b535f5e532f9a7e0114b516c0ea18afd53c3804
- https://raw.githubusercontent.com/unicode-org/cldr/main/common/annotations/en.xml
  取得日2026-11-07 JST、bytes=296588、SHA-256=14d0e9bb5003c085250df4ac7bd7ba1e26d92e74174d7a3a2f42dc16e07fb155
- https://raw.githubusercontent.com/unicode-org/cldr/main/common/annotations/ja.xml
  取得日2026-11-07 JST、bytes=316940、SHA-256=74b6889ca7ad882b547e388a1e36a576ab4bdf00d12f59381eea286be44b15d3
- https://www.unicode.org/Public/17.0.0/emoji/emoji-test.txt
  取得日2026-11-07 JST、bytes=669326、SHA-256=1d8a944f88d7952f7ef7c5167fef3c67995bcae24543949710231b03a201acda
- Discord書式確認: https://docs.discord.com/developers/reference#message-formatting 。説明の事実・形式のみ独立に記述し、本文・データセットは再配布しない。
- HTML形式: https://html.spec.whatwg.org/multipage/named-characters.html 。短い標準構文を独立に抽出した例。
- 独立編集の短い記法標本はCC0-1.0: https://creativecommons.org/publicdomain/zero/1.0/ 。他出典のライセンスを置き換えるものではない。
- Unicode EmojiSources/CLDR: Unicode-3.0。gemojiおよびemoji-data: MIT。dingbat-to-unicode 1.0.2: BSD-2-Clause。以下に再利用条件を保持。

## 再利用ライセンス本文

### https://raw.githubusercontent.com/github/gemoji/master/LICENSE
```text
Copyright (c) 2019 GitHub, Inc.

Permission is hereby granted, free of charge, to any person
obtaining a copy of this software and associated documentation
files (the "Software"), to deal in the Software without
restriction, including without limitation the rights to use,
copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the
Software is furnished to do so, subject to the following
conditions:

The above copyright notice and this permission notice shall be
included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES
OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT
HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR
OTHER DEALINGS IN THE SOFTWARE.

```

### https://raw.githubusercontent.com/iamcal/emoji-data/master/LICENSE
```text
The MIT License (MIT)

Copyright (c) 2013 Cal Henderson

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

```

### https://www.unicode.org/license.txt
```text
UNICODE LICENSE V3

COPYRIGHT AND PERMISSION NOTICE

Copyright © 1991-2026 Unicode, Inc.

NOTICE TO USER: Carefully read the following legal agreement. BY
DOWNLOADING, INSTALLING, COPYING OR OTHERWISE USING DATA FILES, AND/OR
SOFTWARE, YOU UNEQUIVOCALLY ACCEPT, AND AGREE TO BE BOUND BY, ALL OF THE
TERMS AND CONDITIONS OF THIS AGREEMENT. IF YOU DO NOT AGREE, DO NOT
DOWNLOAD, INSTALL, COPY, DISTRIBUTE OR USE THE DATA FILES OR SOFTWARE.

Permission is hereby granted, free of charge, to any person obtaining a
copy of data files and any associated documentation (the "Data Files") or
software and any associated documentation (the "Software") to deal in the
Data Files or Software without restriction, including without limitation
the rights to use, copy, modify, merge, publish, distribute, and/or sell
copies of the Data Files or Software, and to permit persons to whom the
Data Files or Software are furnished to do so, provided that either (a)
this copyright and permission notice appear with all copies of the Data
Files or Software, or (b) this copyright and permission notice appear in
associated Documentation.

THE DATA FILES AND SOFTWARE ARE PROVIDED "AS IS", WITHOUT WARRANTY OF ANY
KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT OF
THIRD PARTY RIGHTS.

IN NO EVENT SHALL THE COPYRIGHT HOLDER OR HOLDERS INCLUDED IN THIS NOTICE
BE LIABLE FOR ANY CLAIM, OR ANY SPECIAL INDIRECT OR CONSEQUENTIAL DAMAGES,
OR ANY DAMAGES WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS,
WHETHER IN AN ACTION OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS ACTION,
ARISING OUT OF OR IN CONNECTION WITH THE USE OR PERFORMANCE OF THE DATA
FILES OR SOFTWARE.

Except as contained in this notice, the name of a copyright holder shall
not be used in advertising or otherwise to promote the sale, use or other
dealings in these Data Files or Software without prior written
authorization of the copyright holder.

```

### https://raw.githubusercontent.com/unicode-org/cldr/main/LICENSE
```text
COPYRIGHT AND PERMISSION NOTICE

Copyright © 2001–2026 Unicode, Inc.

Unicode Technical Standard #35, Unicode Locale Data Markup Language
(LDML) made available in this repository is protected by copyright, and
permission must be obtained from Unicode, Inc. prior to any
reproduction, modification, or other use not permitted by the Unicode
Terms of Use <https://www.unicode.org/copyright.html>. Specifically, you
may make copies of this publication and may annotate and translate it
solely for personal or internal business purposes and not for public
distribution, provided that any such permitted copies and modifications
fully reproduce all copyright and other legal notices contained in the
original. You may not make copies of or modifications to this
publication for public distribution, or incorporate it in whole or in
part into any product or publication without the express written
permission of Unicode. Notwithstanding the foregoing, you may within
this repository provide comments and propose changes to this standard
and may make copies/forks solely for such purposes provided that you
reproduce this copyright notice and these terms of use in any such
copy/fork.

All other content in this repo is released under UNICODE LICENSE V3

NOTICE TO USER: Carefully read the following legal agreement. BY
DOWNLOADING, INSTALLING, COPYING OR OTHERWISE USING DATA FILES, AND/OR
SOFTWARE, YOU UNEQUIVOCALLY ACCEPT, AND AGREE TO BE BOUND BY, ALL OF THE
TERMS AND CONDITIONS OF THIS AGREEMENT. IF YOU DO NOT AGREE, DO NOT
DOWNLOAD, INSTALL, COPY, DISTRIBUTE OR USE THE DATA FILES OR SOFTWARE.

Permission is hereby granted, free of charge, to any person obtaining a
copy of data files and any associated documentation (the "Data Files") or
software and any associated documentation (the "Software") to deal in the
Data Files or Software without restriction, including without limitation
the rights to use, copy, modify, merge, publish, distribute, and/or sell
copies of the Data Files or Software, and to permit persons to whom the
Data Files or Software are furnished to do so, provided that either (a)
this copyright and permission notice appear with all copies of the Data
Files or Software, or (b) this copyright and permission notice appear in
associated Documentation.

THE DATA FILES AND SOFTWARE ARE PROVIDED "AS IS", WITHOUT WARRANTY OF ANY
KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT OF
THIRD PARTY RIGHTS.

IN NO EVENT SHALL THE COPYRIGHT HOLDER OR HOLDERS INCLUDED IN THIS NOTICE
BE LIABLE FOR ANY CLAIM, OR ANY SPECIAL INDIRECT OR CONSEQUENTIAL DAMAGES,
OR ANY DAMAGES WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS,
WHETHER IN AN ACTION OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS ACTION,
ARISING OUT OF OR IN CONNECTION WITH THE USE OR PERFORMANCE OF THE DATA
FILES OR SOFTWARE.

Except as contained in this notice, the name of a copyright holder shall
not be used in advertising or otherwise to promote the sale, use or other
dealings in these Data Files or Software without prior written
authorization of the copyright holder.

SPDX-License-Identifier: Unicode-3.0

```

### https://registry.npmjs.org/dingbat-to-unicode/-/dingbat-to-unicode-1.0.2.tgz
```text
Copyright (c) 2021, Michael Williamson
All rights reserved.

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:

1. Redistributions of source code must retain the above copyright notice, this
   list of conditions and the following disclaimer.
2. Redistributions in binary form must reproduce the above copyright notice,
   this list of conditions and the following disclaimer in the documentation
   and/or other materials provided with the distribution.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR
ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
(INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
(INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

```

## 制約確認
既存tokenizer成果物・他ボットのファイルを変更せず、新規指定2ファイルだけ作成。禁止対象リポジトリと利用者PCを使用せず、PR・push・コメント・アップロード・モデル復元実験は実施しない。
