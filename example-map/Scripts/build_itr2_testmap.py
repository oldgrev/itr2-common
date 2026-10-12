# Makes the ITR2 example map. The build scripts run it in a full editor process with -nullrhi -ExecutePythonScript,
# because the -run=pythonscript commandlet (what ITR1 used) crashes in new_level / new_blank_map on 5.5.
# You can also run it from the editor: File, Execute Python Script.
#   /Game/ITR2Mods/TestMap/L_ITR2Test        the map (40 x 40 m floor, walls, a platform and ramp, PlayerStart, sun + sky light)
#   /Game/ITR2Mods/TestMap/PAL_ITR2TestMap   a PrimaryAssetLabel that puts this folder in chunk 100, so the cook writes
#                                            our map into its own pakchunk100 container
# Lights are Movable, no lighting build. There's a mild ExponentialHeightFog (volumetric fog on, a little directional
# inscattering) and a SkyAtmosphere, so the fog code in the base-pass vertex shader gets used. Both routes get them.
#
# Two versions of the map:
#   - default: engine meshes and BasicShapeMaterial only (the game has its own cooked copies). For stock 5.5.4.
#   - ITR2_CUSTOM_MATERIALS=1 (build-itr2-map-fork.ps1 sets it): also makes three materials of our own in
#     /Game/ITR2Mods/TestMap/Materials (red walls, a checker floor, a green unlit return pad). Those need the patched
#     fork to cook (map-making/guide.md, section 4).
#   - ITR2_FOG_PILLARS=1 (needs ITR2_CUSTOM_MATERIALS=1): for checking your fog against the game's. It swaps in a strong
#     blue fog with orange directional inscattering, opens an 8 m gap in the +X wall and puts four pairs of pillars on a
#     floor extension at 10, 25, 50 and 100 m from the start: left M_ITR2_Red, right the game's own BasicShapeMaterial.
#     Where the shaders match the game's, both pillars of a pair fade into the fog the same.
import os
import unreal

FOLDER = "/Game/ITR2Mods/TestMap"
MAP = FOLDER + "/L_ITR2Test"
CHUNK = 100

eal = unreal.EditorAssetLibrary
ell = unreal.EditorLevelLibrary
CUBE = unreal.load_asset("/Engine/BasicShapes/Cube")
MAT = unreal.load_asset("/Engine/BasicShapes/BasicShapeMaterial")
assert CUBE and MAT, "engine basic shapes missing"


def tag(a, label):
    a.set_actor_label(label)
    a.tags = ["itr2test"]
    return a


def box(label, x, y, z, sx, sy, sz, yaw=0.0, pitch=0.0, mat=None):
    a = ell.spawn_actor_from_object(CUBE, unreal.Vector(x, y, z), unreal.Rotator(0.0, pitch, yaw))
    a.set_actor_scale3d(unreal.Vector(sx / 100.0, sy / 100.0, sz / 100.0))
    a.static_mesh_component.set_material(0, mat or MAT)
    return tag(a, label)


MATDIR = FOLDER + "/Materials"
CUSTOM = os.environ.get("ITR2_CUSTOM_MATERIALS") == "1"
PILLARS = os.environ.get("ITR2_FOG_PILLARS") == "1"
if PILLARS and not CUSTOM:
    print("ITR2_FOG_PILLARS needs ITR2_CUSTOM_MATERIALS=1 (the left pillars use M_ITR2_Red); no pillars")
    PILLARS = False
mel = unreal.MaterialEditingLibrary


def make_material(name, shading_model):
    path = MATDIR + "/" + name
    if eal.does_asset_exist(path):
        m = unreal.load_asset(path)
        mel.delete_all_material_expressions(m)
    else:
        m = unreal.AssetToolsHelpers.get_asset_tools().create_asset(name, MATDIR, unreal.Material, unreal.MaterialFactoryNew())
    m.set_editor_property("shading_model", shading_model)
    m.set_editor_property("blend_mode", unreal.BlendMode.BLEND_OPAQUE)
    return m


def node(m, cls, x, y, **props):
    n = mel.create_material_expression(m, cls, x, y)
    for k, v in props.items():
        n.set_editor_property(k, v)
    return n


def link(a, b, pin=""):
    mel.connect_material_expressions(a, "", b, pin)


def finish(m):
    mel.recompile_material(m)
    eal.save_loaded_asset(m)
    return m


