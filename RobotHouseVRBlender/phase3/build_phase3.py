"""
Phase 3 builder - central U-turn staircase + ceiling opening (Blender / bpy).

    STEP = "A"   # treads + winders
    STEP = "B"   # stringers, newels, finials
    STEP = "C"   # handrails + spindles
    STEP = "D"   # ceiling cut-out
    exec(open('/home/cal/Downloads/RobotHouseVR/phase3/build_phase3.py').read())

Design (from floor-plan symbol + photos 49-2(1), 49-2(4), 49-2(6), 49-2(8)):
  * plan symbol footprint  X 2.48..4.04, Y 3.12..4.78  (two 0.83 m lanes split at Y = 3.95)
  * flight 1  (south lane)  climbs EAST   : steps 1-5   straight, 0.195 m going
  * turn      (east end)    4 winders     : steps 6-9   180 deg, fan around (3.455, 3.95)
  * flight 2  (north lane)  climbs WEST   : steps 10-15 straight - this lane is the one
                                            that passes OVER the desk
  * 16 equal risers, total rise 2.50 m  (= top of the 0.10 m ceiling slab, Z 2.4-2.5)
  * open risers, grey treads, pine stringers / newels / handrail / spindles
Everything is built in world coordinates, then each object's origin is moved to the
bottom-centre of the stair footprint (3.26, 3.95, 0) with no rotation / scale.
"""
import math
import bpy
import bmesh
from mathutils import Vector

# ------------------------------------------------------------------ parameters
X0, X1 = 3.645, 5.05             # stair footprint (west toe .. east end)
Y0, Y1, YM = 2.92, 4.58, 3.75   # south edge, north edge, lane split
D = 0.1755                      # going (tread run)
N_RISERS = 16
RISE = 2.50
R = RISE / N_RISERS             # 0.15625
XJ = X0 + 5 * D                 # 3.455  end of straight flight 1 / start of winders
XW = XJ - 6 * D                 # 2.285  west nosing of top tread (step 15)
T = 0.045                       # tread thickness
SW = 0.05                       # stringer thickness
SD = 0.26                       # stringer vertical depth
NEWEL = 0.09
RAIL_W, RAIL_H = 0.055, 0.07
SPINDLE = 0.032
RAIL_UP = 0.90                  # rail top above nosing line
ORIGIN = Vector((4.35, 3.75, 0.0))
TREAD_Y_S = (Y0 + SW, YM - SW)       # flight-1 tread Y extent
TREAD_Y_N = (YM + SW, Y1 - SW)       # flight-2 tread Y extent
WX1 = X1 - SW                        # winder east limit


def col():
    c = bpy.data.collections.get("02_Staircase")
    return c or bpy.data.collections.new("02_Staircase")


def delete_obj(name):
    o = bpy.data.objects.get(name)
    if o:
        me = o.data
        bpy.data.objects.remove(o, do_unlink=True)
        if me and me.users == 0:
            bpy.data.meshes.remove(me)


# ------------------------------------------------------------------ nosing lines
def z_nose1(x):          # flight 1 (climbs east)
    return R * ((x - X0) / D + 1)


def z_nose2(x):          # flight 2 (climbs west)
    return R * (9 + (XJ - x) / D)


# ------------------------------------------------------------------ bmesh primitives
def add_box(bm, x0, x1, y0, y1, z0, z1):
    vs = [bm.verts.new((x, y, z)) for z in (z0, z1) for y in (y0, y1) for x in (x0, x1)]
    # index = x + 2*y + 4*z
    for q in ((0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)):
        bm.faces.new([vs[i] for i in q])


def _extrude_poly(bm, pts3, vec):
    vs = [bm.verts.new(p) for p in pts3]
    f = bm.faces.new(vs)
    ext = bmesh.ops.extrude_face_region(bm, geom=[f])
    nv = [g for g in ext["geom"] if isinstance(g, bmesh.types.BMVert)]
    bmesh.ops.translate(bm, vec=vec, verts=nv)


def add_prism_xz(bm, pts, y0, y1):
    """polygon given as (x, z) points, extruded along Y from y0 to y1"""
    _extrude_poly(bm, [(x, y0, z) for x, z in pts], Vector((0, y1 - y0, 0)))


def add_prism_yz(bm, pts, x0, x1):
    _extrude_poly(bm, [(x0, y, z) for y, z in pts], Vector((x1 - x0, 0, 0)))


