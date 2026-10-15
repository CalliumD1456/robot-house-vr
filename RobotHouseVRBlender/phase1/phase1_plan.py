"""
Phase 1 - Dimensional calibration & floor-plan trace (no Blender geometry).

Pure-python (no numpy/PIL needed).  Outputs:
  phase1/coordinates.json   machine-readable map used by later phases
  stdout                    QA self-check report

Source of truth
---------------
* Floor Plan.png (730x600 px).  Walls were extracted from the raster by line
  detection (see phase1_notes.md).  Pixel coords below are IMAGE coords (y down).
* Room Rough Dimensions.png - used to calibrate scale and to cross-check.

World frame
-----------
  origin (0,0) = interior south-west corner of room 49/2 (living/dining hall)
  +X = plan right (east), +Y = plan up (north), Z = 0 floor, 1 BU = 1 m.
  scale  K = 0.0198 m/px  (8.70 m sketch west wall / 439.5 px)
"""
import json, math, os

K = 0.0198
OX, OY = 54.0, 479.5          # px of world origin (inner face of west wall, bottom of 49/2)


def X(px):
    return round((px - OX) * K, 3)


def Y(py):
    return round((OY - py) * K, 3)


# ----------------------------------------------------------------------------
# ROOMS  (interior-face polygons, px, rectilinear)
# ----------------------------------------------------------------------------
ROOMS_PX = {
    "49/2 Hall (living/dining/stairs)": [
        (54, 479.5), (218.5, 479.5), (218.5, 434),
        (364.5, 434), (364.5, 189), (230, 189), (230, 197), (218.5, 197),
        (218.5, 40), (54, 40)],
    "49/1 Entry vestibule": [
        (69, 486.5), (218.5, 486.5), (218.5, 570.5), (87, 570.5), (87, 530), (69, 530)],
    "49/3 Kitchen": [(229, 440), (360.5, 440), (360.5, 570.5), (229, 570.5)],
    "49/4 Rear hallway": [(364.5, 349), (534, 349), (534, 397), (364.5, 397)],
    "49/5 Room (S-E)": [(369, 402), (517, 402), (517, 570.5), (369, 570.5)],
    "49/6 Room (E)": [(369, 197), (514.5, 197), (514.5, 343), (369, 343)],
    "49/7 Room (N)": [(230, 182), (464, 182), (464, 40), (230, 40)],
    "49/12 Annex (E)": [(534, 334), (676, 334), (676, 548), (534, 548)],
}
PLAN_AREA = {  # m2 printed on floor plan
    "49/2 Hall (living/dining/stairs)": 44.86, "49/1 Entry vestibule": 4.85,
    "49/3 Kitchen": 7.03, "49/4 Rear hallway": 3.26, "49/5 Room (S-E)": 10.40,
    "49/6 Room (E)": 8.93, "49/7 Room (N)": 13.70, "49/12 Annex (E)": 12.57,
}

