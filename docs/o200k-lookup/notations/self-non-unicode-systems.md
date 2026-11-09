# Unicode絵文字一覧より外側にある記法の調査メモ

調査日: 2026-11-07 JST。AI可読性: 未測定。
「文字列として測れる」ことと「AIが絵柄/意味/空間配置を理解する」ことは分ける。

## 今回実測に加えた系統

- HTML named character references: `&lt;`, `&hearts;` 等。古いWeb上の文字・記号表現。Python stdlib全2,231キー。セミコロン省略形は文脈上の適否が違う。見た目の文字にデコードされる前と後は別入力。
- X-SAMPA (1995): IPAをASCIIで表す音声記法。UCLの一次説明 https://www.phon.ucl.ac.uk/home/sampa/x-sampa.htm 。そのWeb文書の再利用許諾を推測せず、実測にはMITのEpitran対応表を使用: https://github.com/dmort27/epitran/blob/master/epitran/data/ipa-xsampa.csv 。ASCII音声記号とUnicode IPAを両側測定。声や話者感情の表現であって、顔文字ではない。
- Formal SignWriting in ASCII (FSW): 手話の位置/動き/顔/手などを座標付きASCII列で表現。MITのSignMaker READMEにある実在サンプル1列を測定: https://github.com/sutton-signwriting/signmaker 。全辞書は未測定。仕様文書は別ライセンスのCC BY 4.0: https://github.com/sutton-signwriting/formal-signwriting 。FSW/SWUという実装上の対応をUnicode標準の文字割当と混同しない。
- 2000年代携帯PUA: DoCoMo/KDDI/SoftBank/Googleの独自符号。Apache-2.0の歴史資料 https://github.com/google/emoji4unicode 。提案時のUnicode値は現在の標準値と断定せず、確定対応は別途 Unicode EmojiSources に分離。
- Wingdings/Webdings/Symbol/Wingdings 2/Wingdings 3: Unicode文字そのものではなくフォント選択と字位置の組。BSD-2-Clauseの公開対応表 https://github.com/mwilliamson/dingbat-to-unicode 。元字位置・Word式PUA・Unicode対応文字は別に測定。

## 新たに見つかった重要な候補（本表の全件実測には入れていない）

1. **Manuel de Codage (MdC, 1984)**: 古代エジプトのヒエログリフをGardiner符号とASCIIの配置演算子で書く。`A40`, `I3`、横配置 `*`、縦配置 `:`、区画 `-`、括弧。一次の説明: https://khety.qenherkhopeshef.org/HieroEncoding/MDC/mdc.html 。JSeshの対応: https://jseshdoc.qenherkhopeshef.org/en/jsesh/introduction 。Unicode単字一覧だけでは配置・合字を覆えない。JSeshソフトウェアのCeCILLと、フォントの制限付きライセンスは別物。フォント図形を一括再配布しない。コード文字列のデータセットを追加するなら許諾を確認する。
2. **Blissymbolics (1949〜)**: 意味を組み合わせる図形言語。BCIの2026 Authorized Vocabularyは6,551 symbolsと案内され、CC BY 4.0（BCI帰属表示必須）: https://blissymbolics.org/index.php/bci-av-2026 / https://blissymbolics.org/index.php/licensing 。Unicode提案の仮符号を確定した文字として扱わない。SVG/画像/数値IDのどれをtokenizeしているか明記すべき。図形のトークン数は通常のtiktokenでは測れず、ラベルやIDのコストとの混同に注意。
3. **楔形文字のATF・転写体系**: Unicodeの楔形単字とは別に、文字名・読み・破損・向き・行配置をASCII等で表す系統がある。ORACC ATFドキュメント候補: https://oracc.museum.upenn.edu/doc/help/editinginatf/ 。ここでは内容・ライセンスを未精査、データは未取得。
4. **音楽のテキスト記法**: ABC notation / LilyPond / MusicXML / Humdrum。音符のUnicode単字一覧は時間・声部・演奏指定を覆わない。ソフト本体の自由ライセンスと曲データの著作権は分ける。今回コーパス未取得。
5. **数式・論理のASCII記法**: TeX/LaTeX/AsciiMath/MathML/SMILES等は図形の別表現になりうる。``等の制御文字によるパックとは違い、ソーステキストとして実測する必要がある。今回はHTML named entities以外の体系全件を未取得。
6. **点字ASCII・6点/8点点字・モールス**: Unicode字形、印刷用ASCII変換、dot/hyphen表示、触覚/時間信号は別物。通常語への同義置換成功は未検証。
7. **古代/専門記号**: 錬金術・占星術・天文・地図・楽譜・速記（ティロ式等）・印刷校正・手旗/信号旗。Unicode blockにあるものでも、使用規則や組み合わせは別に必要。今回の既存特殊文字表と突き合わせて追加範囲を決めるのがよい。

## 全網羅の定義

顔文字・ASCIIアート・独自shortcode・符号帳・フォント依存PUAは、生成/追加できるため閉じた有限集合ではない。「列挙した公開ソースの取得版は全件通した」「未取得体系はこの台帳に明示した」の二段階で管理する。未取得の候補を実測済みとは報告しない。
