# Unicode emoji-test 外のテキスト記法・歴史的文字の追加測定

測定日時: 2026-11-07T17:06:39.021301+09:00 (JST)
TalkCompress HEAD: `3c29092e21a5cf503d71382ef23433c63fbba6e8`
Python 3.14.8 / tiktoken 0.14.0 / o200k_base / UCD 16.0.0
計 64,564 category×exact-text 行、入力文字列として 63,762 種。日本顔文字主表 37,515 種は別ファイル kaomoji-ja-o200k.jsonl を参照し、ここでは既存主表にない分のみ。

AI 可読性: **未測定**。意味保持・復元成功は未測定。名称の短さと実用圧縮の良さは同一ではない。

|カテゴリ|件数|o200k平均|過小/一致/過大|MAE|
|---|---:|---:|---|---:|
|carrier_modern_unicode|722|2.072|23/691/8|0.043|
|carrier_pua_docomo|284|2.982|275/9/0|0.975|
|carrier_pua_google|805|3.932|0/750/55|0.068|
|carrier_pua_kddi|648|2.980|632/16/0|0.978|
|carrier_pua_softbank|488|2.883|422/66/0|0.877|
|carrier_text_fallback|398|4.158|53/316/29|0.269|
|cldr_name_ar|4342|10.179|2991/1065/286|1.359|
|cldr_name_de|4342|7.988|3696/546/100|2.015|
|cldr_name_en|4342|5.668|862/2578/902|0.447|
|cldr_name_es|4342|8.026|2897/1130/315|1.099|
|cldr_name_fr|4341|7.742|3357/852/132|1.269|
|cldr_name_hi|4340|10.229|2897/835/608|1.387|
|cldr_name_ja|4342|9.178|1243/2022/1077|0.599|
|cldr_name_ko|4342|8.453|1451/2773/118|0.422|
|cldr_name_pt|4342|7.488|3456/682/204|1.641|
|cldr_name_ru|4342|8.461|2371/1205/766|1.058|
|cldr_name_th|4342|11.384|365/3961/16|0.093|
|cldr_name_zh|4342|7.382|437/2160/1745|0.528|
|emoticon_ascii|71|3.437|44/19/8|1.254|
|emoticon_mixed|19|5.000|11/8/0|2.053|
|font_original|224|1.125|3/209/12|0.067|
|font_unicode_target|1044|2.386|189/840/15|0.195|
|font_word_pua_alias|224|1.982|0/222/2|0.009|
|formal_signwriting_ascii_sample|1|44.000|0/1/0|0.000|
|gemoji_shortcode|1913|4.611|977/843/93|0.743|
|html_named_reference|2231|4.105|1450/646/135|0.932|
|ipa_equivalent|173|1.884|84/79/10|0.618|
|ja_kaomoji_supplement|3050|15.357|2741/237/72|3.905|
|xsampa_ascii|168|1.399|19/149/0|0.113|

## 分布・安い/高い代表例

### carrier_modern_unicode
- o200k分布: `{"1": 36, "2": 608, "3": 68, "4": 10}`
- delta=estimate−o200k: `{"-1": 23, "0": 691, "1": 8}`
- 安い例 (o200k → bytes 順): `[{"text": "©", "o200k": 1, "estimate": 1, "bytes": 2}, {"text": "®", "o200k": 1, "estimate": 1, "bytes": 2}, {"text": " ", "o200k": 1, "estimate": 0, "bytes": 3}]`
- 高い例 (o200k 降順 → bytes 昇順): `[{"text": "🇨🇳", "o200k": 4, "estimate": 4, "bytes": 8}, {"text": "🇩🇪", "o200k": 4, "estimate": 4, "bytes": 8}, {"text": "🇪🇸", "o200k": 4, "estimate": 4, "bytes": 8}]`

### carrier_pua_docomo
- o200k分布: `{"2": 9, "3": 273, "4": 1, "6": 1}`
- delta=estimate−o200k: `{"-3": 1, "-1": 274, "0": 9}`
- 安い例 (o200k → bytes 順): `[{"text": "", "o200k": 2, "estimate": 2, "bytes": 3}, {"text": "", "o200k": 2, "estimate": 2, "bytes": 3}, {"text": "", "o200k": 2, "estimate": 2, "bytes": 3}]`
- 高い例 (o200k 降順 → bytes 昇順): `[{"text": "", "o200k": 6, "estimate": 3, "bytes": 6}, {"text": "", "o200k": 4, "estimate": 3, "bytes": 6}, {"text": "", "o200k": 3, "estimate": 2, "bytes": 3}]`

### carrier_pua_google
- o200k分布: `{"3": 55, "4": 750}`
- delta=estimate−o200k: `{"0": 750, "1": 55}`
- 安い例 (o200k → bytes 順): `[{"text": "󾆒", "o200k": 3, "estimate": 4, "bytes": 4}, {"text": "󾇌", "o200k": 3, "estimate": 4, "bytes": 4}, {"text": "󾓝", "o200k": 3, "estimate": 4, "bytes": 4}]`
- 高い例 (o200k 降順 → bytes 昇順): `[{"text": "󾀀", "o200k": 4, "estimate": 4, "bytes": 4}, {"text": "󾀁", "o200k": 4, "estimate": 4, "bytes": 4}, {"text": "󾀂", "o200k": 4, "estimate": 4, "bytes": 4}]`

### carrier_pua_kddi
- o200k分布: `{"2": 16, "3": 631, "6": 1}`
- delta=estimate−o200k: `{"-3": 1, "-1": 631, "0": 16}`
- 安い例 (o200k → bytes 順): `[{"text": "", "o200k": 2, "estimate": 2, "bytes": 3}, {"text": "", "o200k": 2, "estimate": 2, "bytes": 3}, {"text": "", "o200k": 2, "estimate": 2, "bytes": 3}]`
- 高い例 (o200k 降順 → bytes 昇順): `[{"text": "", "o200k": 6, "estimate": 3, "bytes": 6}, {"text": "", "o200k": 3, "estimate": 2, "bytes": 3}, {"text": "", "o200k": 3, "estimate": 2, "bytes": 3}]`