# ----------------------------------------------------------------------------
# WALLS  (solid rects, px: x0,y0,x1,y1) with a thickness class
# ----------------------------------------------------------------------------
WALLS_PX = {
    # id: (rect, kind, note)
    "W01_N_ext_A":      ((42.5, 29, 366, 40),        "ext",  "north wall above 49/2 + 49/7 (left part)"),
    "W02_N_ext_B":      ((366, 29, 474, 40),         "ext",  "north wall over 49/7 right part (jog flattened)"),
    "W03_W_ext":        ((42.5, 40, 54, 486.5),      "ext",  "west wall of 49/2 (full length 8.70)"),
    "W04_49_7_E":       ((464, 40, 474, 70),         "ext",  "49/7 east wall - north of French doors"),
    "W05_49_7_E":       ((464, 144, 474, 189),       "ext",  "49/7 east wall - south of French doors"),
    "W06_49_6_N":       ((364.5, 182, 474, 197),     "part", "49/7-49/6 partition (jog flattened, 0.30 m)"),
    "W07_49_6_N_ext":   ((474, 185, 526, 197),       "ext",  "49/6 north exterior wall"),
    "W08_49_6_E":       ((514.5, 197, 526, 349),     "ext",  "49/6 east exterior wall (window)"),
    "W09_49_6_W":       ((364.5, 189, 369, 349),     "thin", "49/2 | 49/6 partition (sketch 3.25 m)"),
    "W10_hall_N":       ((369, 343, 534, 349),       "part", "rear hallway north wall (sketch 3.20 m)"),
    "W11_hall_S_jamb":  ((369, 397, 377, 402),       "part", "49/5 door jamb"),
    "W12_hall_S":       ((427, 397, 527.5, 402),     "part", "rear hallway south wall (sketch 2.05 m)"),
    "W13_pier":         ((364.5, 397, 369, 434),     "thin", "pier between hall mouth and kitchen"),
    "W14_main_49_7":    ((218.5, 40, 230, 197),      "ext",  "49/2 | 49/7 structural wall"),
    "W15_49_7_S":       ((230, 182, 364.5, 189),     "part", "49/7 south wall (door D7 cut)"),
    "W16_49_5_E":       ((517, 397, 527.5, 581.5),   "ext",  "49/5 east exterior wall"),
    "W17_49_12_W_up":   ((526, 327, 534, 349),       "thin", "annex west wall junction"),
    "W18_49_12_W_lo":   ((527.5, 397, 534, 556),     "thin", "annex west wall (lower)"),
    "W19_49_12_N":      ((526, 327, 683, 334),       "thin", "annex north wall"),
    "W20_49_12_E":      ((676, 327, 683, 556),       "thin", "annex east wall"),
    "W21_49_12_S":      ((527, 548, 683, 556),       "thin", "annex south wall"),
    "W22_S_ext":        ((77, 570.5, 527.5, 581.5),  "ext",  "south exterior wall 49/1 + kitchen + 49/5"),
    "W23_49_1_W_lo":    ((77, 540, 87, 581.5),       "ext",  "49/1 lower west wall"),
    "W24_49_1_W_jamb":  ((42.5, 530, 87, 540),       "ext",  "49/1 entry-door lower jamb / notch"),
    "W25_49_1_N":       ((42.5, 479.5, 172, 486.5),  "thin", "49/2 | 49/1 partition (door D1b cut)"),
    "W26_49_1_kit":     ((218.5, 434, 229, 581.5),   "ext",  "49/1 | kitchen wall (pier flattened to kitchen north face)"),
    "W28_kit_N_A":      ((218.5, 434, 274, 440),     "part", "kitchen north wall, west piece (nib flattened; 1.10 m)"),
    "W29_kit_N_B":      ((313, 434, 364.5, 440),     "part", "kitchen north wall, east piece (sketch 1.02 m)"),
    "W30_kit_E":        ((360.5, 434, 369, 581.5),   "thin", "kitchen | 49/5 partition"),
}

# openings: id -> (rect, kind, note)  kind: int = room-to-room, ext = to outside
OPENINGS_PX = {
    "D1_entry_ext":   ((42.5, 486.5, 69, 530),   "ext", "front door into 49/1 (thick reveal)"),
    "D1b_49_1_hall":  ((172, 479.5, 218.5, 486.5), "int", "door 49/1 <-> hall"),
    "A1_kitchen_arch": ((274, 434, 313, 440),     "int", "kitchen archway"),
    "A2_hall_mouth":  ((364.5, 349, 364.5, 397),    "int", "wide opening hall <-> rear hallway (zero-width plane)"),
    "D7_49_7":        ((318, 182, 355, 189),      "int", "door hall <-> 49/7"),
    "D6_49_6":        ((387, 343, 423, 349),      "int", "door hallway <-> 49/6"),
    "D5_49_5":        ((377, 397, 427, 402),      "int", "door hallway <-> 49/5"),
    "D12_annex":      ((534, 349, 534.0, 397),    "int", "glazed door hallway <-> annex (zero-width plane)"),
    "D49_7_french":   ((464, 70, 474, 144),       "ext", "French doors, 49/7 east wall"),
}

# windows: id -> (wall, axis, a0, a1, note)  px coordinate range along the wall
WINDOWS_PX = {
    "WIN_hall_west_A": ("W03_W_ext", "y", 264, 360, "49/2 west wall window nearest dining (south)"),
    "WIN_hall_west_B": ("W03_W_ext", "y", 98, 194, "49/2 west wall window nearest sofas (north)"),
    "WIN_49_1_S":      ("W22_S_ext", "x", 113, 188, "49/1 south window (entry vestibule)"),
    "WIN_kitchen_S":   ("W22_S_ext", "x", 257, 330, "kitchen sink window"),
    "WIN_49_5_S":      ("W22_S_ext", "x", 414, 463, "49/5 south window"),
    "WIN_49_6_E":      ("W08_49_6_E", "y", 234, 296, "49/6 east window"),
}

