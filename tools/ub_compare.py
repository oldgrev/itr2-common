"""Match each game struct to the stock chain with the most member names in common, then diff members.
    python ub_compare.py <game.json> <stock.json> <diff out.json>"""
import json, sys
g = json.load(open(sys.argv[1]))
stock = json.load(open(sys.argv[2]))
chains = [(dll.split("/")[-1], c) for dll, cs in stock.items() for c in cs]
byname = {}
for i, (_, c) in enumerate(chains):
    for f in c:
        byname.setdefault(f["name"], set()).add(i)
KEYS = ["offset", "base_type", "rows", "cols", "elements", "shader_type", "precision"]
def sig(f):
    return tuple(f.get(k) for k in KEYS)
res = {}
for sname, s in g.items():
    names = [f["name"] for f in s["members"]]
    if not names:
        continue
    cand = set().union(*(byname.get(n, set()) for n in names))
    best, bs = None, 0
    for i in cand:
        cn = [f["name"] for f in chains[i][1]]
        sc = len(set(cn) & set(names)) / len(set(cn) | set(names))
        gm0 = {f["name"]: f for f in s["members"]}
        sc += 1e-4 * sum(1 for f in chains[i][1] if f["name"] in gm0 and sig(f) == sig(gm0[f["name"]])) / len(cn)
        if sc > bs:
            best, bs = i, sc
    if best is None or bs < 0.5:
        res[sname] = {"match": None, "score": bs}
        continue
    sm = {f["name"]: f for f in chains[best][1]}
    gm = {f["name"]: f for f in s["members"]}
    added = [n for n in names if n not in sm]
    removed = [n for n in sm if n not in gm]
    changed = [(n, sig(sm[n]), sig(gm[n])) for n in names if n in sm and sig(sm[n]) != sig(gm[n])]
    res[sname] = {"match": chains[best][0], "score": round(bs, 3), "stock_count": len(sm), "game_count": len(gm),
                  "added": added, "removed": removed, "changed": changed}
json.dump(res, open(sys.argv[3], "w"), indent=1)
same = [k for k, v in res.items() if v["match"] and not (v["added"] or v["removed"] or v["changed"])]
diff = [k for k, v in res.items() if v["match"] and (v["added"] or v["removed"] or v["changed"])]
nomatch = [k for k, v in res.items() if not v["match"]]
print("identical", len(same), "differ", len(diff), "unmatched", len(nomatch))
for k in sorted(diff):
    v = res[k]
    print("%s [%s] stock %d game %d +%d -%d ~%d" % (k, "UB:" + str(g[k].get("shader_variable")) if g[k].get("uniform_buffer") else "", v["stock_count"], v["game_count"], len(v["added"]), len(v["removed"]), len(v["changed"])))
