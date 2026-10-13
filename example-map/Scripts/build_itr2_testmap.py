# Makes the ITR2 example map. The build scripts run it in a full editor process with -nullrhi -ExecutePythonScript,
# because the -run=pythonscript commandlet (what ITR1 used) crashes in new_level / new_blank_map on 5.5.
# You can also run it from the editor: File, Execute Python Script.
#   /Game/ITR2Mods/TestMap/L_ITR2Test        the map (40 x 40 m floor, walls, a platform and ramp, PlayerStart, sun + sky light)
#   /Game/ITR2Mods/TestMap/PAL_ITR2TestMap   a PrimaryAssetLabel that puts this folder in chunk 100, so the cook writes
#                                            our map into its own pakchunk100 container
# Lights are Movable and the map ships unbaked (the coverage flag adds static lights, for -BuildLighting). There's a mild ExponentialHeightFog (volumetric fog on, a little directional
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
#   - ITR2_COVERAGE=1 (needs ITR2_CUSTOM_MATERIALS=1): a strip of things that exercise shader permutations the plain room doesn't,
#     to the right (+Y) of the start. Three L-shaped blocks from an imported OBJ (SM_ITR2_Custom), a masked dot screen, 20 red
#     instanced cubes (a Blueprint with an InstancedStaticMeshComponent), a lightmapped booth with a static point light, a stationary
#     spot light, a LightmassImportanceVolume, and two translucent glass panes (surface translucency volume and per-pixel lighting).
#     The lightmapped parts only matter if you bake lighting (build-itr2-map-fork.ps1 -BuildLighting). Each part is wrapped in
#     try_section, so one failing part is logged ("COVERAGE SKIPPED") and the rest of the map still gets built.
#   Not made here: the WPO cubes (wobbling cyan cubes) and a landscape. Python in this editor can't wire World Position Offset or
#   create a landscape; see example-map/README.md ("World Position Offset") for the manual editor step.
import os
import tempfile
import traceback
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
COVERAGE = os.environ.get("ITR2_COVERAGE") == "1"
if COVERAGE and not CUSTOM:
    print("ITR2_COVERAGE needs ITR2_CUSTOM_MATERIALS=1; no coverage area")
    COVERAGE = False
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


def recompile_with_usage(m):
    # Usage flags decide which shader permutations get cooked. Without used_with_static_lighting the lightmap
    # permutations are skipped, and without used_with_instanced_static_meshes the ISM ones are. Once lighting is built
    # the game then draws the material as WorldGridMaterial (the grey grid). Add the flags for skeletal meshes etc. if you use them.
    for flag in ("used_with_static_lighting", "used_with_instanced_static_meshes"):
        try:
            m.set_editor_property(flag, True)
        except Exception as e:
            unreal.log_warning("usage flag %s: %s" % (flag, e))
    mel.recompile_material(m)


def finish(m):
    recompile_with_usage(m)
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


MESHDIR = FOLDER + "/Meshes"