def add_prism_xy(bm, pts, z0, z1):
    _extrude_poly(bm, [(x, y, z0) for x, y in pts], Vector((0, 0, z1 - z0)))


def build_object(name, bm, c, origin=ORIGIN):
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    bmesh.ops.translate(bm, vec=-origin, verts=bm.verts[:])
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    ob.location = origin
    for cc in list(ob.users_collection):
        cc.objects.unlink(ob)
    c.objects.link(ob)
    return ob


def clip_poly_rect(poly, xmin, xmax, ymin, ymax):
    """Sutherland-Hodgman clip of a polygon to an axis-aligned rectangle"""
    def clip(pts, inside, inter):
        out = []
        for i in range(len(pts)):
            a, b = pts[i], pts[(i + 1) % len(pts)]
            ia, ib = inside(a), inside(b)
            if ia and ib:
                out.append(b)
            elif ia and not ib:
                out.append(inter(a, b))
            elif not ia and ib:
                out.append(inter(a, b)); out.append(b)
        return out
    def ix(xc):  return lambda a, b: (xc, a[1] + (b[1] - a[1]) * (xc - a[0]) / (b[0] - a[0]))
    def iy(yc):  return lambda a, b: (a[0] + (b[0] - a[0]) * (yc - a[1]) / (b[1] - a[1]), yc)
    p = poly
    p = clip(p, lambda q: q[0] >= xmin, ix(xmin))
    p = clip(p, lambda q: q[0] <= xmax, ix(xmax))
    p = clip(p, lambda q: q[1] >= ymin, iy(ymin))
    p = clip(p, lambda q: q[1] <= ymax, iy(ymax))
    return p


def winder_polys():
    """4 wedge polygons (XY) fanning 180 deg around P=(XJ, YM), clipped to the winder block."""
    P = (XJ, YM)
    big = 5.0
    polys = []
    for k in range(4):
        a0 = math.radians(-90 + 45 * k)
        a1 = math.radians(-90 + 45 * (k + 1))
        am = (a0 + a1) / 2
        tri = [P, (P[0] + big * math.cos(a0), P[1] + big * math.sin(a0)),
               (P[0] + big * math.cos(am), P[1] + big * math.sin(am)),
               (P[0] + big * math.cos(a1), P[1] + big * math.sin(a1))]
        c = clip_poly_rect(tri, XJ, WX1, TREAD_Y_S[0], TREAD_Y_N[1])
        # drop duplicate consecutive points
        cl = []
        for q in c:
            if not cl or abs(q[0] - cl[-1][0]) > 1e-6 or abs(q[1] - cl[-1][1]) > 1e-6:
                cl.append(q)
        polys.append(cl)
    return polys


# winder east-edge pieces: (y0, y1, step index)
def winder_edges():
    ys = [TREAD_Y_S[0]]
    P = (XJ, YM)
    for k in (1, 2, 3):
        a = math.radians(-90 + 45 * k)
        y = P[1] + (WX1 - P[0]) * math.tan(a)
        ys.append(max(min(y, TREAD_Y_N[1]), TREAD_Y_S[0]))
    ys.append(TREAD_Y_N[1])
    return [(ys[i], ys[i + 1], 6 + i) for i in range(4)]


# ================================================================== STEP A  treads
def step_A():
    delete_obj("STAIR_Treads")
    bm = bmesh.new()
    # flight 1 : steps 1-5
    for i in range(1, 6):
        xa, xb = X0 + D * (i - 1), X0 + D * i
        add_box(bm, xa, xb, TREAD_Y_S[0], TREAD_Y_S[1], i * R - T, i * R)
    # winders : steps 6-9
    for k, poly in enumerate(winder_polys()):
        z = (6 + k) * R
        add_prism_xy(bm, poly, z - T, z)
    # flight 2 : steps 10-15 (west)
    for i in range(10, 16):
        xb = XJ - D * (i - 10)
        xa = xb - D
        add_box(bm, xa, xb, TREAD_Y_N[0], TREAD_Y_N[1], i * R - T, i * R)
    ob = build_object("STAIR_Treads", bm, col())
    print("treads:", len(ob.data.polygons), "faces; step tops", [round(i * R, 3) for i in range(1, 16)])


