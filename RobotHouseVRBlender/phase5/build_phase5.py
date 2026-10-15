"""
Phase 5 builder - materials, textures and lighting (Blender 5.x / bpy, EEVEE).

    STEP = "M"    # procedural materials + assignment
    STEP = "C"    # curtains, pendant lamps, downlight fixtures  (small new meshes)
    STEP = "L"    # lights (sun, sky, window fill, downlights, pendants) + world
    STEP = "R"    # render / colour-management settings
    STEP = "ALL"
    exec(open('<this file>').read())

All textures are procedural and use Object texture coordinates (no UV maps needed, no image
files).  Re-runnable: every STEP removes what it made before (materials "P5_*", objects
"P5L_*" lights, curtains / pendants / fixtures).  Geometry of earlier phases is not touched
except for adding material slots.
"""
import json
import math
import bpy
import bmesh
from mathutils import Vector

DATA = "/home/cal/Downloads/RobotHouseVR/phase1/coordinates.json"
CEIL_H = 2.40


# =================================================================== node helpers
def setin(node, name, val):
    s = node.inputs.get(name)
    if s is not None:
        try:
            s.default_value = val
        except Exception:
            pass


def new_mat(name):
    old = bpy.data.materials.get(name)
    if old:
        bpy.data.materials.remove(old)
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    out.location = (900, 0)
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.location = (600, 0)
    nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    return m, nt, bsdf


def tex_coord(nt, scale=(1, 1, 1), loc=(-1200, 0)):
    tc = nt.nodes.new("ShaderNodeTexCoord"); tc.location = loc
    mp = nt.nodes.new("ShaderNodeMapping"); mp.location = (loc[0] + 200, loc[1])
    mp.inputs["Scale"].default_value = scale
    nt.links.new(tc.outputs["Object"], mp.inputs["Vector"])
    return mp


def ramp(nt, stops, loc=(0, 0)):
    r = nt.nodes.new("ShaderNodeValToRGB"); r.location = loc
    cr = r.color_ramp
    while len(cr.elements) > len(stops):
        cr.elements.remove(cr.elements[-1])
    while len(cr.elements) < len(stops):
        cr.elements.new(0.5)
    for el, (pos, col) in zip(cr.elements, stops):
        el.position = pos
        el.color = col
    return r


def bump(nt, height_socket, bsdf, strength=0.2, dist=0.01, loc=(300, -300)):
    b = nt.nodes.new("ShaderNodeBump"); b.location = loc
    b.inputs["Strength"].default_value = strength
    b.inputs["Distance"].default_value = dist
    nt.links.new(height_socket, b.inputs["Height"])
    nt.links.new(b.outputs["Normal"], bsdf.inputs["Normal"])


def plain(name, color, rough=0.5, metal=0.0, **kw):
    m, nt, b = new_mat(name)
    setin(b, "Base Color", (*color, 1))
    setin(b, "Roughness", rough)
    setin(b, "Metallic", metal)
    for k, v in kw.items():
        setin(b, k.replace("_", " "), v)
    return m


def noisy(name, color_a, color_b, rough, noise_scale, bump_str=0.1, metal=0.0, nd=0.0):
    """speckled / textured surface: two-colour noise + fine bump"""
    m, nt, b = new_mat(name)
    mp = tex_coord(nt, (1, 1, 1))
    n = nt.nodes.new("ShaderNodeTexNoise"); n.location = (-700, 0)
    setin(n, "Scale", noise_scale); setin(n, "Detail", 8.0); setin(n, "Roughness", 0.7)
    setin(n, "Distortion", nd)
    nt.links.new(mp.outputs["Vector"], n.inputs["Vector"])
    r = ramp(nt, [(0.35, (*color_a, 1)), (0.65, (*color_b, 1))], loc=(-350, 0))
    nt.links.new(n.outputs["Fac"], r.inputs["Fac"])
    nt.links.new(r.outputs["Color"], b.inputs["Base Color"])
    setin(b, "Roughness", rough); setin(b, "Metallic", metal)
    bump(nt, n.outputs["Fac"], b, bump_str, 0.005)
    return m


