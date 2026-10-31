import statistics as st,tiktoken;E=tiktoken.get_encoding("o200k_base");T=lambda s:len(E.encode(s));B=lambda s:len(s.encode())
exec("SVOC="+open(__import__("os").path.join(__import__("os").path.dirname(__file__),"measure.py")).read().split("SVOC=")[1].split("\n")[0])
F={"原文":lambda s,v,o,c:f"{s} {v} {o} {c}.",
"make happy(him)":lambda s,v,o,c:f"{s} {v} {c}({o}).",
"make happy(him)_nospace_obj":lambda s,v,o,c:f"{s} {v} {c}({o.replace(' ','_')}).",
"make(happy(him))":lambda s,v,o,c:f"{s} {v}({c}({o})).",
"make him:happy":lambda s,v,o,c:f"{s} {v} {o}:{c}.",
"make him=happy":lambda s,v,o,c:f"{s} {v} {o}={c}.",
"make_happy him":lambda s,v,o,c:f"{s} {v}_{c} {o}.",
}
b=None;multi=[x for x in SVOC if " " in x[2]];single=[x for x in SVOC if " " not in x[2]]
print("n",len(SVOC),"multi",len(multi))
for n,f in F.items():
  r=[]
  for S in (SVOC,single,multi):
    l=[f(*x) for x in S];r.append((st.mean(map(T,l)),st.mean(map(B,l))))
  if b is None:b=r
  print(n,*[f"{r[i][0]-b[i][0]:+.2f}/{r[i][1]-b[i][1]:+.2f}" for i in range(3)],"|",[E.decode([t]) for t in E.encode(f(*SVOC[0]))],[E.decode([t]) for t in E.encode(f(*multi[0]))] if multi else "")
