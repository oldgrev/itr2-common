"""Recover every shader parameter / uniform buffer struct layout from a UE 5.x shipping exe + its PDB.

Uses the PDB (via the DIA SDK, msdia140.dll, through comtypes) to find every generated member function
`Struct::zzAppendMemberGetPrev(zzNextMemberId<Member>, TArray<FMember>*)` (public symbols), so struct and member
names come from the symbol, not from guessing. Each function is then simulated with capstone (same idea as the ITR1
tool ub_extract_exe.py) to read the FMember it builds on the stack. UE 5.5 FMember (read from the PDB):
Name +0, ShaderType +8, FileLine +0x10, Offset +0x14, BaseType +0x18 (u8), Precision +0x19 (u8), NumRows +0x1c,
NumColumns +0x20, NumElements +0x24, Struct +0x28.
Struct sizes come from the PDB UDT records; shader variable names (for IMPLEMENT_*_UNIFORM_BUFFER_STRUCT) from the
string arguments in `Struct::GetStructMetadata()`.

    python ub_extract_pdb.py <exe> --dump out.json
"""
import os
import json
import re
import sys
import time

import capstone
import comtypes.client
import pefile

# msdia140.dll from Visual Studio's DIA SDK. Set DIA_DLL if yours is somewhere else (Professional, Build Tools...).
DIA = os.environ.get("DIA_DLL", r"C:\Program Files\Microsoft Visual Studio\2022\Community\DIA SDK\bin\amd64\msdia140.dll")
# The game exe. Set ITR2_EXE if your game isn't in the default Steam library.
EXE = os.environ.get("ITR2_EXE", r"C:\Program Files (x86)\Steam\steamapps\common\IntoTheRadius2\IntoTheRadius2\Binaries\Win64\IntoTheRadius2-Win64-Shipping.exe")
BASETYPE = ["INVALID", "BOOL", "INT32", "UINT32", "FLOAT32", "TEXTURE", "SRV", "UAV", "SAMPLER", "RDG_TEXTURE",
            "RDG_TEXTURE_ACCESS", "RDG_TEXTURE_ACCESS_ARRAY", "RDG_TEXTURE_SRV", "RDG_TEXTURE_NON_PIXEL_SRV",
            "RDG_TEXTURE_UAV", "RDG_BUFFER_ACCESS", "RDG_BUFFER_ACCESS_ARRAY", "RDG_BUFFER_SRV", "RDG_BUFFER_UAV",
            "RDG_UNIFORM_BUFFER", "NESTED_STRUCT", "INCLUDED_STRUCT", "REFERENCED_STRUCT",
            "RENDER_TARGET_BINDING_SLOTS", "RESOURCE_COLLECTION"]
FIELDS = [("shader_type", 8, 8), ("file_line", 0x10, 4), ("offset", 0x14, 4), ("base_type", 0x18, 1),
          ("precision", 0x19, 1), ("rows", 0x1c, 4), ("cols", 0x20, 4), ("elements", 0x24, 4), ("struct", 0x28, 8)]
SymTagUDT, SymTagPublic = 11, 10
MEMBER_UNDEC = re.compile(r"__cdecl (.+)::zzAppendMemberGetPrev\(struct .*::zzNextMemberId(\w+),")
MEMBER_SYM = re.compile(r"^\?zzAppendMemberGetPrev@(.+?)@@CAPEAXUzzNextMemberId(\w+?)@")


def demangle_scope(s):
    """'FParameters@FFooCS' -> 'FFooCS::FParameters' (simple scopes only)."""
    return "::".join(reversed(s.split("@")))


def dia_iter(e):
    while True:
        r = e.Next(1)
        x, n = r if isinstance(r, tuple) else (r, 1)
        if not n:
            break
        yield x


