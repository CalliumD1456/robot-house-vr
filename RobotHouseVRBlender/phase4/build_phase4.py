"""
Phase 4 builder - primary furniture blockout (Blender / bpy).

    STEP = "K"   # kitchen            -> 03_Kitchen
    STEP = "L"   # living + dining    -> 04_Living_Dining
    STEP = "O"   # desk + entry       -> 05_Office_Entry
    STEP = "ALL"
    exec(open('<this file>').read())

World frame (same as phase 1): origin = interior SW corner of the hall, +X east, +Y north,
Z = 0 floor, 1 BU = 1 m.  Each piece is one mesh object, origin at the bottom-centre of its
bounding box, no rotation / scale (transforms already applied).  Positions come from the
phase-1 room polygons + the reference photos (49-2(3,4,5,7,8,9), 49-3(1,2), 49-1(1)); sizes are
typical real-world sizes read off the photos.  Boxes are (x0, x1, y0, y1, z0, z1).
"""
import math
import bpy
import bmesh
from mathutils import Vector

PREFIX = ("K_", "L_", "D_", "OFFICE_", "E_")


# ------------------------------------------------------------------ helpers
def col(name):
    c = bpy.data.collections.get(name) or bpy.data.collections.new(name)
    if c.name not in [x.name for x in bpy.context.scene.collection.children]:
        bpy.context.scene.collection.children.link(c)
    return c


def delete_prefixed(prefixes):
    for o in list(bpy.data.objects):
        if o.name.startswith(prefixes):
            me = o.data
            bpy.data.objects.remove(o, do_unlink=True)
            if me and me.users == 0:
                bpy.data.meshes.remove(me)


def add_box(bm, x0, x1, y0, y1, z0, z1):
    vs = [bm.verts.new((x, y, z)) for z in (z0, z1) for y in (y0, y1) for x in (x0, x1)]
    for q in ((0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)):
        bm.faces.new([vs[i] for i in q])


def add_prism_xy(bm, pts, z0, z1):
    vs = [bm.verts.new((x, y, z0)) for x, y in pts]
    f = bm.faces.new(vs)
    ext = bmesh.ops.extrude_face_region(bm, geom=[f])
    nv = [g for g in ext["geom"] if isinstance(g, bmesh.types.BMVert)]
    bmesh.ops.translate(bm, vec=Vector((0, 0, z1 - z0)), verts=nv)


def add_frustum(bm, b0, z0, b1, z1):
    """convex frustum between two rectangles (x0,x1,y0,y1)"""
    vs = []
    for (x0, x1, y0, y1), z in ((b0, z0), (b1, z1)):
        for x, y in ((x0, y0), (x1, y0), (x1, y1), (x0, y1)):
            vs.append(bm.verts.new((x, y, z)))
    bmesh.ops.convex_hull(bm, input=vs)


def make(name, collname, boxes=(), extra=None):
    bm = bmesh.new()
    for b in boxes:
        add_box(bm, *b)
    if extra:
        extra(bm)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    xs = [v.co.x for v in bm.verts]; ys = [v.co.y for v in bm.verts]; zs = [v.co.z for v in bm.verts]
    org = Vector(((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2, min(zs)))
    bmesh.ops.translate(bm, vec=-org, verts=bm.verts[:])
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me); bm.free()
    ob = bpy.data.objects.new(name, me)
    ob.location = org
    col(collname).objects.link(ob)
    return ob


def table_boxes(x0, x1, y0, y1, h, top=0.04, leg=0.06, inset=0.04):
    b = [(x0, x1, y0, y1, h - top, h)]
    for lx in (x0 + inset, x1 - inset - leg):
        for ly in (y0 + inset, y1 - inset - leg):
            b.append((lx, lx + leg, ly, ly + leg, 0, h - top))
    return b