def wood(name, dark, light, rough=0.45, scale=(6, 24, 6), rings=4.0, bump_str=0.12):
    """banded wood grain (pine / beech / oak)"""
    m, nt, b = new_mat(name)
    mp = tex_coord(nt, scale)
    w = nt.nodes.new("ShaderNodeTexWave"); w.location = (-700, 100)
    w.wave_type = "BANDS"; w.bands_direction = "X"; w.wave_profile = "SIN"
    setin(w, "Scale", rings); setin(w, "Distortion", 7.0); setin(w, "Detail", 3.0)
    setin(w, "Detail Scale", 1.5); setin(w, "Detail Roughness", 0.6)
    nt.links.new(mp.outputs["Vector"], w.inputs["Vector"])
    n = nt.nodes.new("ShaderNodeTexNoise"); n.location = (-700, -200)
    setin(n, "Scale", 18.0); setin(n, "Detail", 6.0)
    nt.links.new(mp.outputs["Vector"], n.inputs["Vector"])
    mix = nt.nodes.new("ShaderNodeMath"); mix.operation = "MULTIPLY_ADD"; mix.location = (-450, 0)
    nt.links.new(w.outputs["Fac"], mix.inputs[0]); mix.inputs[1].default_value = 0.8
    nt.links.new(n.outputs["Fac"], mix.inputs[2])
    r = ramp(nt, [(0.25, (*dark, 1)), (0.85, (*light, 1))], loc=(-250, 0))
    nt.links.new(mix.outputs["Value"], r.inputs["Fac"])
    nt.links.new(r.outputs["Color"], b.inputs["Base Color"])
    setin(b, "Roughness", rough)
    bump(nt, w.outputs["Fac"], b, bump_str, 0.004)
    return m


def oak_floor(name):
    """light oak laminate planks 1.2 x 0.19 m, per-plank tint, grain, fine seams"""
    m, nt, b = new_mat(name)
    mp = tex_coord(nt, (0.5 / 1.2, 0.25 / 0.19, 1.0))
    br = nt.nodes.new("ShaderNodeTexBrick"); br.location = (-800, 200)
    br.offset = 0.5; br.offset_frequency = 2
    setin(br, "Scale", 1.0)
    setin(br, "Color1", (0.48, 0.32, 0.16, 1)); setin(br, "Color2", (0.58, 0.41, 0.23, 1))
    setin(br, "Mortar", (0.25, 0.17, 0.09, 1))
    setin(br, "Mortar Size", 0.006); setin(br, "Mortar Smooth", 0.1)
    setin(br, "Bias", 0.0); setin(br, "Brick Width", 0.5); setin(br, "Row Height", 0.25)
    nt.links.new(mp.outputs["Vector"], br.inputs["Vector"])
    # long stretched grain
    mp2 = tex_coord(nt, (1.2, 60.0, 1.0), loc=(-1200, -400))
    n = nt.nodes.new("ShaderNodeTexNoise"); n.location = (-800, -300)
    setin(n, "Scale", 4.0); setin(n, "Detail", 8.0); setin(n, "Roughness", 0.6); setin(n, "Distortion", 0.5)
    nt.links.new(mp2.outputs["Vector"], n.inputs["Vector"])
    mixc = nt.nodes.new("ShaderNodeMix"); mixc.data_type = "RGBA"; mixc.blend_type = "MULTIPLY"
    mixc.location = (-400, 100)
    mixc.inputs["Factor"].default_value = 0.45
    nt.links.new(br.outputs["Color"], mixc.inputs["A"])
    gr = ramp(nt, [(0.3, (0.75, 0.75, 0.75, 1)), (0.7, (1.0, 1.0, 1.0, 1))], loc=(-600, -300))
    nt.links.new(n.outputs["Fac"], gr.inputs["Fac"])
    nt.links.new(gr.outputs["Color"], mixc.inputs["B"])
    nt.links.new(mixc.outputs["Result"], b.inputs["Base Color"])
    setin(b, "Roughness", 0.38)
    bump(nt, br.outputs["Fac"], b, 0.25, 0.003)
    return m