# ================================================================== STEP B  stringers, newels
def newel_list():
    """(x, y, rail_top_z_at_that_point, name)"""
    zt = lambda f, x: f(x) + RAIL_UP
    out = [
        (X0 - 0.045, Y0, zt(z_nose1, X0 - 0.045)),
        (X0 - 0.045, YM, zt(z_nose1, X0 - 0.045)),
        (XJ, Y0, 6 * R + RAIL_UP),
        (XJ, YM, 9 * R + RAIL_UP),
        (XJ, Y1, 9 * R + RAIL_UP),
        (X1, Y0, 6 * R + RAIL_UP),
        (X1, YM, 7.5 * R + RAIL_UP),
        (X1, Y1, 9 * R + RAIL_UP),
        (XW + 0.045, YM, zt(z_nose2, XW + 0.045)),
        (XW + 0.045, Y1, zt(z_nose2, XW + 0.045)),
    ]
    return out


def step_B():
    delete_obj("STAIR_Stringers")
    delete_obj("STAIR_Newels")
    c = col()
    # ---- stringers (pine) ---------------------------------------------------
    bm = bmesh.new()
    up = 0.04
    # flight 1: south + inner edge (profile bottom clipped at the floor)
    xb0 = X0 + D * (SD - up) / R - D          # where bottom edge meets z = 0
    p1 = [(X0, 0), (X0, z_nose1(X0) + up), (XJ, z_nose1(XJ) + up), (XJ, z_nose1(XJ) + up - SD), (xb0, 0)]
    add_prism_xz(bm, p1, Y0, Y0 + SW)
    add_prism_xz(bm, p1, YM - SW, YM)
    # flight 2: north + inner edge (descending toward the west)
    p2 = [(XJ, z_nose2(XJ) + up), (XW, z_nose2(XW) + up), (XW, z_nose2(XW) + up - SD), (XJ, z_nose2(XJ) + up - SD)]
    add_prism_xz(bm, p2, Y1 - SW, Y1)
    add_prism_xz(bm, p2, YM, YM + SW)
    # winder outer boards: south, north and east pieces under each wedge
    edges = winder_edges()
    add_box(bm, XJ, X1, Y0, Y0 + SW, 6 * R + up - SD, 6 * R + up)
    add_box(bm, XJ, X1, Y1 - SW, Y1, 9 * R + up - SD, 9 * R + up)
    for ya, yb, s in edges:
        z = s * R + up
        add_box(bm, WX1, X1, ya, yb, z - SD, z)
    build_object("STAIR_Stringers", bm, c)

    # ---- newels + acorn finials --------------------------------------------
    bm = bmesh.new()
    h = NEWEL / 2
    for x, y, rt in newel_list():
        top = rt + 0.12
        add_box(bm, x - h, x + h, y - h, y + h, 0.0, top)
        # chamfered cap + acorn finial (low-poly sphere)
        add_box(bm, x - h * 0.7, x + h * 0.7, y - h * 0.7, y + h * 0.7, top, top + 0.03)
        res = bmesh.ops.create_uvsphere(bm, u_segments=10, v_segments=6, radius=0.05) \
            if "radius" in bmesh.ops.create_uvsphere.__doc__ else \
            bmesh.ops.create_uvsphere(bm, u_segments=10, v_segments=6, diameter=0.05)
        bmesh.ops.translate(bm, vec=Vector((x, y, top + 0.075)),
                            verts=[v for v in res["verts"]])
    build_object("STAIR_Newels", bm, c)
    print("stringers + newels built:", len(newel_list()), "newels")


# ================================================================== STEP C  handrails + spindles
def rails_def():
    """list of rails: ('xz', pts_by_x...) -> (kind, fixed_coord, a, za, b, zb)  top-of-rail heights"""
    na = X0 - 0.045
    nw = XW + 0.045
    return [
        ("x", Y0, na, z_nose1(na) + RAIL_UP, XJ, 6 * R + RAIL_UP, "f1"),           # flight 1 south
        ("x", YM, na, z_nose1(na) + RAIL_UP, XJ, 6 * R + RAIL_UP, "f1"),           # flight 1 inner
        ("x", Y1, XJ, 9 * R + RAIL_UP, nw, z_nose2(nw) + RAIL_UP, "f2"),            # flight 2 north
        ("x", YM, XJ, 9 * R + RAIL_UP, nw, z_nose2(nw) + RAIL_UP, "f2"),            # flight 2 inner
        ("x", Y0, XJ, 6 * R + RAIL_UP, X1, 6 * R + RAIL_UP, "w_s"),                  # winders south
        ("x", Y1, XJ, 9 * R + RAIL_UP, X1, 9 * R + RAIL_UP, "w_n"),                  # winders north
        ("y", X1, Y0, 6 * R + RAIL_UP, Y1, 9 * R + RAIL_UP, "w_e"),                  # winders east
    ]


