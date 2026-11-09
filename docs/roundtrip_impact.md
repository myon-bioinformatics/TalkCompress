# 往復チェック強制時の影響（report-only）

生成: `uv run python scripts/roundtrip.py --write-doc`（採点は o200k_base）。

## 往復チェック必須の nl 過去形（現在完了セル）

nl（1億人未満）の現在完了セル採用 0 件は `fixtures/roundtrip.json` の `required` に登録。強制は report-only。

| id | EN | 採用 | lt100m 強制時 |
|---|---|---|---|

## 全件（`--impact lt100m`、39件）

```
mx-come-fut-3s-it	it will come	None	->	('verrà', 'it')
mx-come-fut-dem-this	this will come	('this virá', 'pt')	->	('this verrà', 'it')
mx-come-past-2	you came	None	->	('kamst', 'de')
mx-do-perf-3p	they have done	None	->	('hicieron', 'es')
mx-do-perf-dem-these	these have done	None	->	('these hicieron', 'es')
mx-do-perf-dem-those	those have done	None	->	('those hicieron', 'es')
mx-do-perf-rel-que-pl	que have done	None	->	('que hicieron', 'es')
mx-do-perf-rel-which-pl	which have done	None	->	('which hicieron', 'es')
mx-give-perf-1s	I have given	None	->	('ai donné', 'fr')
mx-give-perf-rel-que-pl	que have given	None	->	('que dieron', 'es')
mx-give-perf-rel-que-sg	que has given	None	->	('que dio', 'es')
mx-give-perf-rel-which-pl	which have given	None	->	('which dieron', 'es')
mx-give-perf-rel-which-sg	which has given	None	->	('which dio', 'es')
mx-give-perf-rel-who-pl	who have given	None	->	('who dieron', 'es')
mx-give-perf-rel-who-sg	who has given	None	->	('who dio', 'es')
mx-go-fut-3s-it	it will go	None	->	('irá', 'es')
mx-go-fut-dem-this	this will go	None	->	('this irá', 'es')
mx-go-past-3s-it	it went	None	->	('alla', 'fr')
mx-go-perf-2	you have gone	None	->	('fostes', 'pt')
mx-go-perf-3s-he	he has gone	None	->	('ging', 'de')
mx-go-perf-3s-it	it has gone	None	->	('ging', 'de')
mx-go-perf-3s-she	she has gone	None	->	('ging', 'de')
mx-go-perf-dem-this	this has gone	None	->	('this ging', 'de')
mx-go-perf-rel-que-pl	que have gone	None	->	('que fueron', 'es')
mx-go-perf-rel-que-sg	que has gone	None	->	('que fue', 'es')
mx-go-perf-rel-which-pl	which have gone	None	->	('which fueron', 'es')
mx-go-perf-rel-which-sg	which has gone	None	->	('which fue', 'es')
mx-go-perf-rel-who-pl	who have gone	None	->	('who fueron', 'es')
mx-go-perf-rel-who-sg	who has gone	None	->	('who fue', 'es')
mx-know-past-2	you knew	None	->	('sûtes', 'fr')
mx-know-past-3p	they knew	None	->	('surent', 'fr')
mx-know-perf-3p	they have known	None	->	('han sabido', 'es')
mx-know-pluperf-2	you had known	None	->	('souberas', 'pt')
mx-say-pres-rel-que-sg	que says	None	->	('que diz', 'pt')
mx-see-past-2	you saw	None	->	('viste', 'pt')
mx-see-pluperf-3p	they had seen	None	->	('avaient vu', 'fr')
mx-take-past-2	you took	None	->	('nahmst', 'de')
mx-take-pres-2	you take	None	->	('prenez', 'fr')
mx-want-past-2	you wanted	None	->	('voleste', 'it')
```
