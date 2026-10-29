# 往復チェック強制時の影響（report-only、記録0件時点）

生成: `uv run python scripts/roundtrip.py --write-doc`（採点は o200k_base）。

## 往復チェック必須の nl 過去形（現在完了セル）

nl（1億人未満）の現在完了セル採用 62 件は `fixtures/roundtrip.json` の `required` に登録。強制は report-only。

| id | EN | 採用 | lt100m 強制時 |
|---|---|---|---|
| mx-take-perf-1s | I have taken | nam | ('nam', 'nl') -> ('nahm', 'de') |
| mx-think-perf-1s | I have thought | dacht | ('dacht', 'nl') -> ('dachte', 'de') |
| mx-say-perf-1s | I have said | zei | ('zei', 'nl') -> ('dije', 'es') |
| mx-go-perf-2 | you have gone | ging | ('ging', 'nl') -> ('foste', 'pt') |
| mx-come-perf-2 | you have come | kwam | ('kwam', 'nl') -> ('kamst', 'de') |
| mx-see-perf-2 | you have seen | zag | ('zag', 'nl') -> ('viste', 'es') |
| mx-take-perf-2 | you have taken | nam | ('nam', 'nl') -> ('nahmst', 'de') |
| mx-find-perf-2 | you have found | vond | ('vond', 'nl') -> ('achaste', 'pt') |
| mx-want-perf-2 | you have wanted | wilde | ('wilde', 'nl') -> ('quiseste', 'pt') |
| mx-think-perf-2 | you have thought | dacht | ('dacht', 'nl') -> ('dachtest', 'de') |
| mx-say-perf-2 | you have said | zei | ('zei', 'nl') -> ('dijiste', 'es') |
| mx-give-perf-2 | you have given | gaf | ('gaf', 'nl') -> ('deste', 'pt') |
| mx-take-perf-3s-he | he has taken | nam | ('nam', 'nl') -> ('nahm', 'de') |
| mx-think-perf-3s-he | he has thought | dacht | ('dacht', 'nl') -> ('dachte', 'de') |
| mx-say-perf-3s-he | he has said | zei | ('zei', 'nl') -> ('dijo', 'es') |
| mx-take-perf-3s-she | she has taken | nam | ('nam', 'nl') -> ('nahm', 'de') |
| mx-think-perf-3s-she | she has thought | dacht | ('dacht', 'nl') -> ('dachte', 'de') |
| mx-say-perf-3s-she | she has said | zei | ('zei', 'nl') -> ('dijo', 'es') |
| mx-take-perf-3s-it | it has taken | nam | ('nam', 'nl') -> ('nahm', 'de') |
| mx-think-perf-3s-it | it has thought | dacht | ('dacht', 'nl') -> ('dachte', 'de') |
| mx-say-perf-3s-it | it has said | zei | ('zei', 'nl') -> ('dijo', 'es') |
| mx-do-perf-1p | we have done | deden | ('deden', 'nl') -> ('taten', 'de') |
| mx-see-perf-1p | we have seen | zagen | ('zagen', 'nl') -> ('sahen', 'de') |
| mx-take-perf-1p | we have taken | namen | ('namen', 'nl') -> ('nahmen', 'de') |
| mx-want-perf-1p | we have wanted | wilden | ('wilden', 'nl') -> ('wollten', 'de') |
| mx-know-perf-1p | we have known | wisten | ('wisten', 'nl') -> ('supimos', 'es') |
| mx-do-perf-3p | they have done | deden | ('deden', 'nl') -> ('fizeram', 'pt') |
| mx-see-perf-3p | they have seen | zagen | ('zagen', 'nl') -> ('sahen', 'de') |
| mx-take-perf-3p | they have taken | namen | ('namen', 'nl') -> ('nahmen', 'de') |
| mx-want-perf-3p | they have wanted | wilden | ('wilden', 'nl') -> ('wollten', 'de') |
| mx-take-perf-dem-this | this has taken | this nam | ('this nam', 'nl') -> ('this nahm', 'de') |
| mx-think-perf-dem-this | this has thought | this dacht | ('this dacht', 'nl') -> ('this dachte', 'de') |
| mx-say-perf-dem-this | this has said | this zei | ('this zei', 'nl') -> ('this dijo', 'es') |
| mx-do-perf-dem-these | these have done | these deden | ('these deden', 'nl') -> ('these fizeram', 'pt') |
| mx-see-perf-dem-these | these have seen | these zagen | ('these zagen', 'nl') -> ('these sahen', 'de') |
| mx-take-perf-dem-these | these have taken | these namen | ('these namen', 'nl') -> ('these nahmen', 'de') |
| mx-want-perf-dem-these | these have wanted | these wilden | ('these wilden', 'nl') -> ('these wollten', 'de') |
| mx-do-perf-dem-those | those have done | those deden | ('those deden', 'nl') -> ('those fizeram', 'pt') |
| mx-see-perf-dem-those | those have seen | those zagen | ('those zagen', 'nl') -> ('those sahen', 'de') |
| mx-take-perf-dem-those | those have taken | those namen | ('those namen', 'nl') -> ('those nahmen', 'de') |
| mx-want-perf-dem-those | those have wanted | those wilden | ('those wilden', 'nl') -> ('those wollten', 'de') |
| mx-take-perf-rel-who-sg | who has taken | who nam | ('who nam', 'nl') -> ('who nahm', 'de') |
| mx-think-perf-rel-who-sg | who has thought | who dacht | ('who dacht', 'nl') -> ('who dachte', 'de') |
| mx-say-perf-rel-who-sg | who has said | who zei | ('who zei', 'nl') -> ('who dijo', 'es') |
| mx-do-perf-rel-who-pl | who have done | who deden | ('who deden', 'nl') -> None |
| mx-see-perf-rel-who-pl | who have seen | who zagen | ('who zagen', 'nl') -> None |
| mx-take-perf-rel-who-pl | who have taken | who namen | ('who namen', 'nl') -> None |
| mx-want-perf-rel-who-pl | who have wanted | who wilden | ('who wilden', 'nl') -> ('who wollten', 'de') |
| mx-take-perf-rel-which-sg | which has taken | which nam | ('which nam', 'nl') -> ('which nahm', 'de') |
| mx-think-perf-rel-which-sg | which has thought | which dacht | ('which dacht', 'nl') -> ('which dachte', 'de') |
| mx-say-perf-rel-which-sg | which has said | which zei | ('which zei', 'nl') -> ('which dijo', 'es') |
| mx-do-perf-rel-which-pl | which have done | which deden | ('which deden', 'nl') -> ('which fizeram', 'pt') |
| mx-see-perf-rel-which-pl | which have seen | which zagen | ('which zagen', 'nl') -> ('which sahen', 'de') |
| mx-take-perf-rel-which-pl | which have taken | which namen | ('which namen', 'nl') -> ('which nahmen', 'de') |
| mx-want-perf-rel-which-pl | which have wanted | which wilden | ('which wilden', 'nl') -> ('which wollten', 'de') |
| mx-take-perf-rel-que-sg | que has taken | que nam | ('que nam', 'nl') -> ('que nahm', 'de') |
| mx-think-perf-rel-que-sg | que has thought | que dacht | ('que dacht', 'nl') -> ('que dachte', 'de') |
| mx-say-perf-rel-que-sg | que has said | que zei | ('que zei', 'nl') -> ('que dijo', 'es') |
| mx-do-perf-rel-que-pl | que have done | que deden | ('que deden', 'nl') -> ('que fizeram', 'pt') |
| mx-see-perf-rel-que-pl | que have seen | que zagen | ('que zagen', 'nl') -> ('que sahen', 'de') |
| mx-take-perf-rel-que-pl | que have taken | que namen | ('que namen', 'nl') -> ('que nahmen', 'de') |
| mx-want-perf-rel-que-pl | que have wanted | que wilden | ('que wilden', 'nl') -> ('que wollten', 'de') |