### carrier_pua_softbank
- o200k分布: `{"2": 66, "3": 419, "6": 3}`
- delta=estimate−o200k: `{"-3": 3, "-1": 419, "0": 66}`
- 安い例 (o200k → bytes 順): `[{"text": "", "o200k": 2, "estimate": 2, "bytes": 3}, {"text": "", "o200k": 2, "estimate": 2, "bytes": 3}, {"text": "", "o200k": 2, "estimate": 2, "bytes": 3}]`
- 高い例 (o200k 降順 → bytes 昇順): `[{"text": "", "o200k": 6, "estimate": 3, "bytes": 6}, {"text": "", "o200k": 6, "estimate": 3, "bytes": 6}, {"text": "", "o200k": 6, "estimate": 3, "bytes": 6}]`

### carrier_text_fallback
- o200k分布: `{"1": 13, "2": 28, "3": 86, "4": 113, "5": 94, "6": 46, "7": 15, "8": 2, "9": 1}`
- delta=estimate−o200k: `{"-4": 2, "-3": 2, "-2": 13, "-1": 36, "0": 316, "1": 27, "2": 2}`
- 安い例 (o200k → bytes 順): `[{"text": "[v", "o200k": 1, "estimate": 2, "bytes": 2}, {"text": "oda", "o200k": 1, "estimate": 1, "bytes": 3}, {"text": "†", "o200k": 1, "estimate": 1, "bytes": 3}]`
- 高い例 (o200k 降順 → bytes 昇順): `[{"text": "[飛んでいくお金]", "o200k": 9, "estimate": 9, "bytes": 23}, {"text": "[ハイビスカス]", "o200k": 8, "estimate": 8, "bytes": 20}, {"text": "[工事現場の人]", "o200k": 8, "estimate": 8, "bytes": 20}]`

### cldr_name_ar
- o200k分布: `{"1": 21, "2": 295, "3": 355, "4": 432, "5": 415, "6": 272, "7": 164, "8": 120, "9": 161, "10": 202, "11": 218, "12": 225, "13": 212, "14": 220, "15": 154, "16": 167, "17": 109, "18": 98, "19": 48, "20": 48, "21": 40, "22": 60, "23": 54, "24": 45, "25": 41, "26": 49, "27": 39, "28": 36, "29": 16, "30": 12, "31": 12, "33": 2}`
- delta=estimate−o200k: `{"-6": 7, "-5": 87, "-4": 213, "-3": 351, "-2": 833, "-1": 1500, "0": 1065, "1": 227, "2": 53, "3": 3, "4": 3}`
- 安い例 (o200k → bytes 順): `[{"text": "بق", "o200k": 1, "estimate": 1, "bytes": 4}, {"text": "سن", "o200k": 1, "estimate": 1, "bytes": 4}, {"text": "ين", "o200k": 1, "estimate": 1, "bytes": 4}]`
- 高い例 (o200k 降順 → bytes 昇順): `[{"text": "رجل وامرأة يمسكان بيد بعضهما: بشرة بلون فاتح ومعتدل وبشرة بلون معتدل مائل للغامق", "o200k": 33, "estimate": 27, "bytes": 146}, {"text": "رجل وامرأة يمسكان بيد بعضهما: بشرة بلون معتدل مائل للغامق وبشرة بلون فاتح ومعتدل", "o200k": 33, "estimate": 27, "bytes": 146}, {"text": "رجل وامرأة يمسكان بيد بعضهما: بشرة بلون غامق وبشرة بلون معتدل مائل للغامق", "o200k": 31, "estimate": 25, "bytes": 133}]`

### cldr_name_de
- o200k分布: `{"1": 60, "2": 325, "3": 400, "4": 491, "5": 316, "6": 250, "7": 301, "8": 385, "9": 412, "10": 262, "11": 284, "12": 176, "13": 169, "14": 86, "15": 75, "16": 69, "17": 42, "18": 93, "19": 24, "20": 89, "22": 33}`
- delta=estimate−o200k: `{"-7": 33, "-6": 66, "-5": 202, "-4": 406, "-3": 662, "-2": 1062, "-1": 1265, "0": 546, "1": 86, "2": 13, "3": 1}`
- 安い例 (o200k → bytes 順): `[{"text": "CD", "o200k": 1, "estimate": 1, "bytes": 2}, {"text": "Ei", "o200k": 1, "estimate": 1, "bytes": 2}, {"text": "WC", "o200k": 1, "estimate": 1, "bytes": 2}]`
- 高い例 (o200k 降順 → bytes 昇順): `[{"text": "sich küssendes Paar: Frau, Frau, helle Hautfarbe und mitteldunkle Hautfarbe", "o200k": 22, "estimate": 15, "bytes": 76}, {"text": "sich küssendes Paar: Frau, Frau, mitteldunkle Hautfarbe und helle Hautfarbe", "o200k": 22, "estimate": 15, "bytes": 76}, {"text": "sich küssendes Paar: Frau, Mann, helle Hautfarbe und mitteldunkle Hautfarbe", "o200k": 22, "estimate": 15, "bytes": 76}]`

### cldr_name_en
- o200k分布: `{"1": 205, "2": 701, "3": 714, "4": 337, "5": 252, "6": 438, "7": 570, "8": 393, "9": 218, "10": 87, "11": 93, "12": 94, "13": 84, "14": 66, "15": 10, "16": 24, "17": 48, "18": 8}`
- delta=estimate−o200k: `{"-5": 1, "-4": 1, "-3": 10, "-2": 95, "-1": 755, "0": 2578, "1": 849, "2": 53}`
- 安い例 (o200k → bytes 順): `[{"text": "om", "o200k": 1, "estimate": 1, "bytes": 2}, {"text": "ox", "o200k": 1, "estimate": 1, "bytes": 2}, {"text": "Leo", "o200k": 1, "estimate": 1, "bytes": 3}]`
- 高い例 (o200k 降順 → bytes 昇順): `[{"text": "couple with heart: man, man, medium-dark skin tone, medium-light skin tone", "o200k": 18, "estimate": 19, "bytes": 74}, {"text": "couple with heart: man, man, medium-light skin tone, medium-dark skin tone", "o200k": 18, "estimate": 19, "bytes": 74}, {"text": "couple with heart: woman, man, medium-dark skin tone, medium-light skin tone", "o200k": 18, "estimate": 19, "bytes": 76}]`