def sofa_boxes(x0, x1, y0, y1, back, seat_h=0.45, back_h=0.82, back_t=0.18, arm_t=0.16, arm_h=0.62, foot=0.08):
    """back: 'W','E','N','S' = which side the backrest is on"""
    b = [(x0, x1, y0, y1, foot, seat_h)]
    for fx in (x0 + 0.05, x1 - 0.09):
        for fy in (y0 + 0.05, y1 - 0.09):
            b.append((fx, fx + 0.04, fy, fy + 0.04, 0, foot))
    if back in "WE":
        bx = (x0, x0 + back_t) if back == "W" else (x1 - back_t, x1)
        b.append((bx[0], bx[1], y0, y1, seat_h, back_h))
        b.append((x0, x1, y0, y0 + arm_t, seat_h, arm_h))
        b.append((x0, x1, y1 - arm_t, y1, seat_h, arm_h))
    else:
        by = (y0, y0 + back_t) if back == "S" else (y1 - back_t, y1)
        b.append((x0, x1, by[0], by[1], seat_h, back_h))
        b.append((x0, x0 + arm_t, y0, y1, seat_h, arm_h))
        b.append((x1 - arm_t, x1, y0, y1, seat_h, arm_h))
    return b


def chair_boxes(cx, cy, facing, s=0.42, seat=0.45, back_h=0.92, leg=0.035):
    """facing: +1 east, -1 west, 'N' north, 'S' south (backrest on the opposite side)"""
    h = s / 2
    b = [(cx - h, cx + h, cy - h, cy + h, seat - 0.04, seat)]
    for lx in (cx - h, cx + h - leg):
        for ly in (cy - h, cy + h - leg):
            b.append((lx, lx + leg, ly, ly + leg, 0, seat - 0.04))
    if facing == "N":
        b.append((cx - h, cx + h, cy - h, cy - h + 0.03, seat, back_h))
    elif facing == "S":
        b.append((cx - h, cx + h, cy + h - 0.03, cy + h, seat, back_h))
    elif facing > 0:
        b.append((cx - h, cx - h + 0.03, cy - h, cy + h, seat, back_h))
    else:
        b.append((cx + h - 0.03, cx + h, cy - h, cy + h, seat, back_h))
    return b


# ================================================================== K  kitchen
# kitchen interior: X 3.465..6.07, Y -1.80..0.78 (phase-1 room 49/3)
def step_K():
    C = "03_Kitchen"
    g = 0.01
    base_h, top_t = 0.86, 0.04
    # sink opening X 4.47..5.02, Y -1.69..-1.29 (pocket left open in the base so the basin shows)
    sx0, sx1, sy0, sy1 = 4.47, 5.02, -1.69, -1.29
    base = [
        (3.475, 4.075, -1.79, -0.15, 0, base_h),     # west run (microwave side) incl. corner
        (4.075, sx0, -1.79, -1.19, 0, base_h),       # south run, west of sink
        (sx1, 6.06, -1.79, -1.19, 0, base_h),        # south run, east of sink
        (sx0, sx1, -1.79, sy0, 0, base_h),           # rim behind sink
        (sx0, sx1, sy1, -1.19, 0, base_h),           # rim in front of sink
        (sx0, sx1, sy0, sy1, 0, 0.76),               # cabinet body under the basin
        (5.46, 6.06, -1.19, -0.52, 0, base_h),       # east short run
    ]
    make("K_BaseCabinets", C, base)
    # worktop with the sink opening
    wt = [
        (3.475, 4.075, -1.79, -0.15, base_h, base_h + top_t),
        (4.075, sx0, -1.79, -1.19, base_h, base_h + top_t),
        (sx1, 6.06, -1.79, -1.19, base_h, base_h + top_t),
        (sx0, sx1, -1.79, sy0, base_h, base_h + top_t),
        (sx0, sx1, sy1, -1.19, base_h, base_h + top_t),
        (5.46, 6.06, -1.19, -0.52, base_h, base_h + top_t),
    ]
    make("K_Worktop", C, wt)
    t = 0.015
    sink = [
        (sx0, sx1, sy0, sy1, 0.76, 0.775),
        (sx0, sx0 + t, sy0, sy1, 0.76, base_h + top_t),
        (sx1 - t, sx1, sy0, sy1, 0.76, base_h + top_t),
        (sx0, sx1, sy0, sy0 + t, 0.76, base_h + top_t),
        (sx0, sx1, sy1 - t, sy1, 0.76, base_h + top_t),
    ]
    make("K_Sink", C, sink)
    make("K_Fridge", C, [(5.46, 6.06, 0.12, 0.72, 0, 1.75)])
    make("K_Cooker", C, [(5.46, 6.06, -0.50, 0.10, 0, 0.90)])

    def hood(bm):
        add_frustum(bm, (5.56, 6.06, -0.50, 0.10), 1.55, (5.86, 6.06, -0.30, -0.10), 2.00)
        add_box(bm, 5.86, 6.06, -0.30, -0.10, 2.00, 2.39)
    make("K_Hood", C, extra=hood)
    make("K_WallCabinets", C, [(3.475, 3.81, -1.70, -0.25, 1.45, 2.15)])
    gl = [(3.81, 3.82, -1.68 + i * 0.48, -1.68 + i * 0.48 + 0.44, 1.49, 2.11) for i in range(3)]
    make("K_WallCabinets_Glass", C, gl)


