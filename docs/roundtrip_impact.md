# 往復チェック強制時の影響（report-only、記録0件時点）

生成: `uv run python scripts/roundtrip.py --write-doc`（採点は o200k_base）。

## 往復チェック必須の nl 過去形（現在完了セル）

nl（1億人未満）の現在完了セル採用 0 件は `fixtures/roundtrip.json` の `required` に登録。強制は report-only。

| id | EN | 採用 | lt100m 強制時 |
|---|---|---|---|

## 全件（`--impact lt100m`、22件）

```
mx-come-past-2	you came	None	->	('kamst', 'de')
mx-find-fut-1p	we will find	('najdeme', 'cs')	->	('acharemos', 'pt')
mx-find-fut-3p	they will find	('najdou', 'cs')	->	('acharão', 'pt')
mx-find-fut-dem-these	these will find	('these najdou', 'cs')	->	('these acharão', 'pt')
mx-find-fut-dem-those	those will find	('those najdou', 'cs')	->	('those acharão', 'pt')
mx-give-fut-1p	we will give	('damy', 'pl')	->	('daremo', 'it')
mx-give-fut-2	you will give	('dasz', 'pl')	->	('darai', 'it')
mx-give-fut-3p	they will give	('dají', 'cs')	->	('darán', 'es')
mx-give-fut-dem-these	these will give	('these dají', 'cs')	->	('these darán', 'es')
mx-give-fut-dem-those	those will give	('those dají', 'cs')	->	('those darán', 'es')
mx-go-fut-3s-it	it will go	None	->	('irá', 'es')
mx-go-fut-dem-this	this will go	None	->	('this irá', 'es')
mx-know-past-2	you knew	None	->	('sûtes', 'fr')
mx-know-past-3p	they knew	None	->	('surent', 'fr')
mx-know-perf-3p	they have known	None	->	('han sabido', 'es')
mx-know-pluperf-2	you had known	None	->	('souberas', 'pt')
mx-say-pres-rel-que-sg	que says	None	->	('que diz', 'pt')
mx-see-past-2	you saw	None	->	('viste', 'es')
mx-take-fut-2	you will take	('vezmete', 'cs')	->	('tomarás', 'es')
mx-take-past-2	you took	None	->	('nahmst', 'de')
mx-take-pres-2	you take	None	->	('prenez', 'fr')
mx-want-past-2	you wanted	None	->	('voleste', 'it')
```