### cldr_name_es
- o200k分布: `{"1": 54, "2": 348, "3": 411, "4": 448, "5": 394, "6": 243, "7": 276, "8": 310, "9": 296, "10": 328, "11": 279, "12": 217, "13": 175, "14": 117, "15": 94, "16": 92, "17": 66, "18": 54, "19": 92, "20": 32, "21": 14, "22": 2}`
- delta=estimate−o200k: `{"-5": 10, "-4": 43, "-3": 260, "-2": 819, "-1": 1765, "0": 1130, "1": 266, "2": 47, "3": 2}`
- 安い例 (o200k → bytes 順): `[{"text": "om", "o200k": 1, "estimate": 1, "bytes": 2}, {"text": "Leo", "o200k": 1, "estimate": 1, "bytes": 3}, {"text": "ajo", "o200k": 1, "estimate": 1, "bytes": 3}]`
- 高い例 (o200k 降順 → bytes 昇順): `[{"text": "pareja enamorada: persona adulta, persona adulta, tono de piel claro medio, tono de piel oscuro medio", "o200k": 22, "estimate": 21, "bytes": 101}, {"text": "pareja enamorada: persona adulta, persona adulta, tono de piel oscuro medio, tono de piel claro medio", "o200k": 22, "estimate": 21, "bytes": 101}, {"text": "mujeres con orejas de conejo: tono de piel claro medio y tono de piel oscuro medio", "o200k": 21, "estimate": 18, "bytes": 82}]`

### cldr_name_fr
- o200k分布: `{"1": 73, "2": 384, "3": 398, "4": 380, "5": 292, "6": 321, "7": 366, "8": 378, "9": 373, "10": 267, "11": 269, "12": 192, "13": 146, "14": 149, "15": 105, "16": 103, "17": 65, "18": 44, "19": 32, "20": 4}`
- delta=estimate−o200k: `{"-6": 3, "-5": 16, "-4": 62, "-3": 306, "-2": 1124, "-1": 1846, "0": 852, "1": 117, "2": 13, "3": 2}`
- 安い例 (o200k → bytes 順): `[{"text": "CD", "o200k": 1, "estimate": 1, "bytes": 2}, {"text": "WC", "o200k": 1, "estimate": 1, "bytes": 2}, {"text": "ok", "o200k": 1, "estimate": 1, "bytes": 2}]`
- 高い例 (o200k 降順 → bytes 昇順): `[{"text": "femmes avec des oreilles de lapin : peau foncée et peau moyennement claire", "o200k": 20, "estimate": 17, "bytes": 77}, {"text": "femmes avec des oreilles de lapin : peau moyennement claire et peau foncée", "o200k": 20, "estimate": 17, "bytes": 77}, {"text": "femmes avec des oreilles de lapin : peau légèrement mate et peau moyennement claire", "o200k": 20, "estimate": 17, "bytes": 87}]`

### cldr_name_hi
- o200k分布: `{"1": 4, "2": 116, "3": 247, "4": 275, "5": 293, "6": 316, "7": 279, "8": 291, "9": 266, "10": 290, "11": 327, "12": 351, "13": 269, "14": 216, "15": 154, "16": 102, "17": 75, "18": 47, "19": 81, "20": 86, "21": 100, "22": 74, "23": 40, "24": 9, "25": 4, "26": 7, "27": 9, "28": 7, "29": 4, "30": 1}`
- delta=estimate−o200k: `{"-6": 5, "-5": 17, "-4": 99, "-3": 358, "-2": 1035, "-1": 1383, "0": 835, "1": 361, "2": 154, "3": 63, "4": 28, "5": 2}`
- 安い例 (o200k → bytes 順): `[{"text": "पर", "o200k": 1, "estimate": 1, "bytes": 6}, {"text": "बस", "o200k": 1, "estimate": 1, "bytes": 6}, {"text": "नाक", "o200k": 1, "estimate": 1, "bytes": 9}]`
- 高い例 (o200k 降順 → bytes 昇順): `[{"text": "हस्तचालित व्हीलचेयर पर बैठी औरत: हल्की साँवली त्वचा, दाईं ओर चेहरा घुमाए", "o200k": 30, "estimate": 25, "bytes": 190}, {"text": "मोटर व्हीलचेयर पर बैठी औरत: हल्की साँवली त्वचा, दाईं ओर चेहरा घुमाए", "o200k": 29, "estimate": 24, "bytes": 175}, {"text": "हस्तचालित व्हीलचेयर पर बैठी औरत: हल्की गोरी त्वचा, दाईं ओर चेहरा घुमाए", "o200k": 29, "estimate": 25, "bytes": 184}]`

### cldr_name_ja
- o200k分布: `{"1": 58, "2": 314, "3": 407, "4": 394, "5": 361, "6": 292, "7": 179, "8": 158, "9": 176, "10": 230, "11": 273, "12": 279, "13": 260, "14": 209, "15": 156, "16": 137, "17": 75, "18": 77, "19": 57, "20": 59, "21": 56, "22": 51, "23": 38, "24": 28, "25": 14, "26": 4}`
- delta=estimate−o200k: `{"-4": 7, "-3": 23, "-2": 210, "-1": 1003, "0": 2022, "1": 1073, "2": 4}`
- 安い例 (o200k → bytes 順): `[{"text": "CD", "o200k": 1, "estimate": 1, "bytes": 2}, {"text": "MD", "o200k": 1, "estimate": 1, "bytes": 2}, {"text": "WC", "o200k": 1, "estimate": 1, "bytes": 2}]`
- 高い例 (o200k 降順 → bytes 昇順): `[{"text": "カップルとハート: 大人 大人 やや濃い肌色 やや薄い肌色", "o200k": 26, "estimate": 25, "bytes": 77}, {"text": "カップルとハート: 大人 大人 やや薄い肌色 やや濃い肌色", "o200k": 26, "estimate": 25, "bytes": 77}, {"text": "カップルとハート: 男性 男性 やや濃い肌色 やや薄い肌色", "o200k": 26, "estimate": 25, "bytes": 77}]`

### cldr_name_ko
- o200k分布: `{"1": 47, "2": 320, "3": 375, "4": 375, "5": 278, "6": 231, "7": 294, "8": 357, "9": 382, "10": 374, "11": 265, "12": 219, "13": 182, "14": 170, "15": 145, "16": 97, "17": 48, "18": 34, "19": 36, "20": 39, "21": 33, "22": 26, "23": 12, "24": 2, "25": 1}`
- delta=estimate−o200k: `{"-4": 1, "-3": 23, "-2": 213, "-1": 1214, "0": 2773, "1": 118}`
- 安い例 (o200k → bytes 順): `[{"text": "ATM", "o200k": 1, "estimate": 1, "bytes": 3}, {"text": "DNA", "o200k": 1, "estimate": 1, "bytes": 3}, {"text": "각", "o200k": 1, "estimate": 1, "bytes": 3}]`
- 高い例 (o200k 降順 → bytes 昇順): `[{"text": "세로 막대가 있는 오른쪽 화살표 위에 세로 막대가 있는 왼쪽 화살표", "o200k": 25, "estimate": 25, "bytes": 91}, {"text": "토끼 귀를 쓰고 춤추는 남자들: 연한 갈색 피부 진한 갈색 피부", "o200k": 24, "estimate": 24, "bytes": 83}, {"text": "토끼 귀를 쓰고 춤추는 남자들: 진한 갈색 피부 연한 갈색 피부", "o200k": 24, "estimate": 24, "bytes": 83}]`