class Image:
    def __init__(self, path):
        self.pe = pefile.PE(path, fast_load=True)
        self.data = open(path, "rb").read()
        self.md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64)
        self.md.detail = True

    def off(self, rva):
        for s in self.pe.sections:
            if s.VirtualAddress <= rva < s.VirtualAddress + max(s.Misc_VirtualSize, s.SizeOfRawData):
                o = rva - s.VirtualAddress
                return s.PointerToRawData + o if o < s.SizeOfRawData else None
        return None

    def u16(self, rva):
        o = self.off(rva)
        if o is None:
            return None
        e = o
        while e < len(self.data) - 1 and self.data[e:e + 2] != b"\0\0":
            e += 2
            if e - o > 600:
                return None
        try:
            s = self.data[o:e].decode("utf-16-le")
        except UnicodeDecodeError:
            return None
        return s if s.isprintable() else None

    def cstr(self, rva):
        o = self.off(rva)
        if o is None:
            return None
        e = self.data.find(bytes(1), o, o + 400)
        try:
            return self.data[o:e].decode("ascii")
        except UnicodeDecodeError:
            return None

    def code(self, rva, n):
        o = self.off(rva)
        return self.data[o:o + n]


def full_reg(r):
    if r is None:
        return None
    if r.startswith("e") and len(r) == 3:
        return "r" + r[1:]
    m = re.fullmatch(r"(r\d+)[dwb]", r)
    return m.group(1) if m else r


def simulate(img, rva):
    """Simulate a member function. Returns (stack byte map, returned value, call targets)."""
    X = capstone.x86
    regs, mem, frame, calls = {}, {}, {"rsp": 0}, []
    ret = None
    for n, ins in enumerate(img.md.disasm(img.code(rva, 0x400), rva)):
        if n > 150:
            break
        m, ops = ins.mnemonic, ins.operands
        if m == "ret":
            ret = regs.get("rax")
            break
        if m == "jmp":
            break
        if m == "push":
            frame["rsp"] -= 8
            continue
        if m == "sub" and ops[0].type == X.X86_OP_REG and ins.reg_name(ops[0].reg) == "rsp":
            frame["rsp"] -= ops[1].imm
            continue
        if m == "add" and ops[0].type == X.X86_OP_REG and ins.reg_name(ops[0].reg) == "rsp":
            continue
        if m == "mov" and ops[0].type == X.X86_OP_REG and ops[1].type == X.X86_OP_REG and ins.reg_name(ops[1].reg) == "rsp":
            frame[ins.reg_name(ops[0].reg)] = frame["rsp"]
            continue
        if m == "call":
            tgt = ops[0].imm if ops[0].type == X.X86_OP_IMM else None
            calls.append(tgt)
            regs["rax"] = ("call", tgt)
            continue
        dst = full_reg(ins.reg_name(ops[0].reg)) if ops and ops[0].type == X.X86_OP_REG else None
        if m == "lea" and dst and ops[1].type == X.X86_OP_MEM and ops[1].mem.index == 0 and ops[1].mem.base                 and ins.reg_name(ops[1].mem.base) in frame:
            frame[dst] = frame[ins.reg_name(ops[1].mem.base)] + ops[1].mem.disp
            regs.pop(dst, None)
            continue
        if m == "lea" and ops[1].type == X.X86_OP_MEM and ops[1].mem.base == X.X86_REG_RIP:
            regs[dst] = ins.address + ins.size + ops[1].mem.disp
            continue
        if m == "xor" and dst and ops[1].type == X.X86_OP_REG and ops[0].reg == ops[1].reg:
            regs[dst] = 0
            continue
        if m == "mov" and dst and ops[1].type == X.X86_OP_IMM:
            regs[dst] = ops[1].imm & ((1 << (8 * ops[0].size)) - 1)
            continue
        if m == "mov" and dst and ops[1].type == X.X86_OP_REG:
            regs[dst] = regs.get(full_reg(ins.reg_name(ops[1].reg)))
            continue
        if m == "mov" and ops[0].type == X.X86_OP_MEM:
            base = ins.reg_name(ops[0].mem.base) if ops[0].mem.base else None
            if base in frame and ops[0].mem.index == 0:
                slot = frame[base] + ops[0].mem.disp
                size = ops[0].size
                if ops[1].type == X.X86_OP_IMM:
                    v = ops[1].imm
                else:
                    v = regs.get(full_reg(ins.reg_name(ops[1].reg)))
                if isinstance(v, int):
                    v &= (1 << (8 * size)) - 1
                    for i in range(size):
                        mem[slot + i] = (v >> (8 * i)) & 0xff
                else:
                    mem[slot] = v            # symbolic (call result / unknown)
                    for i in range(1, size):
                        mem.pop(slot + i, None)
            continue
        if dst and m not in ("cmp", "test"):
            regs.pop(dst, None)
            if dst != "rsp":
                frame.pop(dst, None)
    return mem, ret, calls


