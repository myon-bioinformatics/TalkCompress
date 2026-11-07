# 往復チェック強制時の影響（report-only、記録0件時点）

生成: `uv run python scripts/roundtrip.py --write-doc`（採点は o200k_base）。

## 往復チェック必須の nl 過去形（現在完了セル）

nl（1億人未満）の現在完了セル採用 0 件は `fixtures/roundtrip.json` の `required` に登録。強制は report-only。

| id | EN | 採用 | lt100m 強制時 |
|---|---|---|---|

## 全件（`--impact lt100m`、10件）

```
mx-find-fut-1p	we will find	('najdeme', 'cs')	->	('acharemos', 'pt')
mx-find-fut-3p	they will find	('najdou', 'cs')	->	('acharão', 'pt')
mx-find-fut-dem-these	these will find	('these najdou', 'cs')	->	('these acharão', 'pt')
mx-find-fut-dem-those	those will find	('those najdou', 'cs')	->	('those acharão', 'pt')
mx-give-fut-1p	we will give	('damy', 'pl')	->	('daremo', 'it')
mx-give-fut-2	you will give	('dasz', 'pl')	->	('darai', 'it')
mx-give-fut-3p	they will give	('dají', 'cs')	->	('darán', 'es')
mx-give-fut-dem-these	these will give	('these dají', 'cs')	->	('these darán', 'es')
mx-give-fut-dem-those	those will give	('those dají', 'cs')	->	('those darán', 'es')
mx-take-fut-2	you will take	('vezmete', 'cs')	->	('tomarás', 'es')
```