### cldr_name_pt
- o200k分布: `{"1": 55, "2": 377, "3": 340, "4": 399, "5": 416, "6": 405, "7": 379, "8": 439, "9": 361, "10": 286, "11": 203, "12": 123, "13": 123, "14": 101, "15": 100, "16": 74, "17": 66, "18": 48, "19": 32, "20": 12, "21": 3}`
- delta=estimate−o200k: `{"-6": 13, "-5": 56, "-4": 241, "-3": 636, "-2": 1147, "-1": 1363, "0": 682, "1": 174, "2": 26, "3": 4}`
- 安い例 (o200k → bytes 順): `[{"text": "WC", "o200k": 1, "estimate": 1, "bytes": 2}, {"text": "cd", "o200k": 1, "estimate": 1, "bytes": 2}, {"text": "om", "o200k": 1, "estimate": 1, "bytes": 2}]`
- 高い例 (o200k 降順 → bytes 昇順): `[{"text": "homem em cadeira de rodas motorizada: pele morena escura e de frente para a direita", "o200k": 21, "estimate": 19, "bytes": 83}, {"text": "mulher em cadeira de rodas motorizada: pele morena escura e de frente para a direita", "o200k": 21, "estimate": 19, "bytes": 84}, {"text": "pessoa em cadeira de rodas motorizada: pele morena escura e de frente para a direita", "o200k": 21, "estimate": 19, "bytes": 84}]`

### cldr_name_ru
- o200k分布: `{"1": 23, "2": 247, "3": 407, "4": 334, "5": 354, "6": 328, "7": 275, "8": 295, "9": 331, "10": 333, "11": 362, "12": 290, "13": 177, "14": 125, "15": 142, "16": 105, "17": 62, "18": 58, "19": 46, "20": 15, "21": 9, "22": 13, "23": 6, "24": 3, "25": 2}`
- delta=estimate−o200k: `{"-7": 1, "-5": 5, "-4": 47, "-3": 141, "-2": 702, "-1": 1475, "0": 1205, "1": 526, "2": 182, "3": 52, "4": 6}`
- 安い例 (o200k → bytes 順): `[{"text": "CD", "o200k": 1, "estimate": 1, "bytes": 2}, {"text": "DVD", "o200k": 1, "estimate": 1, "bytes": 3}, {"text": "еж", "o200k": 1, "estimate": 1, "bytes": 4}]`
- 高い例 (o200k 降順 → bytes 昇順): `[{"text": "человек в кресле-коляске с ручным приводом: очень темный тон кожи , направленные вправо", "o200k": 25, "estimate": 26, "bytes": 159}, {"text": "человек в кресле-коляске с ручным приводом: очень светлый тон кожи , направленные вправо", "o200k": 25, "estimate": 26, "bytes": 161}, {"text": "человек в кресле-коляске с ручным приводом: темный тон кожи , направленные вправо", "o200k": 24, "estimate": 24, "bytes": 148}]`

### cldr_name_th
- o200k分布: `{"1": 17, "2": 152, "3": 227, "4": 315, "5": 323, "6": 295, "7": 254, "8": 240, "9": 144, "10": 119, "11": 166, "12": 198, "13": 224, "14": 301, "15": 247, "16": 236, "17": 174, "18": 109, "19": 85, "20": 35, "21": 44, "22": 93, "23": 42, "24": 123, "25": 61, "26": 68, "27": 33, "28": 16, "33": 1}`
- delta=estimate−o200k: `{"-3": 4, "-2": 15, "-1": 346, "0": 3961, "1": 16}`
- 安い例 (o200k → bytes 順): `[{"text": "คน", "o200k": 1, "estimate": 1, "bytes": 6}, {"text": "รถ", "o200k": 1, "estimate": 1, "bytes": 6}, {"text": "ลา", "o200k": 1, "estimate": 1, "bytes": 6}]`
- 高い例 (o200k 降順 → bytes 昇順): `[{"text": "สี่เหลี่ยมขนมเปียกปูนกลวงที่มีสี่เหลี่ยมขนมเปียกปูนทึบ", "o200k": 33, "estimate": 33, "bytes": 162}, {"text": "ผู้ชายในชุดหูกระต่าย: โทนผิวสีขาว โทนผิวสีขาวเหลือง", "o200k": 28, "estimate": 28, "bytes": 147}, {"text": "ผู้ชายในชุดหูกระต่าย: โทนผิวสีขาวเหลือง โทนผิวสีขาว", "o200k": 28, "estimate": 28, "bytes": 147}]`

### cldr_name_zh
- o200k分布: `{"1": 119, "2": 531, "3": 507, "4": 364, "5": 282, "6": 219, "7": 211, "8": 317, "9": 393, "10": 375, "11": 249, "12": 192, "13": 144, "14": 127, "15": 98, "16": 53, "17": 78, "18": 52, "19": 28, "20": 2, "24": 1}`
- delta=estimate−o200k: `{"-4": 1, "-3": 6, "-2": 92, "-1": 338, "0": 2160, "1": 1743, "2": 2}`
- 安い例 (o200k → bytes 順): `[{"text": "OK", "o200k": 1, "estimate": 1, "bytes": 2}, {"text": "DNA", "o200k": 1, "estimate": 1, "bytes": 3}, {"text": "DVD", "o200k": 1, "estimate": 1, "bytes": 3}]`
- 高い例 (o200k 降順 → bytes 昇順): `[{"text": "上面是头带杠的向左箭头，下面是头带杠的向右箭头", "o200k": 24, "estimate": 22, "bytes": 69}, {"text": "手拉手的一男一女: 中等-浅肤色中等-深肤色", "o200k": 20, "estimate": 20, "bytes": 58}, {"text": "手拉手的一男一女: 中等-深肤色中等-浅肤色", "o200k": 20, "estimate": 20, "bytes": 58}]`

