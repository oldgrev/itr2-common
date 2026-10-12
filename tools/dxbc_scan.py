"""Pull DXBC blobs out of an uncompressed legacy .ushaderbytecode (retoc to-legacy --no-compres-shaders).

    python dxbc_scan.py <archive.ushaderbytecode> <outdir> [--limit N] [--blobs]

Scans for the DXBC container magic and uses the container's own size field (offset 24), so it doesn't need the
FSerializedShaderArchive header. Writes <outdir>/index.tsv (n, file offset, size, shader-type from SHEX/SHDR,
bytes of trailing UE optional data as printable strings) and (with --blobs) blobs/<n>.dxbc.
"""
import mmap
import os
import re
import struct
import sys

PROG = {0: "PS", 1: "VS", 2: "GS", 3: "HS", 4: "DS", 5: "CS"}


def blobs(mm):
    pos = 0
    while True:
        i = mm.find(b"DXBC", pos)
        if i < 0:
            return
        size, nchunks = struct.unpack_from("<II", mm, i + 24)
        if 32 < size < 64 << 20 and nchunks < 32:
            yield i, size
            pos = i + size
        else:
            pos = i + 4


def prog_type(blob):
    n = struct.unpack_from("<I", blob, 28)[0]
    for k in range(n):
        off = struct.unpack_from("<I", blob, 32 + 4 * k)[0]
        tag = blob[off:off + 4]
        if tag in (b"SHEX", b"SHDR"):
            ver = struct.unpack_from("<I", blob, off + 8)[0]
            return PROG.get(ver >> 16, "?%d" % (ver >> 16))
    return "?"


if __name__ == "__main__":
    src, out = sys.argv[1], sys.argv[2]
    limit = int(sys.argv[sys.argv.index("--limit") + 1]) if "--limit" in sys.argv else 1 << 30
    os.makedirs(os.path.join(out, "blobs"), exist_ok=True)
    with open(src, "rb") as f, open(os.path.join(out, "index.tsv"), "w") as idx:
        mm = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)
        n = 0
        for i, size in blobs(mm):
            blob = mm[i:i + size]
            tail = mm[i + size:i + size + 512]
            tail = tail.split(b"DXBC")[0]
            strs = [s.decode() for s in re.findall(rb"[A-Za-z_][A-Za-z0-9_]{3,}", tail)][:24]
            idx.write("%d\t%d\t%d\t%s\t%s\n" % (n, i, size, prog_type(blob), ",".join(strs)))
            if "--blobs" in sys.argv:
                open(os.path.join(out, "blobs", "%d.dxbc" % n), "wb").write(blob)
            n += 1
            if n >= limit:
                break
        print("blobs:", n)