def build_coverage_materials():
    E = unreal
    out = {}
    # Masked: dot cutout, procedural
    m = make_material("M_ITR2_Masked", E.MaterialShadingModel.MSM_DEFAULT_LIT)
    m.set_editor_property("blend_mode", E.BlendMode.BLEND_MASKED)
    m.set_editor_property("two_sided", True)
    uv = node(m, E.MaterialExpressionTextureCoordinate, -1400, 0)
    k = node(m, E.MaterialExpressionMultiply, -1200, 0, const_b=6.0)
    link(uv, k, "A")
    fr = node(m, E.MaterialExpressionFrac, -1000, 0)
    link(k, fr, "")
    sub = node(m, E.MaterialExpressionSubtract, -850, 0, const_b=0.5)
    link(fr, sub, "A")
    ab = node(m, E.MaterialExpressionAbs, -700, 0)
    link(sub, ab, "")
    mu = node(m, E.MaterialExpressionComponentMask, -550, -60, r=True, g=False, b=False, a=False)
    mv = node(m, E.MaterialExpressionComponentMask, -550, 60, r=False, g=True, b=False, a=False)
    link(ab, mu, "")
    link(ab, mv, "")
    mx = node(m, E.MaterialExpressionMax, -400, 0)
    link(mu, mx, "A")
    link(mv, mx, "B")
    dv = node(m, E.MaterialExpressionDivide, -250, 0, const_b=0.35)
    link(mx, dv, "A")
    fl = node(m, E.MaterialExpressionFloor, -100, 0)
    link(dv, fl, "")
    om = node(m, E.MaterialExpressionOneMinus, 50, 0)
    link(fl, om, "")
    sat = node(m, E.MaterialExpressionSaturate, 200, 0)
    link(om, sat, "")
    col = node(m, E.MaterialExpressionConstant3Vector, 0, -250, constant=E.LinearColor(0.9, 0.45, 0.05, 1.0))
    rg = node(m, E.MaterialExpressionConstant, 0, 250, r=0.6)
    mel.connect_material_property(col, "", E.MaterialProperty.MP_BASE_COLOR)
    mel.connect_material_property(rg, "", E.MaterialProperty.MP_ROUGHNESS)
    mel.connect_material_property(sat, "", E.MaterialProperty.MP_OPACITY_MASK)
    finish(m)
    out["masked"] = m

    # Translucent, lit: A = surface translucency volume, B = per-pixel lighting (the two lit translucency permutation families)
    for nm, mode in (("M_ITR2_Translucent", E.TranslucencyLightingMode.TLM_SURFACE),
                     ("M_ITR2_TranslucentPP", E.TranslucencyLightingMode.TLM_SURFACE_PER_PIXEL_LIGHTING)):
        m = make_material(nm, E.MaterialShadingModel.MSM_DEFAULT_LIT)
        m.set_editor_property("blend_mode", E.BlendMode.BLEND_TRANSLUCENT)
        m.set_editor_property("translucency_lighting_mode", mode)
        m.set_editor_property("two_sided", True)
        tint = E.LinearColor(1.0, 0.35, 0.1, 1.0) if nm == "M_ITR2_Translucent" else E.LinearColor(0.1, 1.0, 0.3, 1.0)
        c = node(m, E.MaterialExpressionConstant3Vector, -400, 0, constant=tint)
        o = node(m, E.MaterialExpressionConstant, -400, 200, r=0.35)
        rg = node(m, E.MaterialExpressionConstant, -400, 400, r=0.15)
        mel.connect_material_property(c, "", E.MaterialProperty.MP_BASE_COLOR)
        mel.connect_material_property(o, "", E.MaterialProperty.MP_OPACITY)
        mel.connect_material_property(rg, "", E.MaterialProperty.MP_ROUGHNESS)
        finish(m)
        out[nm] = m

    return out


def obj_box(lists, base, x0, y0, z0, x1, y1, z1):
    """Append an outward-facing (CCW, right-handed) box to the OBJ line lists; 24 v / 24 vt / 6 vn per box. Returns the new vertex base."""
    faces = [  # (normal, 4 corners CCW seen from outside)
        ((0, 0, 1), [(x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)]),
        ((0, 0, -1), [(x0, y1, z0), (x1, y1, z0), (x1, y0, z0), (x0, y0, z0)]),
        ((1, 0, 0), [(x1, y0, z0), (x1, y1, z0), (x1, y1, z1), (x1, y0, z1)]),
        ((-1, 0, 0), [(x0, y1, z0), (x0, y0, z0), (x0, y0, z1), (x0, y1, z1)]),
        ((0, 1, 0), [(x1, y1, z0), (x0, y1, z0), (x0, y1, z1), (x1, y1, z1)]),
        ((0, -1, 0), [(x0, y0, z0), (x1, y0, z0), (x1, y0, z1), (x0, y0, z1)]),
    ]
    uvs = [(0, 0), (1, 0), (1, 1), (0, 1)]
    v, vt, vn, f = lists
    for fi, (n, cs) in enumerate(faces):
        vn.append("vn %g %g %g" % n)
        for (cx, cy, cz), (u, w) in zip(cs, uvs):
            v.append("v %g %g %g" % (cx, cy, cz))
            vt.append("vt %g %g" % (u, w))
        i0 = base + fi * 4
        f.append("f " + " ".join("%d/%d/%d" % (i0 + k + 1, i0 + k + 1, len(vn)) for k in range(4)))
    return base + 24