### emoticon_ascii
- o200k分布: `{"1": 1, "2": 14, "3": 26, "4": 19, "5": 7, "6": 2, "7": 2}`
- delta=estimate−o200k: `{"-4": 3, "-3": 5, "-2": 17, "-1": 19, "0": 19, "1": 7, "2": 1}`
- 安い例 (o200k → bytes 順): `[{"text": ";;", "o200k": 1, "estimate": 1, "bytes": 2}, {"text": ":c)", "o200k": 2, "estimate": 3, "bytes": 3}, {"text": ":o)", "o200k": 2, "estimate": 3, "bytes": 3}]`
- 高い例 (o200k 降順 → bytes 昇順): `[{"text": "((d[-_-]b))", "o200k": 7, "estimate": 6, "bytes": 11}, {"text": "(+_+) (@_@)", "o200k": 7, "estimate": 4, "bytes": 11}, {"text": "(T_T) (;_;)", "o200k": 6, "estimate": 6, "bytes": 11}]`

### emoticon_mixed
- o200k分布: `{"3": 6, "4": 3, "5": 2, "6": 4, "7": 2, "8": 1, "9": 1}`
- delta=estimate−o200k: `{"-6": 3, "-5": 1, "-4": 2, "-3": 1, "-2": 1, "-1": 3, "0": 8}`
- 安い例 (o200k → bytes 順): `[{"text": ":‑/", "o200k": 3, "estimate": 2, "bytes": 5}, {"text": ":‑x", "o200k": 3, "estimate": 3, "bytes": 5}, {"text": "(^O^)／", "o200k": 3, "estimate": 3, "bytes": 8}]`
- 高い例 (o200k 降順 → bytes 昇順): `[{"text": "(~_~;) (・.・;)", "o200k": 9, "estimate": 3, "bytes": 17}, {"text": "(-_-)/~~~ ($··)/~~~", "o200k": 8, "estimate": 3, "bytes": 21}, {"text": "(=^·^=)", "o200k": 7, "estimate": 1, "bytes": 8}]`

### font_original
- o200k分布: `{"1": 196, "2": 28}`
- delta=estimate−o200k: `{"-1": 3, "0": 209, "1": 12}`
- 安い例 (o200k → bytes 順): `[{"text": " ", "o200k": 1, "estimate": 0, "bytes": 1}, {"text": "!", "o200k": 1, "estimate": 1, "bytes": 1}, {"text": "\"", "o200k": 1, "estimate": 1, "bytes": 1}]`
- 高い例 (o200k 降順 → bytes 昇順): `[{"text": "", "o200k": 2, "estimate": 2, "bytes": 2}, {"text": "", "o200k": 2, "estimate": 2, "bytes": 2}, {"text": "", "o200k": 2, "estimate": 2, "bytes": 2}]`

### font_unicode_target
- o200k分布: `{"1": 142, "2": 357, "3": 545}`
- delta=estimate−o200k: `{"-1": 189, "0": 840, "1": 15}`
- 安い例 (o200k → bytes 順): `[{"text": " ", "o200k": 1, "estimate": 0, "bytes": 1}, {"text": "!", "o200k": 1, "estimate": 1, "bytes": 1}, {"text": "#", "o200k": 1, "estimate": 1, "bytes": 1}]`
- 高い例 (o200k 降順 → bytes 昇順): `[{"text": "⍽", "o200k": 3, "estimate": 2, "bytes": 3}, {"text": "⎋", "o200k": 3, "estimate": 2, "bytes": 3}, {"text": "⎛", "o200k": 3, "estimate": 2, "bytes": 3}]`

### font_word_pua_alias
- o200k分布: `{"1": 4, "2": 220}`
- delta=estimate−o200k: `{"0": 222, "1": 2}`
- 安い例 (o200k → bytes 順): `[{"text": "", "o200k": 1, "estimate": 1, "bytes": 3}, {"text": "", "o200k": 1, "estimate": 1, "bytes": 3}, {"text": "", "o200k": 1, "estimate": 2, "bytes": 3}]`
- 高い例 (o200k 降順 → bytes 昇順): `[{"text": "", "o200k": 2, "estimate": 2, "bytes": 3}, {"text": "", "o200k": 2, "estimate": 2, "bytes": 3}, {"text": "", "o200k": 2, "estimate": 2, "bytes": 3}]`

### formal_signwriting_ascii_sample
- o200k分布: `{"44": 1}`
- delta=estimate−o200k: `{"0": 1}`
- 安い例 (o200k → bytes 順): `[{"text": "AS10011S10019S2e704S2e748M525x535S2e748483x510S10011501x466S2e704510x500S10019476x475", "o200k": 44, "estimate": 44, "bytes": 85}]`
- 高い例 (o200k 降順 → bytes 昇順): `[{"text": "AS10011S10019S2e704S2e748M525x535S2e748483x510S10011501x466S2e704510x500S10019476x475", "o200k": 44, "estimate": 44, "bytes": 85}]`

### gemoji_shortcode
- o200k分布: `{"2": 12, "3": 428, "4": 643, "5": 409, "6": 224, "7": 97, "8": 54, "9": 31, "10": 5, "11": 8, "12": 2}`
- delta=estimate−o200k: `{"-5": 2, "-4": 12, "-3": 47, "-2": 213, "-1": 703, "0": 843, "1": 92, "2": 1}`
- 安い例 (o200k → bytes 順): `[{"text": ":a:", "o200k": 2, "estimate": 3, "bytes": 3}, {"text": ":b:", "o200k": 2, "estimate": 3, "bytes": 3}, {"text": ":m:", "o200k": 2, "estimate": 3, "bytes": 3}]`
- 高い例 (o200k 降順 → bytes 昇順): `[{"text": ":south_georgia_south_sandwich_islands:", "o200k": 12, "estimate": 7, "bytes": 38}, {"text": ":face_with_open_eyes_and_hand_over_mouth:", "o200k": 12, "estimate": 10, "bytes": 41}, {"text": ":family_woman_woman_boy_boy:", "o200k": 11, "estimate": 7, "bytes": 28}]`