def build_materials():
    """Three plain materials made of engine expressions only: no textures, functions or game assets."""
    E = unreal
    # Red: DefaultLit, BaseColor (0.8, 0.05, 0.05), Roughness 0.5
    red = make_material("M_ITR2_Red", E.MaterialShadingModel.MSM_DEFAULT_LIT)
    mel.connect_material_property(node(red, E.MaterialExpressionConstant3Vector, -400, 0, constant=E.LinearColor(0.8, 0.05, 0.05, 1.0)), "", E.MaterialProperty.MP_BASE_COLOR)
    mel.connect_material_property(node(red, E.MaterialExpressionConstant, -400, 200, r=0.5), "", E.MaterialProperty.MP_ROUGHNESS)
    finish(red)

    # Checker: frac((floor(u*40) + floor(v*40)) * 0.5) * 2 is 0 or 1, which picks between two greys
    chk = make_material("M_ITR2_Checker", E.MaterialShadingModel.MSM_DEFAULT_LIT)
    uv = node(chk, E.MaterialExpressionTextureCoordinate, -1400, 0, u_tiling=1.0, v_tiling=1.0)
    scale = node(chk, E.MaterialExpressionMultiply, -1200, 0, const_b=40.0)
    link(uv, scale, "A")
    fl = node(chk, E.MaterialExpressionFloor, -1000, 0)
    link(scale, fl)
    mu = node(chk, E.MaterialExpressionComponentMask, -800, -60, r=True, g=False, b=False, a=False)
    mv = node(chk, E.MaterialExpressionComponentMask, -800, 60, r=False, g=True, b=False, a=False)
    link(fl, mu)
    link(fl, mv)
    add = node(chk, E.MaterialExpressionAdd, -600, 0)
    link(mu, add, "A")
    link(mv, add, "B")
    half = node(chk, E.MaterialExpressionMultiply, -450, 0, const_b=0.5)
    link(add, half, "A")
    fr = node(chk, E.MaterialExpressionFrac, -300, 0)
    link(half, fr)
    two = node(chk, E.MaterialExpressionMultiply, -150, 0, const_b=2.0)
    link(fr, two, "A")
    lp = node(chk, E.MaterialExpressionLinearInterpolate, 50, 0)
    link(node(chk, E.MaterialExpressionConstant3Vector, -150, -200, constant=E.LinearColor(0.15, 0.15, 0.15, 1.0)), lp, "A")
    link(node(chk, E.MaterialExpressionConstant3Vector, -150, 200, constant=E.LinearColor(0.6, 0.6, 0.6, 1.0)), lp, "B")
    link(two, lp, "Alpha")
    mel.connect_material_property(lp, "", E.MaterialProperty.MP_BASE_COLOR)
    mel.connect_material_property(node(chk, E.MaterialExpressionConstant3Vector, 50, 300, constant=E.LinearColor(0.0, 0.0, 1.0, 1.0)), "", E.MaterialProperty.MP_NORMAL)
    mel.connect_material_property(node(chk, E.MaterialExpressionConstant, 50, 450, r=0.8), "", E.MaterialProperty.MP_ROUGHNESS)
    finish(chk)

    # Glow: Unlit, Emissive (0.1, 1.0, 0.2) * 5
    glow = make_material("M_ITR2_Glow", E.MaterialShadingModel.MSM_UNLIT)
    k = node(glow, E.MaterialExpressionMultiply, -200, 0, const_b=5.0)
    link(node(glow, E.MaterialExpressionConstant3Vector, -400, 0, constant=E.LinearColor(0.1, 1.0, 0.2, 1.0)), k, "A")
    mel.connect_material_property(k, "", E.MaterialProperty.MP_EMISSIVE_COLOR)
    finish(glow)
    return red, chk, glow


