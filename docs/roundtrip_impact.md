# 往復チェック強制時の影響（report-only、記録0件時点）

`uv run python scripts/roundtrip.py --impact lt100m` の出力。all スコープでは記録が無いため採用679件すべてが英語に戻る。

```
mx-come-pres-1s	I come	('kom', 'nl')	->	None
mx-come-pres-2	you come	('komt', 'nl')	->	('vens', 'pt')
mx-find-fut-1p	we will find	('najdeme', 'cs')	->	None
mx-find-fut-2	you will find	('najdeš', 'cs')	->	('acharás', 'pt')
mx-find-fut-3p	they will find	('najdou', 'cs')	->	('acharão', 'pt')
mx-find-fut-3s-he	he will find	('najde', 'cs')	->	('achará', 'pt')
mx-find-fut-3s-it	it will find	('najde', 'cs')	->	('achará', 'pt')
mx-find-fut-3s-she	she will find	('najde', 'cs')	->	('achará', 'pt')
mx-find-past-2	you found	('vond', 'nl')	->	('fandet', 'de')
mx-give-fut-1p	we will give	('damy', 'pl')	->	('daremo', 'it')
mx-give-fut-2	you will give	('dasz', 'pl')	->	('darai', 'it')
mx-give-fut-3p	they will give	('dají', 'cs')	->	('darán', 'es')
mx-give-fut-dem-these	these will give	('these dají', 'cs')	->	None
mx-give-fut-dem-those	those will give	('those dají', 'cs')	->	None
mx-give-past-2	you gave	('gaf', 'nl')	->	('gabt', 'de')
mx-go-past-2	you went	('ging', 'nl')	->	None
mx-go-pres-1p	we go	('gaan', 'nl')	->	('imos', 'pt')
mx-say-past-2	you said	('zei', 'nl')	->	None
mx-see-pres-1p	we see	('zien', 'nl')	->	None
mx-take-fut-1p	we will take	('vezmeme', 'cs')	->	None
mx-take-fut-2	you will take	('vezmeš', 'cs')	->	('tomarás', 'es')
mx-take-fut-3p	they will take	('wezmą', 'pl')	->	('tomarán', 'es')
mx-take-fut-3s-he	he will take	('vezme', 'cs')	->	('tomará', 'es')
mx-take-fut-3s-it	it will take	('vezme', 'cs')	->	('tomará', 'es')
mx-take-fut-3s-she	she will take	('vezme', 'cs')	->	('tomará', 'es')
mx-take-past-2	you took	('nam', 'nl')	->	('pris', 'fr')
mx-take-past-3s-he	he took	('nam', 'nl')	->	('nahm', 'de')
mx-take-past-3s-it	it took	('nam', 'nl')	->	('nahm', 'de')
mx-take-past-3s-she	she took	('nam', 'nl')	->	('nahm', 'de')
mx-think-past-1p	we thought	('dachten', 'de')	->	('pensamos', 'es')
mx-think-past-2	you thought	('dacht', 'nl')	->	('dachtet', 'de')
mx-think-past-3p	they thought	('dachten', 'de')	->	('pensaram', 'pt')
mx-think-past-3s-he	he thought	('dacht', 'nl')	->	('pensó', 'es')
mx-think-past-3s-it	it thought	('dacht', 'nl')	->	('pensó', 'es')
mx-think-past-3s-she	she thought	('dacht', 'nl')	->	('pensó', 'es')
mx-think-pres-1p	we think	('denken', 'de')	->	('pensons', 'fr')
mx-think-pres-2	you think	('denkt', 'de')	->	('pensi', 'it')
mx-think-pres-3p	they think	('denken', 'de')	->	('pensam', 'pt')
mx-think-pres-3s-he	he thinks	('denkt', 'de')	->	('pense', 'fr')
mx-think-pres-3s-it	it thinks	('denkt', 'de')	->	('pense', 'fr')
mx-think-pres-3s-she	she thinks	('denkt', 'de')	->	('pense', 'fr')
mx-want-past-1p	we wanted	('wilden', 'nl')	->	('volemmo', 'it')
mx-want-past-2	you wanted	('wilde', 'nl')	->	('voulus', 'fr')
mx-want-past-3p	they wanted	('wilden', 'nl')	->	('vollero', 'it')
mx-want-pres-1s	I want	('wil', 'nl')	->	('veux', 'fr')
mx-want-pres-2	you want	('wil', 'nl')	->	('veux', 'fr')
mx-want-pres-3s-he	he wants	('wil', 'nl')	->	('quer', 'pt')
mx-want-pres-3s-it	it wants	('wil', 'nl')	->	('quer', 'pt')
mx-want-pres-3s-she	she wants	('wil', 'nl')	->	('quer', 'pt')
mx-want-pres-rel-que-sg	que wants	('que wil', 'nl')	->	('que quer', 'pt')
mx-want-pres-rel-which-sg	which wants	('which wil', 'nl')	->	('which quer', 'pt')
mx-want-pres-rel-who-sg	who wants	('who wil', 'nl')	->	('who quer', 'pt')
```