### html_named_reference
- o200k分布: `{"1": 11, "2": 59, "3": 477, "4": 1060, "5": 444, "6": 130, "7": 42, "8": 8}`
- delta=estimate−o200k: `{"-5": 3, "-4": 6, "-3": 47, "-2": 340, "-1": 1054, "0": 646, "1": 109, "2": 22, "3": 4}`
- 安い例 (o200k → bytes 順): `[{"text": "&gt", "o200k": 1, "estimate": 2, "bytes": 3}, {"text": "&lt", "o200k": 1, "estimate": 2, "bytes": 3}, {"text": "&amp", "o200k": 1, "estimate": 2, "bytes": 4}]`
- 高い例 (o200k 降順 → bytes 昇順): `[{"text": "&NotHumpDownHump;", "o200k": 8, "estimate": 3, "bytes": 17}, {"text": "&leftharpoondown;", "o200k": 8, "estimate": 3, "bytes": 17}, {"text": "&nLeftrightarrow;", "o200k": 8, "estimate": 3, "bytes": 17}]`

### ipa_equivalent
- o200k分布: `{"1": 51, "2": 110, "3": 2, "4": 3, "5": 5, "6": 2}`
- delta=estimate−o200k: `{"-3": 4, "-2": 5, "-1": 75, "0": 79, "1": 10}`
- 安い例 (o200k → bytes 順): `[{"text": ".", "o200k": 1, "estimate": 1, "bytes": 1}, {"text": "a", "o200k": 1, "estimate": 1, "bytes": 1}, {"text": "b", "o200k": 1, "estimate": 1, "bytes": 1}]`
- 高い例 (o200k 降順 → bytes 昇順): `[{"text": "ɖ͡ʐ", "o200k": 6, "estimate": 3, "bytes": 6}, {"text": "ʈ͡ʂ", "o200k": 6, "estimate": 3, "bytes": 6}, {"text": "d͡ʑ", "o200k": 5, "estimate": 3, "bytes": 5}]`

### ja_kaomoji_supplement
- o200k分布: `{"1": 1, "2": 10, "3": 19, "4": 49, "5": 112, "6": 132, "7": 158, "8": 216, "9": 141, "10": 155, "11": 172, "12": 158, "13": 162, "14": 173, "15": 164, "16": 150, "17": 127, "18": 108, "19": 95, "20": 72, "21": 99, "22": 70, "23": 64, "24": 63, "25": 47, "26": 42, "27": 36, "28": 45, "29": 24, "30": 20, "31": 18, "32": 17, "33": 13, "34": 12, "35": 14, "36": 17, "37": 11, "38": 7, "39": 4, "40": 3, "41": 12, "42": 3, "43": 5, "45": 1, "47": 2, "48": 4, "49": 2, "51": 4, "52": 3, "55": 2, "58": 1, "62": 2, "71": 1, "72": 1, "76": 1, "80": 1, "82": 2, "84": 1, "93": 1, "94": 1}`
- delta=estimate−o200k: `{"-30": 1, "-29": 2, "-27": 3, "-26": 1, "-25": 1, "-23": 2, "-22": 2, "-21": 6, "-20": 1, "-19": 1, "-18": 7, "-17": 7, "-16": 10, "-15": 15, "-14": 13, "-13": 19, "-12": 22, "-11": 22, "-10": 37, "-9": 68, "-8": 107, "-7": 119, "-6": 247, "-5": 233, "-4": 390, "-3": 444, "-2": 555, "-1": 406, "0": 237, "1": 49, "2": 10, "3": 2, "4": 4, "5": 2, "7": 2, "8": 1, "10": 2}`
- 安い例 (o200k → bytes 順): `[{"text": "><", "o200k": 1, "estimate": 1, "bytes": 2}, {"text": ":>", "o200k": 2, "estimate": 1, "bytes": 2}, {"text": "<3", "o200k": 2, "estimate": 2, "bytes": 2}]`
- 高い例 (o200k 降順 → bytes 昇順): `[{"text": "ｶﾀｶﾀｶﾀｶﾀｶﾀｶﾀｶﾀｶﾀｶﾀｶﾀｶﾀｶﾀｶﾀｶﾀ\n　∧＿∧\n (ヽ´Д`)ﾊｧﾊｧ\n＿/_ﾐつ/￣￣￣/\n　  ＼/＿＿＿/", "o200k": 94, "estimate": 87, "bytes": 164}, {"text": "( >д<).;':ﾍｯｸｼｮﾝ! ⁽⁽◞(꒪ͦᴗ̵̍꒪ͦ=͟͟͞͞ ꒪ͦᴗ̵̍꒪ͦ)◟⁾⁾ﾀﾞﾚｶｳﾜｻｼﾃﾙ?", "o200k": 93, "estimate": 63, "bytes": 126}, {"text": "〃 ≡≡三≡ '〇｜\n`｡･｡･　(ﾟ∀ﾟ≡ﾟ∀ﾟ)　／｜\n　　｜￣￣￣￣　｜　｜\n　　｜　脱水中　｜　｜ｷﾞｭﾙﾙﾙ！\n　　｜　　　　　｜　｜\n　　｜　　　　　｜／\n　　　￣￣￣￣￣", "o200k": 84, "estimate": 66, "bytes": 252}]`

### xsampa_ascii
- o200k分布: `{"1": 111, "2": 48, "3": 8, "4": 1}`
- delta=estimate−o200k: `{"-1": 19, "0": 149}`
- 安い例 (o200k → bytes 順): `[{"text": "\"", "o200k": 1, "estimate": 1, "bytes": 1}, {"text": "%", "o200k": 1, "estimate": 1, "bytes": 1}, {"text": "&", "o200k": 1, "estimate": 1, "bytes": 1}]`
- 高い例 (o200k 降順 → bytes 昇順): `[{"text": "t`_>", "o200k": 4, "estimate": 3, "bytes": 4}, {"text": "c_>", "o200k": 3, "estimate": 2, "bytes": 3}, {"text": "k_>", "o200k": 3, "estimate": 2, "bytes": 3}]`

## 方法・注意