def build_custom_mesh():
    path = MESHDIR + "/SM_ITR2_Custom"
    lists = ([], [], [], [])
    b = obj_box(lists, 0, 0, 0, 0, 300, 100, 100)       # long low arm (walkable)
    b = obj_box(lists, b, 0, 100, 0, 100, 300, 220)     # tall block: asymmetric L
    v, vt, vn, f = lists
    src = os.path.join(tempfile.gettempdir(), "SM_ITR2_Custom.obj")
    with open(src, "w") as fh:
        fh.write("# ITR2 L-block\n" + "\n".join(v + vt + vn + ["g SM_ITR2_Custom"] + f) + "\n")
    task = unreal.AssetImportTask()
    task.set_editor_property("filename", src)
    task.set_editor_property("destination_path", MESHDIR)
    task.set_editor_property("destination_name", "SM_ITR2_Custom")
    task.set_editor_property("automated", True)
    task.set_editor_property("replace_existing", True)
    task.set_editor_property("save", True)
    ui = unreal.FbxImportUI()
    ui.set_editor_property("import_mesh", True)
    ui.set_editor_property("import_as_skeletal", False)
    ui.set_editor_property("import_materials", False)
    ui.set_editor_property("import_textures", False)
    ui.set_editor_property("automated_import_should_detect_type", False)
    ui.set_editor_property("mesh_type_to_import", unreal.FBXImportType.FBXIT_STATIC_MESH)
    try:
        ui.set_editor_property("convert_scene", False)
    except Exception:
        pass
    d = ui.get_editor_property("static_mesh_import_data")
    d.set_editor_property("generate_lightmap_u_vs", True)
    d.set_editor_property("auto_generate_collision", True)
    d.set_editor_property("combine_meshes", True)
    task.set_editor_property("options", ui)
    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
    mesh = unreal.load_asset(path)
    assert mesh, "SM_ITR2_Custom import failed"
    bs = mesh.get_editor_property("body_setup")
    bs.set_editor_property("collision_trace_flag", unreal.CollisionTraceFlag.CTF_USE_COMPLEX_AS_SIMPLE)
    mesh.set_editor_property("light_map_resolution", 64)
    eal.save_loaded_asset(mesh)
    print("SM_ITR2_Custom: bounds=%s lightmap_uv_index=%s" % (mesh.get_bounds(), mesh.get_editor_property("light_map_coordinate_index")))
    return mesh


def spawn_mesh(label, mesh, x, y, z, sx=1.0, sy=1.0, sz=1.0, yaw=0.0, mat=None, mobility=None):
    a = ell.spawn_actor_from_object(mesh, unreal.Vector(x, y, z), unreal.Rotator(0.0, 0.0, yaw))
    a.set_actor_scale3d(unreal.Vector(sx, sy, sz))
    if mat:
        a.static_mesh_component.set_material(0, mat)
    if mobility is not None:
        a.root_component.set_mobility(mobility)
    return tag(a, label)


def try_section(name, fn, *a):
    try:
        r = fn(*a)
        print("COVERAGE OK: " + name)
        return r
    except Exception:
        print("COVERAGE SKIPPED: " + name + "\n" + traceback.format_exc())
        return None


def cov_custom(cm):
    for i, (x, yaw) in enumerate(((-1000, 0), (-600, 45), (-200, 90))):
        spawn_mesh("CustomL%d" % i, cm, x, 1100, 0, yaw=yaw)


def cov_masked(mats):
    # 2 x 0.05 x 2 m dot-cutout screen: casts a dotted shadow from the movable sun
    spawn_mesh("MaskedScreen", CUBE, 200, 1100, 110, 2.0, 0.05, 2.0, yaw=20, mat=mats["masked"])


def cov_ism(red):
    # level actors cannot get new components from Python, so a tiny Blueprint (Actor + InstancedStaticMeshComponent) carries the ISM
    bpp = FOLDER + "/BP_ITR2_IsmCubes"
    if eal.does_asset_exist(bpp):
        eal.delete_asset(bpp)
    fac = unreal.BlueprintFactory()
    fac.set_editor_property("parent_class", unreal.Actor)
    bp = unreal.AssetToolsHelpers.get_asset_tools().create_asset("BP_ITR2_IsmCubes", FOLDER, unreal.Blueprint, fac)
    sub = unreal.get_engine_subsystem(unreal.SubobjectDataSubsystem)
    handles = sub.k2_gather_subobject_data_for_blueprint(bp)
    params = unreal.AddNewSubobjectParams(parent_handle=handles[0], new_class=unreal.InstancedStaticMeshComponent, blueprint_context=bp)
    sub.add_new_subobject(params)
    unreal.BlueprintEditorLibrary.compile_blueprint(bp)
    eal.save_loaded_asset(bp)
    a = ell.spawn_actor_from_object(bp, unreal.Vector(0, 0, 0))
    ism = a.get_component_by_class(unreal.InstancedStaticMeshComponent)
    ism.set_mobility(unreal.ComponentMobility.STATIC)
    ism.set_static_mesh(CUBE)
    ism.set_material(0, red)
    for ix in range(5):
        for iy in range(4):
            t = unreal.Transform(unreal.Vector(300 + ix * 120, 1500 + iy * 120, 25), unreal.Rotator(0, 0, (ix * 4 + iy) * 7.0), unreal.Vector(0.5, 0.5, 0.5))
            r = ism.add_instance(t, True)
            if ix == 0 and iy == 0:
                print("ISM first add_instance -> %s, comp=%s mobility=%s" % (r, ism.get_name(), ism.mobility))
    tag(a, "IsmRedCubes")
    print("ISM instances: %d" % ism.get_instance_count())