def base_z(kind, s):
    """tread / stringer top height under a spindle at parameter s (x or y)"""
    if kind == "f1":
        return z_nose1(s) + 0.04
    if kind == "f2":
        return z_nose2(s) + 0.04
    if kind == "w_s":
        return 6 * R + 0.04
    if kind == "w_n":
        return 9 * R + 0.04
    for ya, yb, st in winder_edges():
        if ya <= s <= yb:
            return st * R + 0.04
    return 6 * R + 0.04


def step_C():
    delete_obj("STAIR_Handrails")
    delete_obj("STAIR_Spindles")
    c = col()
    bmr, bms = bmesh.new(), bmesh.new()
    hs = SPINDLE / 2
    for axis, fixed, a, za, b, zb, kind in rails_def():
        lo, hi = (a, b) if a < b else (b, a)
        zlo, zhi = (za, zb) if a < b else (zb, za)
        if axis == "x":
            add_prism_xz(bmr, [(lo, zlo - RAIL_H), (hi, zhi - RAIL_H), (hi, zhi), (lo, zlo)],
                         fixed - RAIL_W / 2, fixed + RAIL_W / 2)
        else:
            add_prism_yz(bmr, [(lo, zlo - RAIL_H), (hi, zhi - RAIL_H), (hi, zhi), (lo, zlo)],
                         fixed - RAIL_W / 2, fixed + RAIL_W / 2)
        # spindles every ~0.0975 (2 per tread) keeping clear of newels
        margin = NEWEL / 2 + SPINDLE
        n = max(1, int((hi - lo - 2 * margin) / 0.0975))
        for k in range(n + 1):
            s = lo + margin + (hi - lo - 2 * margin) * k / n
            zr = zlo + (zhi - zlo) * (s - lo) / (hi - lo)       # rail top
            zb_ = base_z(kind, s)
            ztop = zr - RAIL_H
            if ztop - zb_ < 0.05:
                continue
            if axis == "x":
                add_box(bms, s - hs, s + hs, fixed - hs, fixed + hs, zb_, ztop)
            else:
                add_box(bms, fixed - hs, fixed + hs, s - hs, s + hs, zb_, ztop)
    build_object("STAIR_Handrails", bmr, c)
    build_object("STAIR_Spindles", bms, c)
    print("handrails + spindles built")


# ================================================================== STEP D  ceiling opening
HOLE = (3.46, 2.83, 5.11, 4.67)     # x0, y0, x1, y1


def step_D():
    ce = bpy.data.objects["ARCH_Ceiling"]
    cut = bpy.data.objects.get("CUT_stair_hole")
    if cut:
        bpy.data.objects.remove(cut, do_unlink=True)
    x0, y0, x1, y1 = HOLE
    bm = bmesh.new()
    add_box(bm, x0, x1, y0, y1, 2.30, 2.60)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    me = bpy.data.meshes.new("CUT_stair_hole")
    bm.to_mesh(me); bm.free()
    cutter = bpy.data.objects.new("CUT_stair_hole", me)
    bpy.context.scene.collection.objects.link(cutter)
    m = ce.modifiers.new("hole", "BOOLEAN")
    m.operation = "DIFFERENCE"; m.solver = "EXACT"; m.object = cutter
    dg = bpy.context.evaluated_depsgraph_get()
    new = bpy.data.meshes.new_from_object(ce.evaluated_get(dg))
    old = ce.data
    ce.modifiers.remove(m)
    ce.data = new
    new.name = old.name
    bpy.data.meshes.remove(old)
    bpy.data.objects.remove(cutter, do_unlink=True)
    print("ceiling hole cut:", HOLE, "ceiling faces", len(ce.data.polygons))


if "STEP" in globals():
    c_ = col()
    if c_.name not in [x.name for x in bpy.context.scene.collection.children]:
        bpy.context.scene.collection.children.link(c_)
    {"A": step_A, "B": step_B, "C": step_C, "D": step_D}[STEP]()