def read_field(mem, at, size):
    v0 = mem.get(at)
    if isinstance(v0, tuple):
        return v0
    if v0 is None and all(mem.get(at + i) is None for i in range(size)):
        return None
    v = 0
    for i in range(size):
        b = mem.get(at + i)
        if not isinstance(b, int):
            return None
        v |= b << (8 * i)
    return v


def parse_member(img, rva, member):
    mem, ret, calls = simulate(img, rva)
    # FMember base = the 8-byte slot holding a pointer to the member name
    base = None
    for slot in sorted(k for k, v in mem.items() if isinstance(v, int)):
        p = read_field(mem, slot, 8)
        if isinstance(p, int) and p > 0x1000 and img.u16(p) == member:
            base = slot
            break
    if base is None:
        return None
    f = {"name": member}
    for name, d, size in FIELDS:
        f[name] = read_field(mem, base + d, size)
    st = f["shader_type"]
    f["shader_type"] = (img.u16(st) or None) if isinstance(st, int) and st else None
    bt = f["base_type"]
    f["base_type"] = BASETYPE[bt] if isinstance(bt, int) and bt < len(BASETYPE) else bt
    f["prev"] = ret if isinstance(ret, int) else None
    f["rva"] = rva
    return f


def metadata_ctor(img, rva, short):
    """Linear sweep of GetStructMetadata: return the args of the FShaderParametersMetadata ctor call."""
    X = capstone.x86
    regs, stack = {}, {}
    for ins in img.md.disasm(img.code(rva, 0x600), rva):
        if ins.mnemonic == "int3":
            break
        ops = ins.operands
        dst = full_reg(ins.reg_name(ops[0].reg)) if ops and ops[0].type == X.X86_OP_REG else None
        if ins.mnemonic == "call":
            name = stack.get(0x20)
            if isinstance(name, int) and img.u16(name) == short:
                s = lambda k: img.u16(stack[k]) if isinstance(stack.get(k), int) and stack[k] else None
                return {"layout_name": img.u16(regs["r9"]) if isinstance(regs.get("r9"), int) else None,
                        "shader_variable": s(0x28), "static_slot": s(0x30), "file": img.cstr(stack[0x38]) if isinstance(stack.get(0x38), int) else None,
                        "file_line": stack.get(0x40), "sizeof": stack.get(0x48),
                        "use_case": regs.get("rdx"), "binding_flags": regs.get("r8")}
            regs.pop("rax", None)
            continue
        if ins.mnemonic == "lea" and ops[1].type == X.X86_OP_MEM and ops[1].mem.base == X.X86_REG_RIP:
            regs[dst] = ins.address + ins.size + ops[1].mem.disp
        elif ins.mnemonic == "xor" and dst and ops[1].type == X.X86_OP_REG and ops[0].reg == ops[1].reg:
            regs[dst] = 0
        elif ins.mnemonic == "mov" and dst and ops[1].type == X.X86_OP_IMM:
            regs[dst] = ops[1].imm
        elif ins.mnemonic == "mov" and ops[0].type == X.X86_OP_MEM and ops[0].mem.base == X.X86_REG_RSP                 and ops[0].mem.index == 0:
            d = ops[0].mem.disp
            stack[d] = ops[1].imm if ops[1].type == X.X86_OP_IMM else regs.get(full_reg(ins.reg_name(ops[1].reg)))
        elif dst:
            regs.pop(dst, None)
    return None


