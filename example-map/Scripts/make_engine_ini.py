"""Make the cooking project's Config/DefaultEngine.ini from the game's own DefaultEngine.ini.

The game's file has PC ("Steam") and Quest settings side by side, plus online, Sentry, OculusXR and so on. For
cooking a map we only want the PC rendering, shader platform and navigation settings, so this keeps those:
- HardwareTargetingSettings, from its /Steam block;
- GameMapsSettings, pointed at your map instead of the game's startup level;
- WindowsTargetSettings, just the RHI and shader formats (DX11 SM5 and DX12 SM6, same as the game);
- RendererSettings: the /Steam block folded into the main one, without CM Games' own keys (CM.*,
  EnvironmentMaskShapesTextureArrayPath), which a stock engine doesn't know;
- NavCollision, RecastNavMesh, NavigationSystemV1 and DevOptions.Shaders as they are.

    python make_engine_ini.py <game DefaultEngine.ini> <out DefaultEngine.ini> [/Game/.../L_Map]
"""
import re
import sys

KEEP = ["/Script/WindowsTargetPlatform.WindowsTargetSettings", "/Script/NavigationSystem.NavCollision",
        "/Script/NavigationSystem.RecastNavMesh", "/Script/NavigationSystem.NavigationSystemV1", "DevOptions.Shaders"]
SKIP_KEY = re.compile(r"^[-+.!]?(CM\.|EnvironmentMaskShapesTextureArrayPath\b)")


def sections(path):
    """{name: [lines]}; repeated sections are joined. Blank lines and comments are dropped."""
    out, cur = {}, None
    for line in open(path, encoding="utf-8-sig").read().splitlines():
        s = line.strip()
        m = re.match(r"^\[(.+)\]$", s)
        if m:
            cur = out.setdefault(m.group(1), [])
        elif cur is not None and s and not s.startswith(";"):
            cur.append(line.rstrip())
    return out


def main():
    src, dst = sys.argv[1], sys.argv[2]
    level = sys.argv[3] if len(sys.argv) > 3 else "/Game/ITR2Mods/TestMap/L_ITR2Test"
    leaf = level.rsplit("/", 1)[-1]
    sec = sections(src)
    for need in KEEP + ["/Script/Engine.RendererSettings"]:
        if need not in sec:
            sys.exit(f"[{need}] not found in {src}; is this the game's DefaultEngine.ini?")
    out = ["; Made by make_engine_ini.py from the game's DefaultEngine.ini: PC settings only, /Steam blocks folded in,",
           "; CM Games' own keys left out, the default map pointed at our map.", ""]

    def block(name, lines):
        out.append(f"[{name}]")
        out.extend(lines)
        out.append("")

    block("/Script/HardwareTargeting.HardwareTargetingSettings",
          sec.get("/Script/HardwareTargeting.HardwareTargetingSettings/Steam", []))
    block("/Script/EngineSettings.GameMapsSettings",
          ["bUseSplitscreen=False", f"GameDefaultMap={level}.{leaf}", f"EditorStartupMap={level}.{leaf}"])
    # only the RHI and shader formats; the audio plugin settings name plugins the project doesn't have
    block(KEEP[0], [l for l in sec[KEEP[0]] if re.match(r"^[-+]?(DefaultGraphicsRHI|D3D1[12]TargetedShaderFormats|Compiler)=", l.strip())])
    renderer = sec.get("/Script/Engine.RendererSettings/Steam", []) + sec["/Script/Engine.RendererSettings"]
    dropped = [l for l in renderer if SKIP_KEY.match(l.strip())]
    block("/Script/Engine.RendererSettings", [l for l in renderer if not SKIP_KEY.match(l.strip())])
    for name in KEEP[1:]:
        block(name, sec[name])
    open(dst, "w", encoding="utf-8", newline="\r\n").write("\n".join(out))
    print(f"wrote {dst}; left out {len(dropped)} CM-only renderer keys")


if __name__ == "__main__":
    main()