## 全件（`--impact lt100m`、124件）

```
mx-come-past-2	you came	('kwam', 'nl')	->	('vins', 'fr')
mx-come-perf-2	you have come	('kwam', 'nl')	->	('kamst', 'de')
mx-come-pres-1p	we come	('komen', 'nl')	->	('kommen', 'de')
mx-come-pres-1s	I come	('kom', 'nl')	->	('komme', 'de')
mx-come-pres-2	you come	('komt', 'nl')	->	('venez', 'fr')
mx-do-perf-1p	we have done	('deden', 'nl')	->	('taten', 'de')
mx-do-perf-3p	they have done	('deden', 'nl')	->	('fizeram', 'pt')
mx-do-perf-dem-these	these have done	('these deden', 'nl')	->	('these fizeram', 'pt')
mx-do-perf-dem-those	those have done	('those deden', 'nl')	->	('those fizeram', 'pt')
mx-do-perf-rel-que-pl	que have done	('que deden', 'nl')	->	('que fizeram', 'pt')
mx-do-perf-rel-which-pl	which have done	('which deden', 'nl')	->	('which fizeram', 'pt')
mx-do-perf-rel-who-pl	who have done	('who deden', 'nl')	->	None
mx-find-fut-1p	we will find	('najdeme', 'cs')	->	('acharemos', 'pt')
mx-find-fut-3p	they will find	('najdou', 'cs')	->	('acharão', 'pt')
mx-find-fut-dem-these	these will find	('these najdou', 'cs')	->	('these acharão', 'pt')
mx-find-fut-dem-those	those will find	('those najdou', 'cs')	->	('those acharão', 'pt')
mx-find-past-2	you found	('vond', 'nl')	->	('achaste', 'pt')
mx-find-perf-2	you have found	('vond', 'nl')	->	('achaste', 'pt')
mx-give-fut-1p	we will give	('damy', 'pl')	->	('daremo', 'it')
mx-give-fut-2	you will give	('dasz', 'pl')	->	('darai', 'it')
mx-give-fut-3p	they will give	('dají', 'cs')	->	('darán', 'es')
mx-give-fut-dem-these	these will give	('these dají', 'cs')	->	('these darán', 'es')
mx-give-fut-dem-those	those will give	('those dají', 'cs')	->	('those darán', 'es')
mx-give-past-2	you gave	('gaf', 'nl')	->	('deste', 'pt')
mx-give-perf-2	you have given	('gaf', 'nl')	->	('deste', 'pt')
mx-go-past-2	you went	('ging', 'nl')	->	('allas', 'fr')
mx-go-perf-2	you have gone	('ging', 'nl')	->	('foste', 'pt')
mx-go-pres-1p	we go	('gaan', 'nl')	->	('gehen', 'de')
mx-know-perf-1p	we have known	('wisten', 'nl')	->	('supimos', 'es')
mx-know-pres-1p	we know	('weten', 'nl')	->	('savons', 'fr')
mx-say-past-2	you said	('zei', 'nl')	->	('dîtes', 'fr')
mx-say-perf-1s	I have said	('zei', 'nl')	->	('dije', 'es')
mx-say-perf-2	you have said	('zei', 'nl')	->	('dijiste', 'es')
mx-say-perf-3s-he	he has said	('zei', 'nl')	->	('dijo', 'es')
mx-say-perf-3s-it	it has said	('zei', 'nl')	->	('dijo', 'es')
mx-say-perf-3s-she	she has said	('zei', 'nl')	->	('dijo', 'es')
mx-say-perf-dem-this	this has said	('this zei', 'nl')	->	('this dijo', 'es')
mx-say-perf-rel-que-sg	que has said	('que zei', 'nl')	->	('que dijo', 'es')
mx-say-perf-rel-which-sg	which has said	('which zei', 'nl')	->	('which dijo', 'es')
mx-say-perf-rel-who-sg	who has said	('who zei', 'nl')	->	('who dijo', 'es')
mx-see-past-1p	we saw	('zagen', 'nl')	->	('sahen', 'de')
mx-see-past-3p	they saw	('zagen', 'nl')	->	('sahen', 'de')
mx-see-perf-1p	we have seen	('zagen', 'nl')	->	('sahen', 'de')
mx-see-perf-2	you have seen	('zag', 'nl')	->	('viste', 'es')
mx-see-perf-3p	they have seen	('zagen', 'nl')	->	('sahen', 'de')
mx-see-perf-dem-these	these have seen	('these zagen', 'nl')	->	('these sahen', 'de')
mx-see-perf-dem-those	those have seen	('those zagen', 'nl')	->	('those sahen', 'de')
mx-see-perf-rel-que-pl	que have seen	('que zagen', 'nl')	->	('que sahen', 'de')
mx-see-perf-rel-which-pl	which have seen	('which zagen', 'nl')	->	('which sahen', 'de')
mx-see-perf-rel-who-pl	who have seen	('who zagen', 'nl')	->	None
mx-see-pres-1p	we see	('zien', 'nl')	->	('sehen', 'de')
mx-take-fut-2	you will take	('vezmete', 'cs')	->	('tomarás', 'es')
mx-take-past-1p	we took	('namen', 'nl')	->	('nahmen', 'de')
mx-take-past-2	you took	('nam', 'nl')	->	('pris', 'fr')
mx-take-past-3p	they took	('namen', 'nl')	->	('nahmen', 'de')
mx-take-past-3s-he	he took	('nam', 'nl')	->	('nahm', 'de')
mx-take-past-3s-it	it took	('nam', 'nl')	->	('nahm', 'de')
mx-take-past-3s-she	she took	('nam', 'nl')	->	('nahm', 'de')
mx-take-perf-1p	we have taken	('namen', 'nl')	->	('nahmen', 'de')
mx-take-perf-1s	I have taken	('nam', 'nl')	->	('nahm', 'de')
mx-take-perf-2	you have taken	('nam', 'nl')	->	('nahmst', 'de')
mx-take-perf-3p	they have taken	('namen', 'nl')	->	('nahmen', 'de')
mx-take-perf-3s-he	he has taken	('nam', 'nl')	->	('nahm', 'de')
mx-take-perf-3s-it	it has taken	('nam', 'nl')	->	('nahm', 'de')
mx-take-perf-3s-she	she has taken	('nam', 'nl')	->	('nahm', 'de')
mx-take-perf-dem-these	these have taken	('these namen', 'nl')	->	('these nahmen', 'de')
mx-take-perf-dem-this	this has taken	('this nam', 'nl')	->	('this nahm', 'de')
mx-take-perf-dem-those	those have taken	('those namen', 'nl')	->	('those nahmen', 'de')
mx-take-perf-rel-que-pl	que have taken	('que namen', 'nl')	->	('que nahmen', 'de')
mx-take-perf-rel-que-sg	que has taken	('que nam', 'nl')	->	('que nahm', 'de')
mx-take-perf-rel-which-pl	which have taken	('which namen', 'nl')	->	('which nahmen', 'de')
mx-take-perf-rel-which-sg	which has taken	('which nam', 'nl')	->	('which nahm', 'de')
mx-take-perf-rel-who-pl	who have taken	('who namen', 'nl')	->	None
mx-take-perf-rel-who-sg	who has taken	('who nam', 'nl')	->	('who nahm', 'de')
mx-take-pres-1p	we take	('nemen', 'nl')	->	('nehmen', 'de')
mx-take-pres-2	you take	('neemt', 'nl')	->	('prends', 'fr')
mx-take-pres-3p	they take	('nemen', 'nl')	->	('toman', 'es')
mx-think-past-2	you thought	('dacht', 'nl')	->	('dachtest', 'de')
mx-think-past-3p	they thought	('dachten', 'de')	->	('pensaram', 'pt')
mx-think-past-3s-he	he thought	('dacht', 'nl')	->	('dachte', 'de')
mx-think-past-3s-it	it thought	('dacht', 'nl')	->	('dachte', 'de')
mx-think-past-3s-she	she thought	('dacht', 'nl')	->	('dachte', 'de')
mx-think-perf-1s	I have thought	('dacht', 'nl')	->	('dachte', 'de')
mx-think-perf-2	you have thought	('dacht', 'nl')	->	('dachtest', 'de')
mx-think-perf-3p	they have thought	('dachten', 'de')	->	('pensaram', 'pt')
mx-think-perf-3s-he	he has thought	('dacht', 'nl')	->	('dachte', 'de')
mx-think-perf-3s-it	it has thought	('dacht', 'nl')	->	('dachte', 'de')
mx-think-perf-3s-she	she has thought	('dacht', 'nl')	->	('dachte', 'de')
mx-think-perf-dem-these	these have thought	('these dachten', 'de')	->	('these pensaram', 'pt')
mx-think-perf-dem-this	this has thought	('this dacht', 'nl')	->	('this dachte', 'de')
mx-think-perf-dem-those	those have thought	('those dachten', 'de')	->	('those pensaram', 'pt')
mx-think-perf-rel-que-pl	que have thought	('que dachten', 'de')	->	('que pensaram', 'pt')
mx-think-perf-rel-que-sg	que has thought	('que dacht', 'nl')	->	('que dachte', 'de')
mx-think-perf-rel-which-pl	which have thought	('which dachten', 'de')	->	('which pensaram', 'pt')
mx-think-perf-rel-which-sg	which has thought	('which dacht', 'nl')	->	('which dachte', 'de')
mx-think-perf-rel-who-sg	who has thought	('who dacht', 'nl')	->	('who dachte', 'de')
mx-think-pres-1p	we think	('denken', 'de')	->	('pensamos', 'es')
mx-think-pres-2	you think	('denkt', 'nl')	->	('pensez', 'fr')
mx-think-pres-3p	they think	('denken', 'de')	->	('pensent', 'fr')
mx-think-pres-3s-he	he thinks	('denkt', 'de')	->	('pense', 'fr')
mx-think-pres-3s-it	it thinks	('denkt', 'de')	->	('pense', 'fr')
mx-think-pres-3s-she	she thinks	('denkt', 'de')	->	('pense', 'fr')
mx-think-pres-rel-que-sg	que thinks	('que denkt', 'de')	->	('que pense', 'fr')
mx-think-pres-rel-which-sg	which thinks	('which denkt', 'de')	->	('which pense', 'fr')
mx-think-pres-rel-who-sg	who thinks	('who denkt', 'de')	->	('who pense', 'fr')
mx-want-past-1p	we wanted	('wilden', 'nl')	->	('wollten', 'de')
mx-want-past-2	you wanted	('wilde', 'nl')	->	('voulus', 'fr')
mx-want-past-3p	they wanted	('wilden', 'nl')	->	('wollten', 'de')
mx-want-perf-1p	we have wanted	('wilden', 'nl')	->	('wollten', 'de')
mx-want-perf-2	you have wanted	('wilde', 'nl')	->	('quiseste', 'pt')
mx-want-perf-3p	they have wanted	('wilden', 'nl')	->	('wollten', 'de')
mx-want-perf-dem-these	these have wanted	('these wilden', 'nl')	->	('these wollten', 'de')
mx-want-perf-dem-those	those have wanted	('those wilden', 'nl')	->	('those wollten', 'de')
mx-want-perf-rel-que-pl	que have wanted	('que wilden', 'nl')	->	('que wollten', 'de')
mx-want-perf-rel-which-pl	which have wanted	('which wilden', 'nl')	->	('which wollten', 'de')
mx-want-perf-rel-who-pl	who have wanted	('who wilden', 'nl')	->	('who wollten', 'de')
mx-want-pres-1s	I want	('wil', 'nl')	->	('veux', 'fr')
mx-want-pres-2	you want	('wil', 'nl')	->	('veux', 'fr')
mx-want-pres-3s-he	he wants	('wil', 'nl')	->	('quer', 'pt')
mx-want-pres-3s-it	it wants	('wil', 'nl')	->	('quer', 'pt')
mx-want-pres-3s-she	she wants	('wil', 'nl')	->	('quer', 'pt')
mx-want-pres-rel-que-sg	que wants	('que wil', 'nl')	->	('que quer', 'pt')
mx-want-pres-rel-which-sg	which wants	('which wil', 'nl')	->	('which quer', 'pt')
mx-want-pres-rel-who-sg	who wants	('who wil', 'nl')	->	('who quer', 'pt')
```