# =================================================================== materials
def build_materials():
    M = {}
    M["floor"] = oak_floor("P5_OakFloor")
    M["wall"] = noisy("P5_WallWhite", (0.90, 0.90, 0.88), (0.93, 0.93, 0.91), 0.92, 60, 0.02)
    M["ceiling"] = plain("P5_Ceiling", (0.95, 0.95, 0.94), 0.95)
    M["pine"] = wood("P5_Pine", (0.38, 0.15, 0.03), (0.68, 0.34, 0.09), 0.40, (5, 22, 5), 5.0)
    M["tread"] = noisy("P5_TreadGrey", (0.18, 0.20, 0.23), (0.24, 0.26, 0.29), 0.55, 120, 0.08)
    M["beech"] = wood("P5_Beech", (0.58, 0.38, 0.18), (0.78, 0.57, 0.32), 0.42, (4, 20, 4), 3.0, 0.06)
    M["oak"] = wood("P5_OakFurn", (0.50, 0.30, 0.12), (0.72, 0.48, 0.22), 0.38, (4, 20, 4), 3.5, 0.06)
    M["laminate"] = noisy("P5_DeskLaminate", (0.55, 0.45, 0.34), (0.66, 0.55, 0.42), 0.45, 40, 0.03)
    M["counter"] = noisy("P5_CounterDark", (0.02, 0.025, 0.03), (0.09, 0.10, 0.11), 0.25, 220, 0.03)
    M["white_cab"] = plain("P5_WhiteCabinet", (0.88, 0.88, 0.86), 0.35)
    M["white_app"] = plain("P5_WhiteAppliance", (0.92, 0.92, 0.92), 0.28)
    M["steel"] = plain("P5_Steel", (0.75, 0.76, 0.78), 0.28, metal=1.0)
    M["chrome"] = plain("P5_Chrome", (0.85, 0.86, 0.88), 0.12, metal=1.0)
    M["black_metal"] = plain("P5_BlackMetal", (0.015, 0.015, 0.016), 0.35, metal=0.8)
    M["black_plastic"] = plain("P5_BlackPlastic", (0.012, 0.012, 0.013), 0.3)
    M["screen"] = plain("P5_Screen", (0.004, 0.005, 0.007), 0.08)
    M["glass"] = plain("P5_Glass", (0.9, 0.95, 1.0), 0.03, Transmission_Weight=1.0, IOR=1.45)
    M["leather"] = noisy("P5_BlackLeather", (0.012, 0.012, 0.012), (0.03, 0.03, 0.03), 0.38, 90, 0.06)
    M["fabric_grey"] = noisy("P5_GreyFabric", (0.10, 0.10, 0.11), (0.17, 0.17, 0.18), 0.95, 400, 0.35)
    M["fabric_blue"] = noisy("P5_ChairBlue", (0.02, 0.05, 0.25), (0.04, 0.09, 0.36), 0.85, 300, 0.25)
    M["curtain"] = noisy("P5_CurtainNavy", (0.07, 0.09, 0.18), (0.13, 0.16, 0.27), 0.95, 500, 0.4)
    M["banner"] = plain("P5_BannerPurple", (0.30, 0.10, 0.45), 0.6)
    M["shade"] = plain("P5_LampShade", (1.0, 0.85, 0.62), 0.9, Emission_Strength=0.0)
    ms = M["shade"]
    b = ms.node_tree.nodes["Principled BSDF"]
    setin(b, "Emission Color", (1.0, 0.72, 0.4, 1)); setin(b, "Emission Strength", 3.0)
    M["downlight"] = plain("P5_DownlightLens", (1, 1, 1), 0.3)
    b = M["downlight"].node_tree.nodes["Principled BSDF"]
    setin(b, "Emission Color", (1.0, 0.88, 0.7, 1)); setin(b, "Emission Strength", 12.0)
    M["rail"] = plain("P5_SilverTrim", (0.7, 0.7, 0.72), 0.3, metal=1.0)
    return M


def below(z):
    return lambda p: 0 if p[2] < z else 1


def assign(name, mats, rule=None):
    ob = bpy.data.objects.get(name)
    if ob is None:
        return
    me = ob.data
    me.materials.clear()
    for m in mats:
        me.materials.append(m)
    if rule is None or len(mats) == 1:
        for p in me.polygons:
            p.material_index = 0
        return
    mw = ob.matrix_world
    for p in me.polygons:
        c = mw @ p.center
        p.material_index = rule((c.x, c.y, c.z))