def cov_booth(checker):
    ST = unreal.ComponentMobility.STATIC
    cx, cy = -1500.0, 1600.0
    spawn_mesh("BoothFloor", CUBE, cx, cy, 11, 4.2, 4.2, 0.2, mat=checker, mobility=ST)   # 1 cm up: avoids coplanar faces with the main floor
    spawn_mesh("BoothWallBack", CUBE, cx, cy + 200, 150, 4.2, 0.2, 3.0, mobility=ST)
    spawn_mesh("BoothWallL", CUBE, cx - 200, cy, 150, 0.2, 4.2, 3.0, mobility=ST)
    spawn_mesh("BoothWallR", CUBE, cx + 200, cy, 150, 0.2, 4.2, 3.0, mobility=ST)
    spawn_mesh("BoothRoof", CUBE, cx, cy, 310, 4.2, 4.2, 0.2, mobility=ST)
    spawn_mesh("BoothPillar", CUBE, cx + 80, cy + 80, 80, 0.5, 0.5, 1.6, mobility=ST)
    pl = ell.spawn_actor_from_class(unreal.PointLight, unreal.Vector(cx, cy - 60, 220), unreal.Rotator(0, 0, 0))
    pl.root_component.set_mobility(ST)
    pl.light_component.set_intensity(2500.0)
    pl.light_component.set_editor_property("attenuation_radius", 700.0)
    pl.light_component.set_light_color(unreal.LinearColor(1.0, 0.78, 0.55, 1.0))
    tag(pl, "BoothStaticLight")
    sp = ell.spawn_actor_from_class(unreal.SpotLight, unreal.Vector(-600, 700, 380), unreal.Rotator(0, -50, 90))   # stationary, on the custom meshes
    sp.root_component.set_mobility(unreal.ComponentMobility.STATIONARY)
    sp.light_component.set_intensity(8000.0)
    sp.light_component.set_editor_property("attenuation_radius", 1200.0)
    tag(sp, "StationarySpot")
    print("Cube lightmap uv index: %s" % CUBE.get_editor_property("light_map_coordinate_index"))


def cov_importance_volume():
    # covers the room + the pillar corridor so the volumetric lightmap reaches the fog pillars too. A spawned volume has the default brush;
    # it is scaled to size, and removed again if its bounds are degenerate (an empty importance volume would shrink the lighting scene to nothing)
    vol = ell.spawn_actor_from_class(unreal.LightmassImportanceVolume, unreal.Vector(3800, 0, 350), unreal.Rotator(0, 0, 0))
    o, ext = vol.get_actor_bounds(False)
    print("importance volume default extent: %s" % ext)
    if min(ext.x, ext.y, ext.z) < 1.0:
        vol.destroy_actor()
        raise RuntimeError("spawned volume has an empty brush")
    vol.set_actor_scale3d(unreal.Vector(11800.0 / (2 * ext.x), 4200.0 / (2 * ext.y), 900.0 / (2 * ext.z)))
    tag(vol, "LightmassImportance")
    o, ext = vol.get_actor_bounds(False)
    print("importance volume extent: %s" % ext)


def cov_glass(mats):
    # panes 6 m and 22 m from the start, to the left of the pillar line (y -450), 4 m wide x 3.5 m tall, 5 cm thick
    spawn_mesh("GlassVolume", CUBE, -900, -450, 175, 0.05, 4.0, 3.5, mat=mats["M_ITR2_Translucent"])
    spawn_mesh("GlassPerPixel", CUBE, 700, -450, 175, 0.05, 4.0, 3.5, mat=mats["M_ITR2_TranslucentPP"])


def coverage(red, checker):
    mats = try_section("coverage materials", build_coverage_materials)
    if not mats:
        return
    cm = try_section("custom mesh SM_ITR2_Custom", build_custom_mesh)
    if cm:
        try_section("custom mesh instances", cov_custom, cm)
    try_section("masked screen", cov_masked, mats)
    try_section("ISM", cov_ism, red)
    try_section("lightmapped booth + lights", cov_booth, checker)
    try_section("lightmass importance volume", cov_importance_volume)
    try_section("translucent panes", cov_glass, mats)


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
    if COVERAGE:
        coverage(red, checker)
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