def build():
    red, checker, glow = build_materials() if CUSTOM else (None, None, None)
    # new_blank_map makes an empty untitled world; it's saved under MAP below
    unreal.EditorLoadingAndSavingUtils.new_blank_map(False)
    H = 2000.0   # 40 x 40 m
    box("Floor", 0, 0, -10, H * 2, H * 2, 20, mat=checker)
    for i, (x, y, sx, sy) in enumerate([(-H, 0, 100, H * 2), (0, H, H * 2, 100), (0, -H, H * 2, 100)]):
        box("Wall%d" % i, x, y, 150, sx, sy, 300)
    if PILLARS:
        # +X wall with an 8 m opening on the start's view line (y -400..400), so the pillars outside stay visible
        GAP = 400.0
        L = H - GAP
        box("Wall3a", H, -(GAP + L / 2), 150, 100, L, 300)
        box("Wall3b", H, GAP + L / 2, 150, 100, L, 300)
        # floor behind the opening, x 2000..9600; the pillars (200 x 200 x 400) are at x = -500 / 1000 / 3500 / 8500
        box("FloorExt", 5800, 0, -10, 7600, 2000, 20, mat=checker)
        for d, px in ((10, -500.0), (25, 1000.0), (50, 3500.0), (100, 8500.0)):
            box("Pillar%dm_Red" % d, px, -150, 200, 200, 200, 400, mat=red)
            box("Pillar%dm_Basic" % d, px, 150, 200, 200, 200, 400)
    else:
        box("Wall3", H, 0, 150, 100, H * 2, 300)
    box("InnerWallA", 300, 600, 150, 800, 40, 300, mat=red)
    box("InnerWallB", -600, -500, 150, 40, 900, 300, mat=red)
    box("Platform", 1200, -1200, 100, 600, 400, 200)
    box("Ramp", 1200 - 580, -1200, 100, 600, 400, 20, pitch=19.5)   # rises toward +X to the platform
    # Return pad: must match ReturnPad in loader-ue4ss/ITR2MapLoader/Scripts/config.lua (X=1500, Y=0). 2.5 m slab + 3 m post.
    PAD_X, PAD_Y = 1500.0, 0.0
    # Recognisable by shape: a big flat slab and a tall thin post. Green with our materials, grey without. (No material
    # instance for a green pad on stock 5.5.4: one saved by stock crashed the game, see the guide.)
    box("ReturnPadSlab", PAD_X, PAD_Y, 5, 250, 250, 10, mat=glow)
    box("ReturnPadPost", PAD_X, PAD_Y, 160, 20, 20, 300, mat=glow)
    ps = ell.spawn_actor_from_class(unreal.PlayerStart, unreal.Vector(-1500, 0, 100), unreal.Rotator(0, 0, 0))
    tag(ps, "PlayerStart")
    sun = ell.spawn_actor_from_class(unreal.DirectionalLight, unreal.Vector(0, 0, 1000), unreal.Rotator(0, -25, 210) if PILLARS else unreal.Rotator(0, -50, 35))
    sun.root_component.set_mobility(unreal.ComponentMobility.MOVABLE)
    sun.light_component.set_intensity(3.0)
    tag(sun, "Sun")
    sky = ell.spawn_actor_from_class(unreal.SkyLight, unreal.Vector(0, 0, 800), unreal.Rotator(0, 0, 0))
    sky.root_component.set_mobility(unreal.ComponentMobility.MOVABLE)
    sky.light_component.set_intensity(1.0)
    tag(sky, "SkyLight")

    # Fog. FogDensity is per 1000 cm, so 0.05 is an optical depth of about 0.5 at 100 m.
    fog = ell.spawn_actor_from_class(unreal.ExponentialHeightFog, unreal.Vector(0, 0, 0), unreal.Rotator(0, 0, 0))
    fc = fog.component
    fc.set_editor_property("enable_volumetric_fog", True)
    fc.set_editor_property("directional_inscattering_exponent", 4.0)
    fc.set_editor_property("directional_inscattering_start_distance", 500.0)
    if PILLARS:
        # strong and saturated so a difference between the two pillars of a pair shows: tau about 0.4 / 1 / 2 / 4 at 10 / 25 / 50 / 100 m
        fc.set_editor_property("fog_density", 0.4)
        fc.set_editor_property("fog_height_falloff", 0.001)               # about the same at any height
        fc.set_editor_property("start_distance", 0.0)
        fc.set_editor_property("fog_max_opacity", 1.0)
        fc.set_editor_property("fog_inscattering_luminance", unreal.LinearColor(0.0, 0.25, 1.0, 1.0))
        fc.set_editor_property("volumetric_fog_distance", 6000.0)         # the 100 m pair is beyond it, so that one is vertex fog only
        fc.set_editor_property("volumetric_fog_albedo", unreal.Color(40, 90, 255, 255))
        fc.set_editor_property("directional_inscattering_luminance", unreal.LinearColor(8.0, 1.5, 0.0, 1.0))
    else:
        fc.set_editor_property("fog_density", 0.05)
        fc.set_editor_property("directional_inscattering_luminance", unreal.LinearColor(1.0, 0.75, 0.4, 1.0))
    tag(fog, "ExponentialHeightFog")
    atm = ell.spawn_actor_from_class(unreal.SkyAtmosphere, unreal.Vector(0, 0, 0), unreal.Rotator(0, 0, 0))
    tag(atm, "SkyAtmosphere")
    unreal.EditorLoadingAndSavingUtils.save_map(ell.get_editor_world(), MAP)

    # chunk label
    pal_path = FOLDER + "/PAL_ITR2TestMap"
    if not eal.does_asset_exist(pal_path):
        pal = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
            "PAL_ITR2TestMap", FOLDER, unreal.PrimaryAssetLabel, unreal.DataAssetFactory())
    else:
        pal = unreal.load_asset(pal_path)
    rules = pal.get_editor_property("rules")
    rules.set_editor_property("chunk_id", CHUNK)
    rules.set_editor_property("cook_rule", unreal.PrimaryAssetCookRule.ALWAYS_COOK)
    pal.set_editor_property("rules", rules)
    pal.set_editor_property("label_assets_in_my_directory", True)
    eal.save_loaded_asset(pal)
    print("ITR2 test map built: " + MAP)


build()
