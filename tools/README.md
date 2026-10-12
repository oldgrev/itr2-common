# Tools

All Python 3. The build scripts and the kludge are in [`example-map/`](../example-map/); these are for applying the
engine patch and checking the result.

- **`hashpatch.py check|apply <json> <engine root>`**
  Applies [`engine/`](../engine/) to your fork checkout (the folder with `Engine\` in it). It checks every file's hash
  first and won't apply if anything doesn't match or it's already been applied. `make` is for writing a patch from a
  git diff. This is the ITR1 one plus support for files the patch creates.

## Does my fork match the game's shader layouts?
`pip install pefile capstone comtypes` first.
- **`ub_extract_stock.py <out.json> <editor dll>...`**
  Pulls the shader parameter layouts out of an editor build (`UnrealEditor-Engine.dll`, `-Renderer.dll`,
  `-RenderCore.dll`, `-Landscape.dll`). There's no PDB for those, so it finds the functions by their code pattern.
- **`ub_compare.py <game.json> <yours.json> <diff out.json>`**
  Matches each game struct to yours and diffs them. The game side is
  [`data/ub/game-itr2-5.5.4.json`](../data/ub/game-itr2-5.5.4.json).
- **`ub_extract_pdb.py [exe] --dump out.json`**
  How that game file was made: it reads the layouts out of `IntoTheRadius2-Win64-Shipping.exe` with the PDB that ships
  next to it (through Microsoft's DIA SDK and `comtypes`). Only needed again if the game updates. It looks for the exe
  in the default Steam folder (set `ITR2_EXE` otherwise) and for `msdia140.dll` where VS 2022 Community puts it (set
  `DIA_DLL` otherwise). `ub_extract_stock.py` uses its code too.

## Did my materials' shaders come out right?
These read the shader archive in your container after `retoc to-legacy` has turned it into an uncompressed legacy
`.ushaderbytecode` (guide §5 has the command). Windows only, they use `d3dcompiler_47.dll`.
- **`dxbc_scan.py <archive> <outdir> [--blobs]`**
  Finds the DXBC shaders in the archive and writes `index.tsv`.
- **`xform_check.py <archive> <index.tsv>`**
  Says which instance transform format the GPUScene vertex shaders read. The game's are all `uncompressed`. If yours
  say `compressed`, the `DataDrivenPlatformInfo.ini` change from the engine patch wasn't in the editor that cooked
  them, and the materials will draw black.
- **`prim_loads.py`** is what `xform_check.py` uses to disassemble. On its own it shows how shaders index the
  per-object data.
