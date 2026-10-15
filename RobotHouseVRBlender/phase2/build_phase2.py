"""
Phase 2 builder - floor, ceiling, walls, openings (Blender / bpy).

Run inside Blender via the MCP:
    STEP = "A"   # or "B", "C"
    exec(open('/home/cal/Downloads/RobotHouseVR/phase2/build_phase2.py').read())

STEP A  scene reset + collections
STEP B  floor slab + ceiling slab (building footprint)
STEP C  wall shell (exact union of wall rects) + door / arch / window cut-outs

Data source: phase1/coordinates.json  (metres, origin = SW interior corner of hall 49/2)
No bpy.ops mesh operators are used; all geometry is bmesh so the script is
context-independent and repeatable (each STEP deletes what it previously made).
"""
import json
import bpy
import bmesh

DATA = "/home/cal/Downloads/RobotHouseVR/phase1/coordinates.json"
CEIL_H = 2.40          # floor top Z = 0, ceiling underside Z = 2.40
SLAB_T = 0.10
DOOR_H = 2.04
ARCH_H = 2.10
FRENCH_H = 2.10
WIN_SILL = 0.90
WIN_HEAD = 2.10
WIN_HEAD_SMALL = 2.00   # windows narrower than 1.3 m
EPS = 0.02              # cutter overshoot through wall faces

COLLECTIONS = ["01_Architecture", "02_Staircase", "03_Kitchen", "04_Living_Dining", "05_Office_Entry"]


def load():
    with open(DATA) as f:
        return json.load(f)


# ---------------------------------------------------------------- collections
def get_col(name, parent=None):
    col = bpy.data.collections.get(name)
    if col is None:
        col = bpy.data.collections.new(name)
        (parent or bpy.context.scene.collection).children.link(col)
    return col


def link_only(obj, col):
    for c in list(obj.users_collection):
        c.objects.unlink(obj)
    col.objects.link(obj)


def delete_obj(name):
    o = bpy.data.objects.get(name)
    if o:
        me = o.data
        bpy.data.objects.remove(o, do_unlink=True)
        if me and me.users == 0:
            bpy.data.meshes.remove(me)


# ---------------------------------------------------------------- footprints
def point_in_poly(px, py, poly):
    inside = False
    n = len(poly)
    for i in range(n):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % n]
        if (y1 > py) != (y2 > py):
            xi = x1 + (py - y1) * (x2 - x1) / (y2 - y1)
            if xi > px:
                inside = not inside
    return inside


def footprint_cells(rects, polys):
    """Compressed-grid union of axis-aligned rects and rectilinear polygons.
    Returns (xs, ys, filled-cell-set)."""
    xs, ys = set(), set()
    for x0, y0, x1, y1 in rects:
        xs |= {round(x0, 3), round(x1, 3)}
        ys |= {round(y0, 3), round(y1, 3)}
    for p in polys:
        for x, y in p:
            xs.add(round(x, 3)); ys.add(round(y, 3))
    xs, ys = sorted(xs), sorted(ys)
    filled = set()
    for i in range(len(xs) - 1):
        cx = (xs[i] + xs[i + 1]) / 2
        for j in range(len(ys) - 1):
            cy = (ys[j] + ys[j + 1]) / 2
            hit = any(x0 <= cx <= x1 and y0 <= cy <= y1 for x0, y0, x1, y1 in rects)
            if not hit:
                hit = any(point_in_poly(cx, cy, p) for p in polys)
            if hit:
                filled.add((i, j))
    return xs, ys, filled


def merge_coplanar(bm):
    """Merge edge-connected coplanar faces into n-gons (grouped by normal + plane offset),
    then drop collinear 2-valence vertices."""
    bm.normal_update()
    groups = {}
    for f in bm.faces:
        n = f.normal
        key = (round(n.x, 3), round(n.y, 3), round(n.z, 3), round(n.dot(f.verts[0].co), 3))
        groups.setdefault(key, []).append(f)
    for fs in groups.values():
        if len(fs) > 1:
            bmesh.ops.dissolve_faces(bm, faces=[f for f in fs if f.is_valid])
    for _ in range(3):
        kill = []
        for v in bm.verts:
            if len(v.link_edges) == 2:
                e1, e2 = v.link_edges
                a_ = (e1.other_vert(v).co - v.co).normalized()
                b_ = (e2.other_vert(v).co - v.co).normalized()
                if a_.cross(b_).length < 1e-6:
                    kill.append(v)
        if not kill:
            break
        bmesh.ops.dissolve_verts(bm, verts=kill)


def prism_from_cells(name, xs, ys, filled, z0, z1, col):
    """Extrude the filled grid cells between z0 and z1 -> one clean mesh object."""
    bm = bmesh.new()
    vmap = {}

    def v(i, j):
        if (i, j) not in vmap:
            vmap[(i, j)] = bm.verts.new((xs[i], ys[j], z0))
        return vmap[(i, j)]

    for (i, j) in sorted(filled):
        bm.faces.new((v(i, j), v(i + 1, j), v(i + 1, j + 1), v(i, j + 1)))
    merge_coplanar(bm)
    ext = bmesh.ops.extrude_face_region(bm, geom=bm.faces[:])
    top_verts = [g for g in ext["geom"] if isinstance(g, bmesh.types.BMVert)]
    for tv in top_verts:
        tv.co.z = z1
    bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=1e-5)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    col.objects.link(ob)
    return ob


