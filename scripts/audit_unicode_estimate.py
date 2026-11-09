"""Compare raw-text Unicode estimates with o200k; dev-only, no runtime dependency.

JSONL text rows and metadata strings are reported separately. Synthetic random
code points are stress data, not grammatical syllables or natural-language data.
"""
import argparse, collections, importlib.util, json, random, sys, unicodedata
from pathlib import Path
repo=Path(__file__).resolve().parents[1]
root=repo.parent
sys.path[:0]=[str(repo),str(repo/'shared')]
BASE=['한국어','안녕하세요 세계','Tiếng Việt','café','क़','क्ष','क्‍ष','क्‌ष','שָׁלוֹם','مَرْحَبًا','☺️','❤️','葛\U000e0100城','ᄒᆞᆫ','ꥠힰ','क्ॹ','க்ஷ','👨‍👩‍👧‍👦','']
RANDOM_SETS=[('random_bn','কখগঘঙচছজঝঞটঠডঢণতথদধনপফবভমযরলশষসহািীুূেৈোৌ্'),('random_ta','கஙசஞடணதநபமயரலவழளறனாிீுூெேைொோௌ்'),('random_km_my','កខគឃងចឆជញដឋឌតថទនបផពមយរាលិីឹកខကခဂဃငစဆဇညတထဒနပဖဗမယရလဝါိီုူ')]
SCRIPTS=[('bengali',0x980,0x9ff),('tamil',0xb80,0xbff),('deva',0x900,0x97f),('arabic',0x600,0x6ff),('hebrew',0x590,0x5ff)]
def load(name,path):
 s=importlib.util.spec_from_file_location(name,path/'TesseraTalk/tessera_talk.py'); m=importlib.util.module_from_spec(s);sys.modules[name]=m;s.loader.exec_module(m);return m
def metrics(xs,enc,models):
 out={}
 for name,m in models:
  pairs=[(m.estimate_tokens(s),len(enc.encode(s,disallowed_special=()))) for s in xs];e=[a-b for a,b in pairs];out[name]={'n':len(e),'exact':sum(x==0 for x in e)/len(e),'mae':sum(map(abs,e))/len(e),'bias':sum(e)/len(e),'over':sum(x>0 for x in e),'under':sum(x<0 for x in e),'ratio':sum(a for a,b in pairs)/max(1,sum(b for a,b in pairs))}
 return out
def corpus_sets(seed=1203):
 sets=collections.defaultdict(list)
 for p in sorted((repo/'tests/fixtures/corpus').rglob('*.jsonl')):
  for l in p.read_text().splitlines():
   d=json.loads(l);s=d.get('text');
   sets['all_jsonl_strings'].extend(v for v in d.values() if isinstance(v,str))
   if not isinstance(s,str):continue
   sets['corpus'].append(s)
   for name,lo,hi in SCRIPTS:
    if any(lo<=ord(c)<=hi for c in s):sets[name].append(s)
 r=random.Random(seed)
 for name,chars in RANDOM_SETS:
  sets[name]=[''.join(r.choice(chars) for _ in range(r.randint(1,16))) for i in range(3000)]
 return sets
def boundaries(enc,old,new,base=BASE):
 rows=[]
 for s in base:
  for form in ['NFC','NFD']:
   for template in ['{}','x {} y']:
    t=template.format(unicodedata.normalize(form,s));rows.append({'text':t,'form':form,'main':old.estimate_tokens(t),'pr':new.estimate_tokens(t),'actual':len(enc.encode(t))})
 return rows
def audit(baseline,output=None):
 """Compare the baseline checkout's estimate_tokens with this repo's; writes JSON to ``output`` when given."""
 import tiktoken
 enc=tiktoken.get_encoding('o200k_base')
 old=load('old',Path(baseline));new=load('new',repo)
 result={'tiktoken':tiktoken.__version__,'metrics':{k:metrics(v,enc,[('main',old),('pr',new)]) for k,v in corpus_sets().items()},'boundaries':boundaries(enc,old,new)}
 if output is not None:Path(output).write_text(json.dumps(result,ensure_ascii=False,indent=2))
 return result
def main(argv=None):
 ap=argparse.ArgumentParser()
 ap.add_argument('--baseline',type=Path,required=True)
 ap.add_argument('--output',type=Path,required=True)
 args=ap.parse_args(argv)
 print(json.dumps(audit(args.baseline,args.output)['metrics'],indent=2))
if __name__=='__main__':
 raise SystemExit(main())
