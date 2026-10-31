import sys,re,statistics as st
sys.path[:0]=[".","shared","ShorthandEdge"]
import tiktoken; from shorthand_edge import compress
E=tiktoken.get_encoding("o200k_base")
T=lambda s:len(E.encode(s)); B=lambda s:len(s.encode())
def camel(a,b): return a+b[0].upper()+b[1:]
# (subj, verb, particle/comp, rest)
PV=[("I","look","up","the word"),("She","turn","off","the light"),("We","set","up","the server"),("They","give","up","the plan"),("He","pick","up","the kids"),("You","figure","out","the bug"),("I","put","off","the meeting"),("She","carry","out","the test"),("We","fill","in","the form"),("They","break","down","the task"),("He","shut","down","the app"),("I","look","after","my cat"),("You","run","into","an error"),("We","come","across","a paper"),("They","point","out","the flaw")]
SVC=[("I","become","happy"),("She","feel","tired"),("It","get","dark"),("He","look","busy"),("We","stay","calm"),("They","seem","ready"),("It","turn","cold"),("You","sound","sure"),("The data","look","clean"),("The test","become","slow"),("She","grow","old"),("It","go","bad")]
SVOO=[("I","give","him","a book"),("She","send","me","an email"),("We","show","them","the result"),("He","tell","us","the truth"),("They","buy","her","a gift"),("You","lend","me","a pen"),("I","teach","them","Python"),("She","ask","him","a question"),("We","offer","you","a job"),("He","pass","me","the salt"),("They","bring","us","coffee"),("I","hand","her","the key")]
SVOC=[("I","make","him","happy"),("She","keep","the room","clean"),("We","call","him","Bob"),("They","find","it","useful"),("He","leave","the door","open"),("You","paint","the wall","red"),("I","consider","her","smart"),("She","make","me","angry"),("We","keep","it","simple"),("They","name","the cat","Max"),("He","get","the job","done"),("I","set","the bird","free")]
art=lambda x:re.sub(r"^(a|an|the) ","",x)
rows={}
def add(k,s): rows.setdefault(k,[]).append((T(s),B(s)))
for s,v,p,o in PV:
  add(("句動詞","原文"),f"{s} {v} {p} {o}.")
  add(("句動詞","現行TC"),compress(f"{s} {v} {p} {o}."))
  for n,f in [("_",f"{v}_{p}"),("-",f"{v}-{p}"),("camel",camel(v,p))]: add(("句動詞",n),f"{s} {f} {o}.")
for s,v,c in SVC:
  add(("SVC","原文"),f"{s} {v} {c}."); add(("SVC","現行TC"),compress(f"{s} {v} {c}."))
  for n,f in [("_",f"{v}_{c}"),("-",f"{v}-{c}"),("camel",camel(v,c))]: add(("SVC",n),f"{s} {f}.")
for s,v,i,d in SVOO:
  add(("SVOO","原文"),f"{s} {v} {i} {d}."); add(("SVOO","現行TC"),compress(f"{s} {v} {i} {d}."))
  add(("SVOO","f(i, d)"),f"{s} {v}({i}, {art(d)})."); add(("SVOO","f(i,d)"),f"{s} {v}({i},{art(d)}).")
for s,v,o,c in SVOC:
  add(("SVOC","原文"),f"{s} {v} {o} {c}."); add(("SVOC","現行TC"),compress(f"{s} {v} {o} {c}."))
  add(("SVOC","f(o→c)"),f"{s} {v}({o}→{c})."); add(("SVOC","f(o->c)"),f"{s} {v}({o}->{c}).")
  add(("SVOC","v_c o"),f"{s} {v}_{c} {o}.")
base={}
for (g,n),l in rows.items():
  t=st.mean(x for x,_ in l); b=st.mean(y for _,y in l)
  if n=="原文": base[g]=(t,b)
  bt,bb=base[g]; print(f"{g}\t{n}\tn={len(l)}\ttok={t:.2f}({t-bt:+.2f})\tbyte={b:.2f}({b-bb:+.2f})")
print(compress("I look up the word."),"|",compress("I give him a book."))
for w in ["look_up","look-up","lookUp","make_happy","→","->","give(him, book)"]: print(w,[E.decode([x]) for x in E.encode(" "+w)])
