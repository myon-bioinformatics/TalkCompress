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
    T = lambda s: len(E.encode(s))
    B = lambda s: len(s.encode())
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
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