# ---------------------------------------------------------------- boolean helpers
def box(name, x0, y0, x1, y1, z0, z1):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for vv in bm.verts:
        vv.co.x = x0 if vv.co.x < 0 else x1
        vv.co.y = y0 if vv.co.y < 0 else y1
        vv.co.z = z0 if vv.co.z < 0 else z1
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    return ob


def bool_diff(target, cutter):
    m = target.modifiers.new("cut", "BOOLEAN")
    m.operation = "DIFFERENCE"
    m.solver = "EXACT"
    m.object = cutter
    dg = bpy.context.evaluated_depsgraph_get()
    new = bpy.data.meshes.new_from_object(target.evaluated_get(dg))
    old = target.data
    target.modifiers.remove(m)
    target.data = new
    new.name = old.name
    bpy.data.meshes.remove(old)


def tidy(ob):
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=1e-5)
    merge_coplanar(bm)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    bm.to_mesh(ob.data)
    bm.free()
    ob.data.update()


# ---------------------------------------------------------------- opening geometry
def opening_rects(d):
    """(name, rect, head_height) for every opening that needs wall fill / cutter."""
    out = []
    for n, o in d["openings"].items():
        x0, y0, x1, y1 = o["bbox_m"]
        if (x1 - x0) < 1e-6 or (y1 - y0) < 1e-6:
            continue                      # zero-width planes (A2, D12): fully open
        if n.startswith("A1"):
            h = ARCH_H
        elif n.startswith("D49_7_french"):
            h = FRENCH_H
        else:
            h = DOOR_H
        out.append((n, (x0, y0, x1, y1), h))
    return out


def window_cutters(d):
    out = []
    for n, w in d["windows"].items():
        wall = d["walls"][w["wall"]]["bbox_m"]
        a, b = w["from_m"], w["to_m"]
        if w["axis"] == "x":
            r = (a, wall[1] - EPS, b, wall[3] + EPS)
        else:
            r = (wall[0] - EPS, a, wall[2] + EPS, b)
        head = WIN_HEAD if w["width_m"] >= 1.3 else WIN_HEAD_SMALL
        out.append((n, r, WIN_SILL, head))
    return out


# ================================================================ STEPS
def step_A():
    for name in ("Cube",):
        delete_obj(name)
    helpers = get_col("00_Scene_Helpers")
    for nm in ("Camera", "Light"):
        o = bpy.data.objects.get(nm)
        if o:
            link_only(o, helpers)
    for c in COLLECTIONS:
        get_col(c)
    print("collections:", [c.name for c in bpy.context.scene.collection.children])


def step_B():
    d = load()
    col = get_col("01_Architecture")
    for n in ("ARCH_Floor", "ARCH_Ceiling"):
        delete_obj(n)
    rects = [tuple(w["bbox_m"]) for w in d["walls"].values()]
    rects += [r for _, r, _ in opening_rects(d)]
    polys = [r["polygon_m"] for r in d["rooms"].values()]
    xs, ys, filled = footprint_cells(rects, polys)
    fl = prism_from_cells("ARCH_Floor", xs, ys, filled, -SLAB_T, 0.0, col)
    ce = prism_from_cells("ARCH_Ceiling", xs, ys, filled, CEIL_H, CEIL_H + SLAB_T, col)
    print("footprint cells", len(filled), "floor verts", len(fl.data.vertices), "ceiling verts", len(ce.data.vertices))


def step_C():
    d = load()
    col = get_col("01_Architecture")
    delete_obj("ARCH_Walls")
    rects = [tuple(w["bbox_m"]) for w in d["walls"].values()]
    ops = opening_rects(d)
    rects += [r for _, r, _ in ops]        # fill every opening so a lintel survives above it
    xs, ys, filled = footprint_cells(rects, [])
    walls = prism_from_cells("ARCH_Walls", xs, ys, filled, 0.0, CEIL_H, col)
    ncut = 0
    cutters = []
    for n, (x0, y0, x1, y1), h in ops:
        # extend the cutter through the wall thickness only (the narrow axis)
        if (x1 - x0) < (y1 - y0):
            x0 -= EPS; x1 += EPS
        else:
            y0 -= EPS; y1 += EPS
        cutters.append(box("CUT_" + n, x0, y0, x1, y1, -0.05, h))
    for n, (x0, y0, x1, y1), sill, head in window_cutters(d):
        cutters.append(box("CUT_" + n, x0, y0, x1, y1, sill, head))
    for c in cutters:
        bool_diff(walls, c)
        ncut += 1
        bpy.data.objects.remove(c, do_unlink=True)
    tidy(walls)
    print("walls verts", len(walls.data.vertices), "faces", len(walls.data.polygons), "cuts", ncut)


if "STEP" in globals():
    {"A": step_A, "B": step_B, "C": step_C}[STEP]()