def step_M():
    M = build_materials()
    assign("ARCH_Walls", [M["wall"]])
    assign("ARCH_Floor", [M["floor"]])
    assign("ARCH_Ceiling", [M["ceiling"]])
    assign("STAIR_Treads", [M["tread"]])
    for n in ("STAIR_Stringers", "STAIR_Newels", "STAIR_Handrails", "STAIR_Spindles"):
        assign(n, [M["pine"]])
    # kitchen
    assign("K_BaseCabinets", [M["white_cab"]])
    assign("K_Worktop", [M["counter"]])
    assign("K_Sink", [M["steel"]])
    assign("K_Fridge", [M["white_app"]])
    assign("K_Cooker", [M["white_app"]])
    assign("K_Hood", [M["steel"]])
    assign("K_WallCabinets", [M["beech"]])
    assign("K_WallCabinets_Glass", [M["glass"]])
    # living / dining
    for n in ("D_Table", "D_Chair_1", "D_Chair_2", "D_Chair_3", "D_Chair_4"):
        assign(n, [M["oak"]])
    assign("L_Bookcase", [M["beech"]])
    assign("L_Sideboard", [M["beech"]])
    assign("L_CoffeeTable", [M["beech"]])
    for n in ("L_Sofa_West", "L_Loveseat_North"):
        assign(n, [M["leather"], M["chrome"]], lambda p: 1 if p[2] < 0.075 else 0)
    assign("L_Sofa_East", [M["fabric_grey"], M["black_plastic"]], lambda p: 1 if p[2] < 0.075 else 0)
    assign("L_TV", [M["screen"]])
    # office / entry
    assign("OFFICE_Desk", [M["laminate"], M["black_metal"]], lambda p: 0 if p[2] > 0.70 else 1)
    assign("OFFICE_Monitors", [M["black_plastic"], M["rail"]],
           lambda p: 1 if p[2] < 0.915 else 0)
    assign("OFFICE_Chair", [M["fabric_blue"], M["black_plastic"]], lambda p: 1 if p[2] < 0.43 else 0)
    assign("OFFICE_StairCabinet", [M["beech"]])
    assign("E_CurvedCabinet", [M["beech"]])
    assign("E_BannerStand", [M["banner"], M["black_metal"]], lambda p: 1 if p[2] < 0.041 else 0)
    print("materials assigned:", len(M))


# =================================================================== geometry helpers
def _col(name):
    c = bpy.data.collections.get(name) or bpy.data.collections.new(name)
    if c.name not in [x.name for x in bpy.context.scene.collection.children]:
        bpy.context.scene.collection.children.link(c)
    return c


def _mk(name, bm, coll, mat):
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    xs = [v.co.x for v in bm.verts]; ys = [v.co.y for v in bm.verts]; zs = [v.co.z for v in bm.verts]
    org = Vector(((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2, min(zs)))
    bmesh.ops.translate(bm, vec=-org, verts=bm.verts[:])
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me); bm.free()
    me.materials.append(mat)
    ob = bpy.data.objects.new(name, me)
    ob.location = org
    _col(coll).objects.link(ob)
    return ob


def _del_prefix(prefixes):
    for o in list(bpy.data.objects):
        if o.name.startswith(prefixes):
            me = o.data
            bpy.data.objects.remove(o, do_unlink=True)
            if me and getattr(me, "users", 1) == 0:
                (bpy.data.meshes if isinstance(me, bpy.types.Mesh) else bpy.data.lights).remove(me)


def _prism(bm, pts, z0, z1):
    vs = [bm.verts.new((x, y, z0)) for x, y in pts]
    f = bm.faces.new(vs)
    ext = bmesh.ops.extrude_face_region(bm, geom=[f])
    nv = [g for g in ext["geom"] if isinstance(g, bmesh.types.BMVert)]
    bmesh.ops.translate(bm, vec=Vector((0, 0, z1 - z0)), verts=nv)


def _cone(bm, r_bot, r_top, h, z0, cx, cy, segs=32):
    try:
        bmesh.ops.create_cone(bm, cap_ends=True, segments=segs, radius1=r_bot, radius2=r_top, depth=h)
    except TypeError:
        bmesh.ops.create_cone(bm, cap_ends=True, segments=segs, diameter1=2 * r_bot, diameter2=2 * r_top, depth=h)
    return z0 + h / 2


