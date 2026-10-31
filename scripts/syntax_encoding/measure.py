"""Manual exploratory tokenizer measurement; importing never obtains encodings."""
import argparse
import re
import statistics as st

if __package__:
    from .cases import PV, SVC, SVOO, SVOC
else:
    from cases import PV, SVC, SVOO, SVOC


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', action='store_true', help='Explicitly run tokenization (may obtain encoding data)')
    args = parser.parse_args(argv)
    if not args.run:
        parser.error('measurement is manual only; pass --run explicitly')
    import tiktoken
    E = tiktoken.get_encoding('o200k_base')
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from ShorthandEdge.shorthand_edge import compress
    T=lambda s:len(E.encode(s)); B=lambda s:len(s.encode())
    def camel(a,b): return a+b[0].upper()+b[1:]
    # (subj, verb, particle/comp, rest)
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
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