def main():
    args = sys.argv[1:]
    exe = args[0] if args and not args[0].startswith("--") else EXE
    pdb = exe[:-3] + "pdb"
    mod = comtypes.client.GetModule(DIA)
    src = comtypes.client.CreateObject(mod.DiaSource, interface=mod.IDiaDataSource)
    src.loadDataFromPdb(pdb)
    ses = src.openSession()
    g = ses.globalScope
    img = Image(exe)
    t = time.time()

    def sym_at(rva):
        s = ses.findSymbolByRVA(rva, SymTagPublic)
        return s.name if s else None

    def struct_of(rva):
        """Name of the struct whose metadata getter / static metadata object sits at rva."""
        s = ses.findSymbolByRVA(rva, SymTagPublic)
        if not s:
            return None
        u = s.undecoratedName or s.name
        for pat in (r"TShaderParameterStructTypeInfo<(?:struct |class )?(.+?)>::",
                    r"GetForwardDeclaredShaderParametersStructMetadata\((?:struct |class )?(\S+) const \*",
                    r"(?:struct |class |__cdecl )([\w:]+?)(?:::FTypeInfo)?::GetStructMetadata"):
            mm = re.search(pat, u)
            if mm:
                return mm.group(1)
        return u

    structs = {}
    pubs = list(dia_iter(g.findChildren(SymTagPublic, "?zzAppendMemberGetPrev@*", 0x8)))
    print("%d member functions" % len(pubs), file=sys.stderr)
    bad = []
    for p in pubs:
        if "UzzFirstMemberId@" in p.name:
            continue
        m = MEMBER_UNDEC.search(p.undecoratedName or "")
        if not m:
            bad.append(p.name)
            continue
        sname, member = m.group(1), m.group(2)
        f = parse_member(img, p.relativeVirtualAddress, member)
        if not f:
            bad.append(p.name)
            f = {"name": member, "error": "unparsed", "rva": p.relativeVirtualAddress}
        # nested/included struct metadata: resolve call target or data pointer to a struct name
        sv = f.get("struct")
        if isinstance(sv, tuple):
            f["struct"] = struct_of(sv[1]) if sv[1] else None
        elif isinstance(sv, int) and sv:
            f["struct"] = struct_of(sv)
        else:
            f["struct"] = None
        structs.setdefault(sname, []).append(f)
    print("parsed in %.0fs, %d failures" % (time.time() - t, len(bad)), file=sys.stderr)

    out = {}
    for sname, members in sorted(structs.items()):
        # declaration order: follow prev pointers from the member nobody points at
        by_rva = {f["rva"]: f for f in members}
        prevs = {f.get("prev") for f in members}
        last = [f for f in members if f["rva"] not in prevs]
        order = []
        if len(last) == 1:
            cur = last[0]["rva"]
            while cur in by_rva and len(order) <= len(members):
                order.append(by_rva[cur])
                cur = by_rva[cur].get("prev")
            order.reverse()
        if len(order) != len(members):
            order = sorted(members, key=lambda f: (f.get("offset") or 0))
        size = 0
        for u in dia_iter(g.findChildren(SymTagUDT, sname, 0x1)):
            size = max(size, u.length)
        out[sname] = {"size": size or None, "members": [{k: v for k, v in f.items() if k != "prev"} for f in order]}

    # uniform buffers: Struct::GetStructMetadata() (not FTypeInfo::) constructs the static FShaderParametersMetadata:
    # ctor(this, UseCase dl, BindingFlags r8b, LayoutName r9, StructTypeName [rsp+20], ShaderVariableName [rsp+28],
    #      StaticSlotName [rsp+30], FileName [rsp+38], FileLine [rsp+40], Size [rsp+48], Members [rsp+50], ...)
    for p in dia_iter(g.findChildren(SymTagPublic, "?GetStructMetadata@*", 0x8)):
        mm = re.search(r"__cdecl (.+)::GetStructMetadata\(void\)", p.undecoratedName or "")
        if not mm or mm.group(1).endswith("::FTypeInfo") or "TShaderParameterStructTypeInfo" in mm.group(1):
            continue
        sname = mm.group(1)
        info = metadata_ctor(img, p.relativeVirtualAddress, sname.split("::")[-1])
        if not info:
            print("no ctor found for", sname, file=sys.stderr)
            continue
        e = out.setdefault(sname, {"size": None, "members": []})
        e.update(info)
        e["uniform_buffer"] = True
        if e["size"] is None:
            e["size"] = info["sizeof"]
    json.dump(out, open(args[args.index("--dump") + 1], "w"), indent=1)
    print("%d structs, %d uniform buffers" % (len(out), sum(1 for v in out.values() if v.get("uniform_buffer"))),
          file=sys.stderr)
    for b in bad[:40]:
        print("FAIL", b, file=sys.stderr)


if __name__ == "__main__":
    main()