# =================================================================== curtains, pendants, fixtures
CURTAINS = {  # name: (y0, y1, z0, z1)
    "L_Curtain_A": (2.00, 4.65, 0.38, 2.32),
    "L_Curtain_B": (5.40, 7.80, 0.90, 2.32),
}
PENDANTS = {"L_Pendant_1": (1.55, 4.95), "L_Pendant_2": (1.55, 7.25)}
DOWNLIGHTS = [(0.9, 1.3), (2.3, 1.3), (0.9, 3.0), (2.3, 3.0), (0.9, 4.7), (2.3, 4.7),
              (0.9, 6.4), (2.3, 6.4), (0.9, 8.0), (2.3, 8.0),
              (4.4, 1.7), (5.6, 1.7), (5.6, 5.2), (4.3, 5.2),
              (4.2, -0.8), (5.3, -0.8), (0.9, -0.95), (2.3, -0.95)]


def step_C():
    _del_prefix(("L_Curtain", "L_Pendant", "P5F_"))
    M = {m.name: m for m in bpy.data.materials}
    curt, shade, lens, black = M["P5_CurtainNavy"], M["P5_LampShade"], M["P5_DownlightLens"], M["P5_BlackMetal"]
    # curtains: pleated ribbon hanging on the inside of the west wall
    for name, (y0, y1, z0, z1) in CURTAINS.items():
        bm = bmesh.new()
        n = 36
        outer, inner = [], []
        for i in range(n + 1):
            y = y0 + (y1 - y0) * i / n
            x = 0.07 + 0.035 * math.sin(2 * math.pi * i / 3.0)
            outer.append((x, y))
            inner.append((x - 0.016, y))
        _prism(bm, outer + inner[::-1], z0, z1)
        _mk(name, bm, "04_Living_Dining", curt)
    for name, (cx, cy) in PENDANTS.items():
        bm = bmesh.new()
        # cable
        v = []
        for x, y in ((cx - 0.006, cy - 0.006), (cx + 0.006, cy - 0.006), (cx + 0.006, cy + 0.006), (cx - 0.006, cy + 0.006)):
            v.append((x, y))
        _prism(bm, v, 2.18, CEIL_H)
        _mk(name + "_cable", bm, "04_Living_Dining", black)
        bm = bmesh.new()
        zc = _cone(bm, 0.19, 0.07, 0.24, 1.94, cx, cy)
        bmesh.ops.translate(bm, vec=Vector((cx, cy, zc)), verts=bm.verts[:])
        _mk(name, bm, "04_Living_Dining", shade)
    for i, (x, y) in enumerate(DOWNLIGHTS):
        bm = bmesh.new()
        zc = _cone(bm, 0.045, 0.045, 0.012, CEIL_H - 0.012, x, y, 24)
        bmesh.ops.translate(bm, vec=Vector((x, y, zc)), verts=bm.verts[:])
        _mk("P5F_Downlight_%02d" % i, bm, "06_Lighting", lens)
    print("curtains / pendants / fixtures built")


# =================================================================== lights
def add_light(name, kind, loc, energy, color=(1, 1, 1), **kw):
    ld = bpy.data.lights.new(name, kind)
    ld.energy = energy
    ld.color = color
    for k, v in kw.items():
        setattr(ld, k, v)
    ob = bpy.data.objects.new(name, ld)
    ob.location = loc
    _col("06_Lighting").objects.link(ob)
    return ob


def aim(ob, direction):
    ob.rotation_euler = Vector(direction).normalized().to_track_quat("-Z", "Y").to_euler()


