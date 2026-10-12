"""In-place 4-byte fix for ITR2's CM rendering version (see map-making/guide.md, "The kludge").

The game's FRenderingObjectVersion has an extra CM entry at 49 that makes ULevel read 61 bytes of precomputed
visibility data stock 5.5.4 never writes. Stock stamps packages with 49, so we lower the package's rendering version
to 48: the game skips CM's branch, and nothing else in 5.5.4 is gated on 49. Same-size edit, so the UAT-built
container (mount point, header, offsets) is untouched. Needs an UNCOMPRESSED container, which build-itr2-map.ps1
makes by default.

    python patch_inplace.py <container.ucas>
"""
import struct, sys

# FRenderingObjectVersion::GUID = 12F88B9F-8875-4AFC-A67C-D90C383ABD29, serialized as 4 little-endian uint32
GUID = struct.pack("<4I", 0x12F88B9F, 0x88754AFC, 0xA67CD90C, 0x383ABD29)

path = sys.argv[1]
data = bytearray(open(path, "rb").read())
hits = [i for i in range(len(data)) if data.startswith(GUID, i)]
if len(hits) != 1:
    raise SystemExit(f"expected 1 FRenderingObjectVersion entry, found {len(hits)} (is the container compressed?)")
off = hits[0] + 16
ver, = struct.unpack_from("<i", data, off)
if ver == 48:
    print("already 48"); sys.exit(0)
if ver != 49:
    raise SystemExit(f"rendering version is {ver}, expected 49")
struct.pack_into("<i", data, off, 48)
open(path, "wb").write(data)
print(f"rendering version 49 -> 48 at 0x{off:x}")