# ================================================================== L  living + dining
def step_L():
    C = "04_Living_Dining"
    # --- dining: table in front of the west window, long axis E-W (photos 2(5), 2(9)),
    #     two chairs on each long side
    make("D_Table", C, table_boxes(0.25, 1.85, 2.85, 3.75, 0.76))
    make("D_Chair_1", C, chair_boxes(0.65, 2.62, "N"))
    make("D_Chair_2", C, chair_boxes(1.45, 2.62, "N"))
    make("D_Chair_3", C, chair_boxes(0.65, 3.98, "S"))
    make("D_Chair_4", C, chair_boxes(1.45, 3.98, "S"))
    # --- south wall: tall bookcase + low sideboard (left of the hall door D1b)
    bc = [(0.10, 0.85, 0.02, 0.32, 0, 1.80)]
    t = 0.02
    bk = [(0.10, 0.10 + t, 0.02, 0.32, 0, 1.80), (0.85 - t, 0.85, 0.02, 0.32, 0, 1.80),
          (0.10, 0.85, 0.02, 0.04, 0, 1.80)]
    for z in (0.0, 0.40, 0.80, 1.20, 1.60, 1.78):
        bk.append((0.10, 0.85, 0.02, 0.32, z, z + t))
    make("L_Bookcase", C, bk)
    make("L_Sideboard", C, [(0.95, 2.30, 0.02, 0.47, 0.06, 0.80), (0.97, 1.03, 0.04, 0.10, 0, 0.06),
                            (2.22, 2.28, 0.04, 0.10, 0, 0.06), (0.97, 1.03, 0.39, 0.45, 0, 0.06),
                            (2.22, 2.28, 0.39, 0.45, 0, 0.06)])
    # --- lounge (north end)
    make("L_Sofa_West", C, sofa_boxes(0.05, 0.85, 5.85, 7.85, "W"))
    make("L_Loveseat_North", C, sofa_boxes(0.95, 2.10, 7.85, 8.65, "N"))
    # grey fabric couch against the east (TV) wall, facing west (photos 2(3), 2(5))
    make("L_Sofa_East", C, sofa_boxes(2.30, 3.20, 6.45, 8.45, "E", seat_h=0.45, back_h=0.85))
    make("L_CoffeeTable", C, table_boxes(1.25, 1.80, 6.55, 7.45, 0.40, top=0.04, leg=0.04, inset=0.03))
    make("L_TV", C, [(3.19, 3.25, 6.60, 7.60, 1.05, 1.65)])


