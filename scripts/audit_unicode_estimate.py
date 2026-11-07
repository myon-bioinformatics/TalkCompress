"""Compare raw-text Unicode estimates with o200k; dev-only, no runtime dependency.

JSONL text rows and metadata strings are reported separately. Synthetic random
code points are stress data, not grammatical syllables or natural-language data.
"""
import sys,json,importlib.util,random,unicodedata,collections
from pathlib import Path
import argparse
ap=argparse.ArgumentParser()
ap.add_argument('--baseline',type=Path,required=True)
ap.add_argument('--output',type=Path,required=True)
args=ap.parse_args()
repo=Path(__file__).resolve().parents[1]
root=repo.parent
sys.path[:0]=[str(repo),str(repo/'shared')]
import tiktoken
enc=tiktoken.get_encoding('o200k_base')
def load(name,path):
 s=importlib.util.spec_from_file_location(name,path/'SentenceCalibratedMosaic/sentence_calibrated_mosaic.py'); m=importlib.util.module_from_spec(s);sys.modules[name]=m;s.loader.exec_module(m);return m
old=load('old',args.baseline);new=load('new',repo)
def metrics(xs):
 out={}
 for name,m in [('main',old),('pr',new)]:
  pairs=[(m.estimate_tokens(s),len(enc.encode(s,disallowed_special=()))) for s in xs];e=[a-b for a,b in pairs];out[name]={'n':len(e),'exact':sum(x==0 for x in e)/len(e),'mae':sum(map(abs,e))/len(e),'bias':sum(e)/len(e),'over':sum(x>0 for x in e),'under':sum(x<0 for x in e),'ratio':sum(a for a,b in pairs)/max(1,sum(b for a,b in pairs))}
 return out
sets=collections.defaultdict(list)
for p in sorted((repo/'tests/fixtures/corpus').rglob('*.jsonl')):
 for l in p.read_text().splitlines():
  d=json.loads(l);s=d.get('text');
  sets['all_jsonl_strings'].extend(v for v in d.values() if isinstance(v,str))
  if not isinstance(s,str):continue
  sets['corpus'].append(s)
  for name,lo,hi in [('bengali',0x980,0x9ff),('tamil',0xb80,0xbff),('deva',0x900,0x97f),('arabic',0x600,0x6ff),('hebrew',0x590,0x5ff)]:
   if any(lo<=ord(c)<=hi for c in s):sets[name].append(s)
r=random.Random(1203)
for name,chars in [('random_bn','কখগঘঙচছজঝঞটঠডঢণতথদধনপফবভমযরলশষসহািীুূেৈোৌ্'),('random_ta','கஙசஞடணதநபமயரலவழளறனாிீுூெேைொோௌ்'),('random_km_my','កខគឃងចឆជញដឋឌតថទនបផពមយរាលិីឹកខကခဂဃငစဆဇညတထဒနပဖဗမယရလဝါိီုူ')]:
 sets[name]=[''.join(r.choice(chars) for _ in range(r.randint(1,16))) for i in range(3000)]
base=['한국어','안녕하세요 세계','Tiếng Việt','café','क़','क्ष','क्\u200dष','क्\u200cष','שָׁלוֹם','مَرْحَبًا','☺️','❤️','葛\U000e0100城','\u1112\u119e\u11ab','\ua960\ud7b0','क्ॹ','க்ஷ','👨‍👩‍👧‍👦','']
rows=[]
for s in base:
 for form in ['NFC','NFD']:
  for template in ['{}','x {} y']:
   t=template.format(unicodedata.normalize(form,s));rows.append({'text':t,'form':form,'main':old.estimate_tokens(t),'pr':new.estimate_tokens(t),'actual':len(enc.encode(t))})
result={'tiktoken':tiktoken.__version__,'metrics':{k:metrics(v) for k,v in sets.items()},'boundaries':rows}
args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2));print(json.dumps(result['metrics'],indent=2))