- 西洋/キリル顔文字の主表 emoticons-ascii-o200k.jsonl (485種) も別途参照。この表では同じ辞書キーを再計測収録せず、補充分だけを残した。
- bare 入力を encode_ordinary で計測。追加で先頭ASCIIスペース1個の実測と推定を別フィールドに保存。入力にNFC/NFD変換やstripはせず、estimate_tokens内部の正規化は現行仕様のまま。
- category×exact-text 内だけ重複排除。カテゴリをまたぐ同一文字列は別行。出典の多対一・同一顔文字の複数ラベルを origins に保存。
- CLDR は release-48、12言語 en/ja/ko/zh/ru/ar/de/fr/es/pt/th/hi の annotations と annotationsDerived。tts名称のみ入力として測定し、検索keywordはmetadata。継承マーカーを本文として測らない。言語名は注釈名の言語であり、顔文字の発祥を示さない。
- shortcode は gemoji の実在aliasのみ。Slack/Discord のカスタム絵文字・動的ID/アニメID・全サービス互換は未検証。文字列 :smile: 自体のコストと描画された😄のコストは別物。
- EmojiSources は Unicode 17.0 の現行Unicode↔歴史的Shift-JIS対応。Shift-JISバイト自体をUTF-8文字列と偽って計測していない。
- emoji4unicode は2000年代の提案資料。PUA値の正規/一方向fallbackを区別し、proposed Unicode値を現行の確定対応とは扱わない。PUAの意味はフォント・機器・符号体系に依存し、フォントなしのモデル理解は不明。
- Wingdings/Webdings等は元符号・Word式F000オフセットPUA・Unicode対応先を別カテゴリで計測。元ASCII符号の安さは表示絵柄の学習や意味保持の証拠ではない。
- HTMLはPython stdlib html.entities.html5の実在全キー（セミコロンあり/省略可を区別）。テキスト記法のコストであり、レンダリング後のコストではない。
- kaomoji-collection のHTML実体参照は1回だけ html.unescape し、その処理の有無をmetadataに保存。日本主表との重複を省いた。
- emotのPythonはAST literalだけ読んだ。辞書キーに含まれるバックスラッシュを勝手に除去していないので、一部は通常の顔文字でなく辞書の表記癖を含む。
- カテゴリの1行は1つのglyph/意味とは限らない。複数行AAも入力改行を保持する。

## 未測定・網羅性の限界

- Unicode外の追加候補と出典は self-non-unicode-systems.md に整理。
- 「全て」は閉じた集合ではない。顔文字・ASCII art・カスタム絵文字・フォント対応・私用領域は無限に生成/拡張可能。ここでの全件は列挙した公開ソースの取得スナップショット内のみ。
- モデルによる顔文字意味理解、復元、皮肉・文化差、前後文脈によるBPE変化（先頭space以外）、フォント描画の同等性、CLDRの全locale/継承展開は未測定。
- Formal SignWriting は公式SignMaker READMEの実例1件だけ測定。X-SAMPAはEpitranの公開対応表をASCII/IPAの別カテゴリで測定。全文/連続音声列への一般化は未検証。
- 古代文字・記号体系全般（ヒエログリフ、錬金術、占星術、楽譜、速記、点字、SignWritingの全文法/Blissymbolics等）をこの表だけで全網羅したわけではない。別カテゴリとして調査可能。
- Unicode参照表PRの作業と分離。PR/commit/pushなし。/workspace/TalkCompress と利用者PCには触れていない。

## 出典・再利用条件

