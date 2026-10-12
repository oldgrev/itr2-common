# Engine patch

`itr2-cm-compat.hashpatch.json` is our patch for Meta's Oculus fork of UE 5.5.4, tag
`oculus-5.5.4-release-1.110.0-v78.0`, so the editor saves and compiles what Into the Radius 2 expects:
- the rendering version entry CM Games added, and the 61 bytes of level visibility data that go with it;
- 44 properties and 7 classes CM added to engine types, as stubs, plus `FLightingChannels` with two channels;
- CM's changes to the uniform buffers material shaders use (`View`, `InstancedView`, `Primitive` and the per-object
  data, `ForwardLightData`, `SceneTextures`, `BasePass`, landscape);
- CM's lighting shader changes, marked `// ITR2:` in the shaders: the indirect light threshold and fill-sun terms in the
  base pass, the directional light attenuation, the spot cone cutoff, the reflection capture index guard, and the
  light-function atlas for opaque materials (stride 9 with per-eye matrices, as the game has it), plus the sun fade.
  The editor-side C++ fills for the new constants are in too, so the editor viewport still lights things;
- five more of CM's differences, found by auditing all 19 compiled shaders of the example against the game's, marked
  `shader-audit` in the shaders: in the base-pass vertex shader the height fog's exclusion distance, its directional
  inscattering condition and the aerial perspective's clip position; the order the fill-sun luminance is taken in; and
  a clamp on the volumetric lightmap lookup;
- `bSupportsSceneDataCompressedTransforms=false` for SM5, SM6 and ES3_1 in `Engine\Config\Windows\DataDrivenPlatformInfo.ini`,
  like the game's copy of that file. Without it your materials' vertex shaders read the object's transform in the
  wrong format and everything they draw comes out black.

Tested on 2026-10-12 in VR: a map cooked with the patched fork, with three materials of our own, loads in game, the
colours are right, there's no strobing under the torch, and in shade and under the torch they look like the game's own
materials. Only simple materials were tested (guide §5, §9). The three fog fixes were checked in VR afterwards: a
pillar with our material and one with the game's fade into the fog the same, in DX11 and DX12. The volumetric
lightmap clamp hasn't been tried in game (it needs baked lighting). The fill and ambient terms are reconstructed from
the game's compiled shaders, not from CM's source, so they're a close match, not a proven identical one.

It doesn't contain any of Epic's code. It refers to the lines it changes by line number and hash, and to lines it
reuses by where they are in your copy, so you need a clean checkout of that tag to apply it:
```
python <itr2-common>\tools\hashpatch.py check <itr2-common>\engine\itr2-cm-compat.hashpatch.json C:\ue55
python <itr2-common>\tools\hashpatch.py apply <itr2-common>\engine\itr2-cm-compat.hashpatch.json C:\ue55
```
69 files, 7 of them new. Applied to the tag's original files, it gives exactly the files of the fork we cooked the
example with. It refuses to apply a second time.

Licence: MIT ([`LICENSE`](LICENSE)), covering only the lines the patch adds. See the main README for why.
