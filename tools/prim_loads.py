"""Disassemble shaders from a legacy .ushaderbytecode (offsets from dxbc_scan.py's index.tsv) and report how they
index GPUScene primitive data.

    python prim_loads.py <archive> <index.tsv> <n>[,<n>...] [--asm OUTDIR]
    python prim_loads.py <archive> <index.tsv> --survey [--filter REGEX] [--max N]

For each shader: prints every integer literal multiplied into a structured-buffer index (imul/umad/imad with an
immediate), and every ld_structured with the buffer register and the literal added to the index.
--survey: histogram of those multiply literals over many shaders.
"""
import collections
import ctypes
import mmap
import os
import re
import sys

_d3d = ctypes.WinDLL("d3dcompiler_47.dll")


def disasm(dxbc):
    blob = ctypes.c_void_p()
    hr = _d3d.D3DDisassemble(ctypes.c_char_p(dxbc), ctypes.c_size_t(len(dxbc)), 0, None, ctypes.byref(blob))
    if hr != 0:
        return "D3DDisassemble failed %08x" % (hr & 0xFFFFFFFF)
    vt = ctypes.cast(blob, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
    get_ptr = ctypes.WINFUNCTYPE(ctypes.c_void_p, ctypes.c_void_p)(vt[3])
    get_size = ctypes.WINFUNCTYPE(ctypes.c_size_t, ctypes.c_void_p)(vt[4])
    release = ctypes.WINFUNCTYPE(ctypes.c_ulong, ctypes.c_void_p)(vt[2])
    text = ctypes.string_at(get_ptr(blob), get_size(blob)).decode("latin1")
    release(blob)
    return text


def load_index(path):
    rows = {}
    for line in open(path):
        n, off, size, kind, ubs = (line.rstrip("\n").split("\t") + [""])[:5]
        rows[int(n)] = (int(off), int(size), kind, ubs)
    return rows


MUL = re.compile(r"\b(imul null, |umad |imad |ishl )(r\d+\.\w+), (\S+), (\S+)(?:, (\S+))?")
LIT = re.compile(r"^l\((-?\d+)\)$")


def mul_literals(text):
    out = []
    for line in text.splitlines():
        m = MUL.search(line)
        if not m:
            continue
        for a in (m.group(3), m.group(4)):
            lm = LIT.match(a.rstrip(","))
            if lm:
                out.append((m.group(1).strip(), int(lm.group(1)), line.strip()))
    return out


if __name__ == "__main__":
    arc, idxp = sys.argv[1], sys.argv[2]
    rows = load_index(idxp)
    f = open(arc, "rb")
    mm = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)
    if "--survey" in sys.argv:
        flt = re.compile(sys.argv[sys.argv.index("--filter") + 1]) if "--filter" in sys.argv else None
        mx = int(sys.argv[sys.argv.index("--max") + 1]) if "--max" in sys.argv else 1000
        hist = collections.Counter()
        seen = 0
        for n, (off, size, kind, ubs) in sorted(rows.items()):
            if flt and not flt.search(kind + " " + ubs):
                continue
            text = disasm(mm[off:off + size])
            lits = {(op, v) for op, v, _ in mul_literals(text) if op != "ishl"}
            for k in lits:
                hist[k] += 1
            seen += 1
            if seen >= mx:
                break
        print("shaders:", seen)
        for (op, v), c in hist.most_common(30):
            print("%6d  %s %d" % (c, op, v))
        sys.exit(0)
    out = sys.argv[sys.argv.index("--asm") + 1] if "--asm" in sys.argv else None
    for n in [int(x) for x in sys.argv[3].split(",")]:
        off, size, kind, ubs = rows[n]
        text = disasm(mm[off:off + size])
        print("=== #%d %s %d bytes ubs=%s" % (n, kind, size, ubs))
        if out:
            os.makedirs(out, exist_ok=True)
            open(os.path.join(out, "%d_%s.asm" % (n, kind)), "w").write(text)
        for line in text.splitlines():
            if re.search(r"dcl_resource_structured|dcl_constantbuffer|ld_structured|imul|umad|imad", line):
                print("   ", line.strip())