# ----------------------------------------------------------------------------
# helpers
# ----------------------------------------------------------------------------
def poly_area_px(p):
    s = 0
    for i in range(len(p)):
        x1, y1 = p[i]; x2, y2 = p[(i + 1) % len(p)]
        s += x1 * y2 - x2 * y1
    return abs(s) / 2


def rect_m(r):
    x0, y0, x1, y1 = r
    return (X(x0), Y(y1), X(x1), Y(y0))        # xmin,ymin,xmax,ymax in metres


# raster check at 0.5 px (~1 cm) resolution
S = 2
W_, H_ = int(730 * S), int(600 * S)


def raster_poly(p):
    cells = set()
    pts = [(x * S, y * S) for x, y in p]
    edges = [(pts[i], pts[(i + 1) % len(pts)]) for i in range(len(pts))]
    vert = [(a[0], min(a[1], b[1]), max(a[1], b[1])) for a, b in edges if a[0] == b[0]]
    ys = [v[1] for v in vert] + [v[2] for v in vert]
    for j in range(int(min(ys)), int(max(ys))):
        yc = j + 0.5
        xs = sorted(x for x, y0, y1 in vert if y0 <= yc < y1)
        for a, b in zip(xs[0::2], xs[1::2]):
            for i in range(int(round(a)), int(round(b))):
                cells.add((i, j))
    return cells


def raster_rect(r):
    x0, y0, x1, y1 = r
    if x1 - x0 < 1e-9:       # zero-width plane: represent as 1-cell line
        return {(int(round(x0 * S)), j) for j in range(int(y0 * S), int(y1 * S))}
    return {(i, j) for i in range(int(round(x0 * S)), int(round(x1 * S)))
            for j in range(int(round(y0 * S)), int(round(y1 * S)))}


