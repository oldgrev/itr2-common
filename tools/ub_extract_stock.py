"""python ub_extract_stock.py <out.json> <editor dll>...

Stock UE 5.5 editor DLLs have no PDB: find member functions by the TArray::Add prologue pattern, simulate them,
locate the FMember by a stack slot that points at a UTF-16 identifier with a sane BaseType at +0x18, then chain
them through the returned prev-function pointers (same idea as the ITR1 ub_extract_exe.py)."""
import json, re, sys
from ub_extract_pdb import Image, simulate, read_field, FIELDS, BASETYPE
import capstone

NUM_LOAD = re.compile(rb"\x48\x63[\x78-\x7f]\x08|\x48\x63[\x40-\x47\x48-\x4f\x50-\x57\x58-\x5f\x68-\x6f\x70-\x77]\x08|\x4c\x63[\x40-\x7f]\x08")
IDENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


def parse(img, rva):
    mem, ret, calls = simulate(img, rva)
    for slot in sorted(k for k, v in mem.items() if isinstance(v, int)):
        p = read_field(mem, slot, 8)
        if not (isinstance(p, int) and p > 0x1000):
            continue
        nm = img.u16(p)
        if not nm or not IDENT.fullmatch(nm):
            continue
        bt = read_field(mem, slot + 0x18, 1)
        off = read_field(mem, slot + 0x14, 4)
        if not isinstance(bt, int) or not (0 < bt < 25) or not isinstance(off, int):
            continue
        f = {"name": nm}
        for name, d, size in FIELDS:
            f[name] = read_field(mem, slot + d, size)
        st = f["shader_type"]
        f["shader_type"] = (img.u16(st) or None) if isinstance(st, int) and st else None
        f["base_type"] = BASETYPE[bt]
        f["struct"] = "?" if f["struct"] is not None and f["struct"] != 0 else None
        f["prev"] = ret if isinstance(ret, int) else None
        f["rva"] = rva
        return f
    return None


def extract(path):
    img = Image(path)
    t = [s for s in img.pe.sections if s.Name.startswith(b".text")][0]
    text = img.data[t.PointerToRawData:t.PointerToRawData + t.SizeOfRawData]
    funcs, tried = {}, set()
    for m in NUM_LOAD.finditer(text):
        i = m.start()
        for p in range(i - (t.VirtualAddress + i) % 16, max(0, i - 0x200), -16):
            if text[p - 1] not in (0xCC, 0xC3):
                continue
            start = t.VirtualAddress + p
            if start in tried:
                break
            tried.add(start)
            f = parse(img, start)
            if f:
                funcs[start] = f
                break
    prevs = {f["prev"] for f in funcs.values() if f["prev"]}
    out = []
    for rva, f in funcs.items():
        if rva in prevs:
            continue
        chain, cur = [], rva
        while cur in funcs and len(chain) < 2000:
            chain.append(funcs[cur]); cur = funcs[cur]["prev"]
        out.append([{k: v for k, v in x.items() if k != "prev"} for x in reversed(chain)])
    return out


if __name__ == "__main__":
    res = {}
    for p in sys.argv[2:]:
        c = extract(p)
        print(p, len(c), "chains", sum(map(len, c)), "members", file=sys.stderr)
        res[p] = c
    json.dump(res, open(sys.argv[1], "w"), indent=0)
