# コーパス出典とライセンス（ko/vi/th/id/tr/he/fa/sw/bn/ta、担当: GitHubヘルプ4bot）

`scripts/fetch_corpus_lowres.py` が生成する `tatoeba/<lang>.jsonl`（tier=short）と `flores200/<lang>.jsonl`（tier=medium/long）の出典です。リポジトリには tier ごと先頭 20 件のサンプルだけを置きます。全量は同スクリプトで `.cache/corpus/lowres/` に再生成します。形式・manifest は `docs/corpus.md` に従います。

## ライセンスと帰属表示

| category | 出典 | ライセンス | 帰属表示 |
|---|---|---|---|
| tatoeba | Tatoeba（OPUS-Tatoeba v2023-04-12 mono） | CC BY 2.0 FR | Tatoeba contributors。利用規約: https://tatoeba.org/en/terms_of_use 。OPUS: https://opus.nlpl.eu/Tatoeba/ （J. Tiedemann, "Parallel Data, Tools and Interfaces in OPUS", LREC 2012） |
| flores200 | FLORES-200 dev+devtest | CC BY-SA 4.0 | NLLB Team et al., "No Language Left Behind", 2022; Goyal et al., "The FLORES-101 Evaluation Benchmark", 2021。https://github.com/facebookresearch/flores/blob/main/flores200/README.md |

- tier=long は、同じ元記事 URL の連続文を半角空白 1 つで連結した改変物です。CC BY-SA 4.0 の継承条件に従います。
- fa と sw は、OPUS のファイルコード `pes`・`swh` を `fa`・`sw` として登録しています。元のコードは各行と manifest の `source` に書いています。
- NC・ND のデータは含みません。

## 取得元（sha256 固定）

| lang | 取得元 URL | sha256 |
|---|---|---|
| ko（Tatoeba, ko） | https://object.pouta.csc.fi/OPUS-Tatoeba/v2023-04-12/mono/ko.txt.gz | `72e21497f261ba7d174dfa4f191410e95fb3ec0b9f219c643672eace6df5f310` |
| vi（Tatoeba, vi） | https://object.pouta.csc.fi/OPUS-Tatoeba/v2023-04-12/mono/vi.txt.gz | `3c4188d7d83870d9b684ed7d67c2c4381a2332e52021b05f3c11915f58e1f590` |
| th（Tatoeba, th） | https://object.pouta.csc.fi/OPUS-Tatoeba/v2023-04-12/mono/th.txt.gz | `874e4df516f2b14f6614b5aabff197778b0838f93ac5733d35b49565bdb2b174` |
| id（Tatoeba, id） | https://object.pouta.csc.fi/OPUS-Tatoeba/v2023-04-12/mono/id.txt.gz | `3e4f08eb043e95648cbe56d595a0ead3a4f351eb1414262bb0ccd07b073aca83` |
| tr（Tatoeba, tr） | https://object.pouta.csc.fi/OPUS-Tatoeba/v2023-04-12/mono/tr.txt.gz | `61b2b4bb62f442f4af13111b1a897e6cd14bf20c713bf0692adfe5ea92ed96a2` |
| he（Tatoeba, he） | https://object.pouta.csc.fi/OPUS-Tatoeba/v2023-04-12/mono/he.txt.gz | `1934d66e4450358cad385ecb5a0583113120b14cd89e97348875dd7aa5713083` |
| fa（Tatoeba, pes） | https://object.pouta.csc.fi/OPUS-Tatoeba/v2023-04-12/mono/pes.txt.gz | `f0159d67e05802efde95ffe3c4f1ec6c8b7fe6816dab2fc9a3a589d92561f052` |
| sw（Tatoeba, swh） | https://object.pouta.csc.fi/OPUS-Tatoeba/v2023-04-12/mono/swh.txt.gz | `a922ba70a73015b68c5f2447f609040ea8b7492e05bc6e0337391b580ec87bda` |
| bn（Tatoeba, bn） | https://object.pouta.csc.fi/OPUS-Tatoeba/v2023-04-12/mono/bn.txt.gz | `816f6d8d4d8f55304135385f0a23bf3494ee6972e80e34f76712bd236be60c95` |
| ta（Tatoeba, ta） | https://object.pouta.csc.fi/OPUS-Tatoeba/v2023-04-12/mono/ta.txt.gz | `9bea4291a732f89c1cb0c4269da590d4c5764ec7dd36f20583042c953b94cb5d` |
| 全 10 言語（FLORES-200） | https://dl.fbaipublicfiles.com/nllb/flores200_dataset.tar.gz | `b8b0b76783024b85797e5cc75064eb83fc5288b41e9654dabc7be6ae944011f6` |

FLORES-200 の tar 内で使うファイル: `flores200_dataset/{dev,devtest}/<code>.{dev,devtest}` と `flores200_dataset/metadata_{dev,devtest}.tsv`。コード: ko=kor_Hang, vi=vie_Latn, th=tha_Thai, id=ind_Latn, tr=tur_Latn, he=heb_Hebr, fa=pes_Arab, sw=swh_Latn, bn=ben_Beng, ta=tam_Taml。