def main():
    out = {"units": "m", "origin_px": [OX, OY], "scale_m_per_px": K, "rooms": {}, "walls": {},
           "openings": {}, "windows": {}}
    report = []

    # --- rooms -------------------------------------------------------------
    room_cells = {}
    for n, p in ROOMS_PX.items():
        m = [[X(x), Y(y)] for x, y in p]
        area = poly_area_px(p) * K * K
        room_cells[n] = raster_poly(p)
        out["rooms"][n] = {"polygon_m": m, "area_m2": round(area, 2), "plan_area_m2": PLAN_AREA[n]}
        report.append((n, area, PLAN_AREA[n], area / PLAN_AREA[n]))

    # --- walls -------------------------------------------------------------
    wall_cells = set()
    wcell_by = {}
    for n, (r, kind, note) in WALLS_PX.items():
        x0, y0, x1, y1 = rect_m(r)
        horiz = (x1 - x0) >= (y1 - y0)
        t = round((y1 - y0) if horiz else (x1 - x0), 3)
        if horiz:
            cl = [[x0, round((y0 + y1) / 2, 3)], [x1, round((y0 + y1) / 2, 3)]]
        else:
            cl = [[round((x0 + x1) / 2, 3), y0], [round((x0 + x1) / 2, 3), y1]]
        out["walls"][n] = {"bbox_m": [x0, y0, x1, y1], "centreline_m": cl, "thickness_m": t,
                           "class": kind, "note": note}
        c = raster_rect(r)
        wcell_by[n] = c
        wall_cells |= c

    # --- openings ----------------------------------------------------------
    open_cells = set()
    for n, (r, kind, note) in OPENINGS_PX.items():
        x0, y0, x1, y1 = rect_m(r)
        out["openings"][n] = {"bbox_m": [x0, y0, x1, y1], "kind": kind, "note": note,
                              "clear_width_m": round(max(x1 - x0, y1 - y0), 3)}
        open_cells |= raster_rect(r)

    for n, (wall, axis, a, b, note) in WINDOWS_PX.items():
        out["windows"][n] = {"wall": wall, "axis": axis,
                             "from_m": X(a) if axis == "x" else Y(b),
                             "to_m": X(b) if axis == "x" else Y(a),
                             "width_m": round((b - a) * K, 3), "note": note}

    # --- checks ------------------------------------------------------------
    all_room = {}
    for n, cs in room_cells.items():
        for c in cs:
            if c in all_room:
                report.append(("ROOM OVERLAP", n, all_room[c], 0))
                break
            all_room[c] = n
    cut = wall_cells & open_cells          # openings carve through the solid wall rects
    wall_cells = wall_cells - open_cells
    print(f"wall cells carved by openings: {len(cut)}")
    overlap_rw = [c for c in all_room if c in wall_cells]
    leaks = []
    for (i, j), n in all_room.items():
        for d in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nb = (i + d[0], j + d[1])
            if nb in all_room or nb in wall_cells or nb in open_cells:
                continue
            leaks.append((n, nb))
    ow = [c for c in open_cells if c in wall_cells]

    print("== ROOM AREAS (model vs printed plan) ==")
    for n, a, pa, ratio in report:
        print(f"  {n:36s} model {a:6.2f}  plan {pa:6.2f}  ratio {ratio:5.2f}")
    print(f"\nroom/wall cell overlaps : {len(overlap_rw)}")
    print(f"leak cells (room edge not sealed by wall/opening): {len(leaks)}")
    for n, nb in leaks[:20]:
        print("   leak", n, "cell(px)", (nb[0] / S, nb[1] / S), "-> world", (X(nb[0] / S), Y(nb[1] / S)))

    # exterior sealing: every OPENING of kind 'int' must touch >=2 distinct rooms
    print("\n== OPENING connectivity ==")
    for n, (r, kind, note) in OPENINGS_PX.items():
        oc = raster_rect(r)
        touch = set()
        for (i, j) in oc:
            for d in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nb = (i + d[0], j + d[1])
                if nb in all_room:
                    touch.add(all_room[nb])
        # zero-width planes touch rooms on the plane itself
        if r[2] - r[0] < 1e-9:
            for j in range(int(r[1] * S), int(r[3] * S)):
                for dx in (-1, 0):
                    c = (int(round(r[0] * S)) + dx, j)
                    if c in all_room:
                        touch.add(all_room[c])
        print(f"  {n:16s} {kind}  touches {sorted(touch)}")

    # --- sketch cross-check -----------------------------------------------
    print("\n== SKETCH CROSS-CHECK (sketch mm  vs  plan-trace mm) ==")
    chk = [
        ("49/2 west wall length",            8700, (479.5 - 40) * K * 1000),
        ("49/2 north width",                 3250, (218.5 - 54) * K * 1000),
        ("49/2 east wall (north section)",   3100, (197 - 40) * K * 1000),
        ("step to 49/7 face (vertical)",      150, (197 - 189) * K * 1000),
        ("wall W15 left piece (to door)",    1700, (318 - 230) * K * 1000),
        ("49/2|49/6 partition face",         3250, (352 - 189) * K * 1000),
        ("hallway north wall",               3200, (530 - 369) * K * 1000),
        ("hallway south wall",               2050, (534 - 427) * K * 1000),
        ("kitchen N wall west piece",         980, (274 - 225) * K * 1000),
        ("kitchen N wall east piece",        1020, (364.5 - 313) * K * 1000),
        ("kitchen width",                    2600, (360.5 - 229) * K * 1000),
        ("kitchen depth",                    2577, (570.5 - 440) * K * 1000),
        ("49/1 south width",                 2587, (218.5 - 87) * K * 1000),
        ("49/1 east wall height",            2350, (571 - 452) * K * 1000),
        ("49/2 south wall to 49/1 door",     2350, (172 - 54) * K * 1000),
        ("49/1 north wall (door to jog)",    2046, (172 - 69) * K * 1000),
        ("49/1 west face upper + lower",     908.3 + 815.7, (570.5 - 486.5) * K * 1000),
        ("kitchen nib / pier step",           360, (452 - 434) * K * 1000),
    ]
    for nme, sk, pl in chk:
        print(f"  {nme:36s} sketch {sk:7.0f}  trace {pl:7.0f}  d {pl - sk:+6.0f} mm")

    here = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(here, "coordinates.json"), "w") as f:
        json.dump(out, f, indent=1)
    print("\nwrote coordinates.json")


if __name__ == "__main__":
    main()
