"""Which instance-transform encoding do the GPUScene vertex shaders in an archive decode?

    python xform_check.py <archive> <index.tsv> [--every K]

compressed   = PLATFORM_ALLOW_SCENE_DATA_COMPRESSED_TRANSFORMS 1 (DecodeTransform: uint4 rotation/scale, 2 float4s)
uncompressed = 0 (3 float4 rows loaded at InstanceId + {1,2,3}*SOAStride). ITR2's game shaders are all uncompressed.
"""
import mmap
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from prim_loads import disasm, load_index  # noqa: E402

if __name__ == "__main__":
    every = int(sys.argv[sys.argv.index("--every") + 1]) if "--every" in sys.argv else 1
    rows = load_index(sys.argv[2])
    f = open(sys.argv[1], "rb")
    mm = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)
    c = {"compressed": 0, "uncompressed": 0, "neither": 0}
    n = 0
    for k, (off, size, kind, ubs) in sorted(rows.items()):
        if kind != "VS" or "Scene" not in ubs.split(","):
            continue
        n += 1
        if n % every:
            continue
        t = disasm(mm[off:off + size])
        if "-32768.000000, -32768.000000, 0.000000, -16384.000000" in t:
            c["compressed"] += 1
        elif "l(3), cb" in t:
            c["uncompressed"] += 1
        else:
            c["neither"] += 1
    print("GPUScene VS:", n, "sampled:", c)