# ================================================================== O  desk + entry
def step_O():
    C = "05_Office_Entry"
    # --- desk in the hall extension just north of the stair (photo-derived)
    dx0, dx1, dy0, dy1 = 3.65, 5.15, 5.05, 5.72
    d = [(dx0, dx1, dy0, dy1, 0.71, 0.75)]
    for lx in (dx0 + 0.10, dx1 - 0.16):
        d.append((lx, lx + 0.06, dy0 + 0.05, dy1 - 0.05, 0.0, 0.03))       # foot
        d.append((lx, lx + 0.06, (dy0 + dy1) / 2 - 0.03, (dy0 + dy1) / 2 + 0.03, 0.03, 0.71))
    make("OFFICE_Desk", C, d)
    mon = []
    for mx in (3.90, 4.50):
        mon.append((mx, mx + 0.55, 5.62, 5.66, 0.92, 1.25))                  # panel
        mon.append((mx + 0.25, mx + 0.30, 5.60, 5.66, 0.75, 0.92))           # stand
        mon.append((mx + 0.15, mx + 0.40, 5.54, 5.66, 0.75, 0.765))          # foot
    make("OFFICE_Monitors", C, mon)
    cx, cy = 4.00, 4.82
    ch = [(cx - 0.25, cx + 0.25, cy - 0.25, cy + 0.25, 0.44, 0.52),
          (cx - 0.23, cx + 0.23, cy - 0.25, cy - 0.20, 0.52, 1.05),
          (cx - 0.025, cx + 0.025, cy - 0.025, cy + 0.025, 0.10, 0.44),
          (cx - 0.325, cx + 0.325, cy - 0.03, cy + 0.03, 0.05, 0.10),
          (cx - 0.03, cx + 0.03, cy - 0.325, cy + 0.325, 0.05, 0.10)]
    for px, py in ((cx - 0.325, cy), (cx + 0.325, cy), (cx, cy - 0.325), (cx, cy + 0.325)):
        ch.append((px - 0.025, px + 0.025, py - 0.025, py + 0.025, 0, 0.05))
    make("OFFICE_Chair", C, ch)
    # --- low storage cabinet under the winders, between the east newels
    make("OFFICE_StairCabinet", C, [(4.52, 4.97, 3.02, 3.70, 0, 0.70)])
    # --- entry vestibule (49/1): curved-front cabinet under the south window
    def curved(bm):
        pts = [(1.45, -1.78), (2.35, -1.78), (2.35, -1.30)]
        n = 8
        for i in range(1, n):
            u = i / n
            # quadratic bezier from (2.35,-1.30) via (1.90,-1.00) to (1.45,-1.30)
            x = (1 - u) ** 2 * 2.35 + 2 * u * (1 - u) * 1.90 + u * u * 1.45
            y = (1 - u) ** 2 * -1.30 + 2 * u * (1 - u) * -1.00 + u * u * -1.30
            pts.append((x, y))
        pts.append((1.45, -1.30))
        add_prism_xy(bm, pts, 0.0, 0.75)
    make("E_CurvedCabinet", C, extra=curved)
    make("E_BannerStand", C, [(3.07, 3.22, -1.52, -0.63, 0, 0.04), (3.14, 3.18, -1.50, -0.65, 0.04, 2.00)])


STEPS = {"K": (step_K, ("K_",)), "L": (step_L, ("L_", "D_")), "O": (step_O, ("OFFICE_", "E_"))}

if "STEP" in globals():
    keys = list(STEPS) if STEP == "ALL" else [STEP]
    for k in keys:
        fn, pre = STEPS[k]
        delete_prefixed(pre)
        fn()
    print("phase 4 built:", keys, "objects:",
          len([o for o in bpy.data.objects if o.name.startswith(PREFIX)]))
