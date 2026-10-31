import re,statistics as st
import tiktoken;E=tiktoken.get_encoding("o200k_base");T=lambda s:len(E.encode(s));B=lambda s:len(s.encode())
exec("SVOC="+open(__import__("os").path.join(__import__("os").path.dirname(__file__),"measure.py")).read().split("SVOC=")[1].split("\n")[0])
u=lambda x:x.replace(" ","_")
F={"原文":lambda s,v,o,c:f"{s} {v} {o} {c}.",
"make_him->happy":lambda s,v,o,c:f"{s} {v}_{u(o)}->{c}.",
"make_him_happy":lambda s,v,o,c:f"{s} {v}_{u(o)}_{c}.",
"make him->happy":lambda s,v,o,c:f"{s} {v} {o}->{c}.",
"make_happy him":lambda s,v,o,c:f"{s} {v}_{c} {o}.",
"makeHappy him":lambda s,v,o,c:f"{s} {v}{c[0].upper()+c[1:]} {o}.",
"make him=happy":lambda s,v,o,c:f"{s} {v} {o}={c}.",
"make him:happy":lambda s,v,o,c:f"{s} {v} {o}:{c}.",
}
b=None
for n,f in F.items():
  l=[f(*x) for x in SVOC];t=st.mean(map(T,l));by=st.mean(map(B,l))
  if b is None:b=(t,by)
  print(f"{n}\ttok {t-b[0]:+.2f}\tbyte {by-b[1]:+.2f}\t{l[1]}")
for w in ["keep_the_room_clean","keepClean","makeHappy","keep the room->clean"]:print(w,[E.decode([x]) for x in E.encode(" "+w)])