- EmojiSources.txt: https://www.unicode.org/Public/17.0.0/ucd/EmojiSources.txt / Unicode-3.0 / SHA256 `db1b517734304781702789d586801275e82bd91ff45be7d34e2dc250cc10e34d`
- cldr-ar.xml: https://raw.githubusercontent.com/unicode-org/cldr/release-48/common/annotations/ar.xml / Unicode-3.0 / SHA256 `64e2f9817583f3e5378647bc2b6e82a7d6896f4a084072e1520500ef1afe3887`
- cldr-de.xml: https://raw.githubusercontent.com/unicode-org/cldr/release-48/common/annotations/de.xml / Unicode-3.0 / SHA256 `12eb92612539223d4dcfaec3c45437a31a82022b1c59160873fa4d4439dd7d07`
- cldr-derived-ar.xml: https://raw.githubusercontent.com/unicode-org/cldr/release-48/common/annotationsDerived/ar.xml / Unicode-3.0 / SHA256 `beac3c6bc02012d9b87eef8ae3e152630c7a8cd8f015ff5f28193bcc34541b6b`
- cldr-derived-de.xml: https://raw.githubusercontent.com/unicode-org/cldr/release-48/common/annotationsDerived/de.xml / Unicode-3.0 / SHA256 `c7511229fdfa1471cecba195ff4a094d70507a320e5364e0edc8ca5c72eeae09`
- cldr-derived-en.xml: https://raw.githubusercontent.com/unicode-org/cldr/release-48/common/annotationsDerived/en.xml / Unicode-3.0 / SHA256 `d76bd041c8c9e7b00b716aff8b7d9dbf509877010e191d5efd068be2553e066e`
- cldr-derived-es.xml: https://raw.githubusercontent.com/unicode-org/cldr/release-48/common/annotationsDerived/es.xml / Unicode-3.0 / SHA256 `ea9b3abc0a2c73a815faec1034764b6a503d14638ad4fb9556d8a7341838672c`
- cldr-derived-fr.xml: https://raw.githubusercontent.com/unicode-org/cldr/release-48/common/annotationsDerived/fr.xml / Unicode-3.0 / SHA256 `f76bab496c0e1a9ae8fc309a6a01a313089ec167289db59c308a33cfd225f78b`
- cldr-derived-hi.xml: https://raw.githubusercontent.com/unicode-org/cldr/release-48/common/annotationsDerived/hi.xml / Unicode-3.0 / SHA256 `56156ab368112abf93f200937e4ee2d86601a37142167091f14737c831357db8`
- cldr-derived-ja.xml: https://raw.githubusercontent.com/unicode-org/cldr/release-48/common/annotationsDerived/ja.xml / Unicode-3.0 / SHA256 `4f2e1b1e64594cabbe12c6f60cee497863923f49833e1631942f16d015838e67`
- cldr-derived-ko.xml: https://raw.githubusercontent.com/unicode-org/cldr/release-48/common/annotationsDerived/ko.xml / Unicode-3.0 / SHA256 `c624e7369d0b283c9f7085360157b7f5f701260b36e4e5ff3f9552ce196dbbb8`
- cldr-derived-pt.xml: https://raw.githubusercontent.com/unicode-org/cldr/release-48/common/annotationsDerived/pt.xml / Unicode-3.0 / SHA256 `8810bb38da561be161413f6292a6ce4a81d815ae9b6906a16a5b38d89f398496`
- cldr-derived-ru.xml: https://raw.githubusercontent.com/unicode-org/cldr/release-48/common/annotationsDerived/ru.xml / Unicode-3.0 / SHA256 `cd3aa5d40a42d473c7796584d560cac9b35f223561dd3e0e57594fec5003c010`
- cldr-derived-th.xml: https://raw.githubusercontent.com/unicode-org/cldr/release-48/common/annotationsDerived/th.xml / Unicode-3.0 / SHA256 `28378f0aea0872c920af6398a9cde2fe032e29e3fc03341c9dbee4ac7c1190f5`
- cldr-derived-zh.xml: https://raw.githubusercontent.com/unicode-org/cldr/release-48/common/annotationsDerived/zh.xml / Unicode-3.0 / SHA256 `777acebb7c4ed103c34f5605881a2537656e0a17d9d1127518da7cd54f612bcc`
- cldr-en.xml: https://raw.githubusercontent.com/unicode-org/cldr/release-48/common/annotations/en.xml / Unicode-3.0 / SHA256 `8511aadd046fdba2f0ffe590266ced8bbf48175ad139b2675d85d7141057b235`
- cldr-es.xml: https://raw.githubusercontent.com/unicode-org/cldr/release-48/common/annotations/es.xml / Unicode-3.0 / SHA256 `fe8384e9cd2ee0998eb00ddf5549272eb5b56739e539ef33fedcd727fce5026a`
- cldr-fr.xml: https://raw.githubusercontent.com/unicode-org/cldr/release-48/common/annotations/fr.xml / Unicode-3.0 / SHA256 `d832108eabaad757700107dab95b3d9b0a198e46c34db3f255f80fe399cfbe94`
- cldr-hi.xml: https://raw.githubusercontent.com/unicode-org/cldr/release-48/common/annotations/hi.xml / Unicode-3.0 / SHA256 `a6b256ab43b7fa894564ac35b49cfa50f42778987f3e4ab4986477dbde1e2597`
- cldr-ja.xml: https://raw.githubusercontent.com/unicode-org/cldr/release-48/common/annotations/ja.xml / Unicode-3.0 / SHA256 `27b1009d4ca4cb61b68a9e8c52f974629d76d00b95711bd984783bc0f58d3da4`
- cldr-ko.xml: https://raw.githubusercontent.com/unicode-org/cldr/release-48/common/annotations/ko.xml / Unicode-3.0 / SHA256 `1d7007de84c0431f892b3f8c87b24835c8f8474a1711a2406592aaf24f5db72d`
- cldr-pt.xml: https://raw.githubusercontent.com/unicode-org/cldr/release-48/common/annotations/pt.xml / Unicode-3.0 / SHA256 `784be701f969963dc1d8240cd8ae02eb5bad28153bc9d0613e5c5777537e5398`
- cldr-ru.xml: https://raw.githubusercontent.com/unicode-org/cldr/release-48/common/annotations/ru.xml / Unicode-3.0 / SHA256 `325bc6bb96aff4a5a9124a9087313669b0e88da920b84e261d61a402ea9405a8`
- cldr-th.xml: https://raw.githubusercontent.com/unicode-org/cldr/release-48/common/annotations/th.xml / Unicode-3.0 / SHA256 `9d4fa1d15ad86074862c886ff59f2153feb2097762aed6802334e91024d488fe`
- cldr-zh.xml: https://raw.githubusercontent.com/unicode-org/cldr/release-48/common/annotations/zh.xml / Unicode-3.0 / SHA256 `92389f71659998736530c72d4dcc86e453fe0be170cde5c5ad27094cab2a2de8`
- dingbats.csv: https://raw.githubusercontent.com/mwilliamson/dingbat-to-unicode/main/dingbats.csv / BSD-2-Clause / SHA256 `88244b93435fe6f9aa3faa791e24ab0168deaff54021532e1c3071c8161676eb`
- emoji4unicode.xml: https://raw.githubusercontent.com/google/emoji4unicode/master/data/emoji4unicode.xml / Apache-2.0 / SHA256 `221369d8cabd3f6f217ba82cf25d41c0f97d283cefa6a9a66de1af69121418d3`
- emot.py: https://raw.githubusercontent.com/NeelShah18/emot/master/emot/emo_unicode.py / MIT / SHA256 `05126202199c3a9d1ce98b50f9a95be8a16af9700d6732be2d66207f7c0af822`
- gemoji.json: https://raw.githubusercontent.com/github/gemoji/master/db/emoji.json / MIT / SHA256 `b174ae2aeb321b52f64adb9ff412f966a7f338839d780784dd15dcad702c2dd6`
- ipa-xsampa.csv: https://raw.githubusercontent.com/dmort27/epitran/master/epitran/data/ipa-xsampa.csv / MIT / SHA256 `4e3f3d9eb3245f4eb95ba47225b625e632b35f218ab6c7868d66b9363dcef9a6`
- kaomoji-collection.json: https://raw.githubusercontent.com/kaomojiya-collection/kaomoji-collection/main/kaomoji.json / MIT / SHA256 `7373e5dabd04fdc91cfb452af6f65950fa6953a613c804cbcd790d3ed4ef738d`
- kaomoji-data.json: https://raw.githubusercontent.com/kaomojikan/kaomoji-data/main/kaomoji.json / MIT / SHA256 `22721e1b31d60fee5a9bd9f26c8639ab4efee2e6c01cec3f674f0e0d1d3aea2b`
- python-stdlib-html.entities: https://docs.python.org/3/library/html.entities.html / PSF-2.0 / SHA256 `d7ed3f33f59f35a1c60aeb3b11e3c95dc136b24e0705f762a9c3831c2f51c3ca`
- signmaker-README.md: https://raw.githubusercontent.com/sutton-signwriting/signmaker/main/README.md / MIT / SHA256 `3d801ed2a26fbcde343807deeefe41f833ce30459a27f73e3095adc79b8a7582`

再配布時は self-notations-sources/ 内のMIT/BSD/Apache/Unicode/PSFライセンスおよびNOTICEを保持。第三者文字列の意味・商標・特定フォントの権利を譲渡するものではない。
JSONL SHA256: `017b8b5771c9570c346e1e374f1c27bc90785b30680969afa733520330a0c590`

## 全行の再検証

- JSONL全64,564行を再parseし、重複キーなし・token ids・bare/leading-space実測・estimate・delta・UTF-8 bytes・出典URL/hash/licenseの非欠落を再検証: PASS。
- 全体: 一致24,910 / 過小32,946 / 過大6,708。CLDR名称は顔文字とは性質が異なるため全体比だけで品質評価しない。
- 測定HEAD 3c29092 の TesseraTalk/ は基準main 84e5dca と差分なし（追加lookup表の文書コミットだけ異なる）。
- JSONL 47,242,119 bytes。転送向けgzipも生成（2,984,857 bytes）。gzipと出典のライセンス/NOTICE/manifestを併せて取り込める。
- リポジトリテストは未実行（実装変更なし、全データを独立再計算検証）。