def step_L():
    _del_prefix("P5L_")
    old = bpy.data.objects.get("Light")
    if old:
        ld = old.data
        bpy.data.objects.remove(old, do_unlink=True)
        bpy.data.lights.remove(ld)
    d = json.load(open(DATA))
    warm = (1.0, 0.86, 0.68)
    # sun through the west windows (low afternoon sun from the west-south-west)
    sun = add_light("P5L_Sun", "SUN", (-3, 3, 5), 0.8, (1.0, 0.95, 0.85), angle=math.radians(1.5))
    aim(sun, (0.85, 0.25, -0.45))
    # sky fill at every window: a rectangular area light just outside the glass line
    wall = {k: v["bbox_m"] for k, v in d["walls"].items()}
    for wn, w in d["windows"].items():
        wid = w["to_m"] - w["from_m"]
        head = 2.0 if wid < 1.3 else 2.1
        h = head - 0.9
        mid = (w["from_m"] + w["to_m"]) / 2
        zc = 0.9 + h / 2
        bb = wall[w["wall"]]
        if w["wall"] == "W03_W_ext":
            loc, dirv = (bb[0] - 0.15, mid, zc), (1, 0, -0.1)
        elif w["wall"] == "W22_S_ext":
            loc, dirv = (mid, bb[1] - 0.15, zc), (0, 1, -0.1)
        else:
            loc, dirv = (bb[2] + 0.15, mid, zc), (-1, 0, -0.1)
        a = add_light("P5L_Win_" + wn, "AREA", loc, 27.0 * wid, (0.97, 0.98, 1.0), shape="RECTANGLE",
                      size=wid, size_y=h)
        aim(a, dirv)
    # recessed downlights
    for i, (x, y) in enumerate(DOWNLIGHTS):
        s = add_light("P5L_Spot_%02d" % i, "SPOT", (x, y, CEIL_H - 0.02), 26.0, warm,
                      spot_size=math.radians(105), spot_blend=0.6, shadow_soft_size=0.05)
        aim(s, (0, 0, -1))
    # pendants
    for name, (cx, cy) in PENDANTS.items():
        add_light("P5L_" + name, "POINT", (cx, cy, 2.05), 12.0, (1.0, 0.78, 0.5), shadow_soft_size=0.12)
    # one ceiling light for each room that has no downlights
    for rn, r in d["rooms"].items():
        if rn.startswith(("49/2", "49/3", "49/1")):
            continue
        p = r["polygon_m"]
        cx = sum(a for a, b in p) / len(p); cy = sum(b for a, b in p) / len(p)
        add_light("P5L_Room_" + rn.split()[0].replace("/", "_"), "POINT", (cx, cy, 2.25), 12.0, warm,
                  shadow_soft_size=0.15)
    # world sky
    w = bpy.context.scene.world or bpy.data.worlds.new("World")
    bpy.context.scene.world = w
    w.use_nodes = True
    nt = w.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputWorld"); out.location = (600, 0)
    lit = nt.nodes.new("ShaderNodeBackground"); lit.location = (0, 100)      # what lights the scene
    lit.inputs["Color"].default_value = (0.85, 0.89, 0.97, 1); lit.inputs["Strength"].default_value = 0.15
    vis = nt.nodes.new("ShaderNodeBackground"); vis.location = (0, -100)     # what the camera sees through windows
    vis.inputs["Color"].default_value = (0.70, 0.84, 1.0, 1); vis.inputs["Strength"].default_value = 1.6
    lp = nt.nodes.new("ShaderNodeLightPath"); lp.location = (0, 300)
    mx = nt.nodes.new("ShaderNodeMixShader"); mx.location = (300, 0)
    nt.links.new(lp.outputs["Is Camera Ray"], mx.inputs["Fac"])
    nt.links.new(lit.outputs["Background"], mx.inputs[1])
    nt.links.new(vis.outputs["Background"], mx.inputs[2])
    nt.links.new(mx.outputs["Shader"], out.inputs["Surface"])
    print("lights:", len([o for o in bpy.data.objects if o.type == "LIGHT"]))


# =================================================================== render settings
def step_R():
    sc = bpy.context.scene
    sc.render.engine = "BLENDER_EEVEE"
    sc.render.resolution_x, sc.render.resolution_y = 1280, 960
    try:
        sc.eevee.taa_render_samples = 96
        sc.eevee.use_raytracing = True
        sc.eevee.use_shadows = True
    except Exception as e:
        print("eevee props:", e)
    sc.view_settings.view_transform = "AgX"
    sc.view_settings.exposure = 0.0
    ce = bpy.data.objects.get("ARCH_Ceiling")
    if ce:
        ce.hide_render = False
    print("render settings applied")


STEPS = {"M": step_M, "C": step_C, "L": step_L, "R": step_R}
if "STEP" in globals():
    for k in (list(STEPS) if STEP == "ALL" else [STEP]):
        STEPS[k]()
