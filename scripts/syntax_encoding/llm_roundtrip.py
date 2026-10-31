import sys,re,json
import os;HERE=os.path.dirname(os.path.abspath(__file__))
src=open(os.path.join(HERE,"measure.py")).read()
exec("SVOC="+src.split("SVOC=")[1].split("\n")[0])
from llama_cpp import Llama
L=Llama(os.environ.get("SMOLLM_GGUF","m.gguf"),n_ctx=1024,verbose=False,seed=0)
F={"make happy(him)":lambda s,v,o,c:f"{s} {v} {c}({o}).",
"make(happy(him))":lambda s,v,o,c:f"{s} {v}({c}({o})).",
"make him:happy":lambda s,v,o,c:f"{s} {v} {o}:{c}.",
"make him=happy":lambda s,v,o,c:f"{s} {v} {o}={c}.",
"make_happy him":lambda s,v,o,c:f"{s} {v}_{c} {o}."}
SYS="Compressed English notation: 'V C(O)' or 'V(C(O))' or 'V O:C' or 'V O=C' or 'V_C O' all mean 'V O C' (e.g. 'I make happy(him).' = 'I make him happy.'). Rewrite the sentence as normal English. Output only the sentence."
norm=lambda x:re.sub(r"[^a-z ]","",x.lower()).split()
res={}
for n,f in F.items():
  ok=0;ex=[]
  for x in SVOC:
    gold=f"{x[0]} {x[1]} {x[2]} {x[3]}."
    r=L.create_chat_completion([{"role":"system","content":SYS},{"role":"user","content":f(*x)}],temperature=0,max_tokens=24)["choices"][0]["message"]["content"].strip().split("\n")[0]
    good=norm(r)==norm(gold);ok+=good
    if len(ex)<2:ex.append((f(*x),r))
  res[n]=ok;print(n,f"{ok}/{len(SVOC)}",ex,flush=True)
