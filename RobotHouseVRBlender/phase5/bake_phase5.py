"""
Phase 5b - bake the lighting into textures and strip the lights (Blender 5.x, Cycles bake).

Run headless from a copy of the lit scene:
    blender -b RobotHouse_GroundFloor.blend --python bake_phase5.py

For every mesh object:
  1. smart-UV-unwrap a fresh UV map ("Bake_UV")
  2. bake DIRECT + INDIRECT + DIFFUSE colour + EMIT (no glossy) to its own image
  3. replace its material(s) with ONE unlit Emission material that shows the baked image
Then all lights are deleted, downlight fixtures are merged into one object, EEVEE is
set to cheap settings and the result is saved as RobotHouse_GroundFloor_Baked.blend
with the images packed inside.  The lit scene file is never overwritten.
"""
import math
import os
import sys
import time
import bpy

BASE = "/home/cal/Downloads/RobotHouseVR"
OUT_DIR = BASE + "/baked"
OUT_BLEND = BASE + "/RobotHouse_GroundFloor_Baked.blend"
LOG = BASE + "/baked/bake_log.txt"
SAMPLES = int(os.environ.get("BAKE_SAMPLES", "48"))
FIXED_RES = {"ARCH_Floor": 3072, "ARCH_Walls": 3072, "ARCH_Ceiling": 1024}
SKIP = ("P5F_",)                      # lit fixtures stay emissive, not baked
NO_BAKE = ("K_WallCabinets_Glass",)    # glass: replaced by a simple translucent material

os.makedirs(OUT_DIR, exist_ok=True)
_t0 = time.time()


def log(*a):
    msg = "[%6.1fs] %s" % (time.time() - _t0, " ".join(str(x) for x in a))
    print(msg)
    with open(LOG, "a") as f:
        f.write(msg + "\n")
        f.flush()


sc = bpy.context.scene
vl = bpy.context.view_layer

# ------------------------------------------------------------------ cycles / device
sc.render.engine = "CYCLES"
cy = sc.cycles
prefs = bpy.context.preferences.addons["cycles"].preferences
dev_type = None
# CPU only: the OptiX/GPU bake froze the laptop on the first (largest) object
cy.device = "CPU"
sc.render.threads_mode = "FIXED"
sc.render.threads = 6
cy.samples = SAMPLES
cy.use_adaptive_sampling = True
cy.max_bounces = 6
cy.diffuse_bounces = 4
cy.glossy_bounces = 2
cy.use_denoising = True
cy.adaptive_threshold = 0.02
log("device", cy.device, dev_type, "samples", SAMPLES)

# make everything bakeable
for o in bpy.data.objects:
    o.hide_viewport = False
    o.hide_render = False
    try:
        o.hide_set(False)
    except Exception:
        pass
for c in vl.layer_collection.children:
    c.exclude = False
    c.hide_viewport = False

targets = [o for o in bpy.data.objects
           if o.type == "MESH" and not o.name.startswith(SKIP)]
log("targets", len(targets))


def pow2_near(v, lo=128, hi=int(os.environ.get('BAKE_MAX_RES', '2048'))):
    p = lo
    while p < v and p < hi:
        p *= 2
    return p


def surface_area(ob):
    return sum(p.area for p in ob.data.polygons)


def res_for(ob):
    if ob.name in FIXED_RES:
        return FIXED_RES[ob.name]
    return pow2_near(math.sqrt(surface_area(ob)) * float(os.environ.get('BAKE_PX_PER_M', '110')))


def principled(m):
    if not m.use_nodes:
        return None
    for n in m.node_tree.nodes:
        if n.type == "BSDF_PRINCIPLED":
            return n
    return None


def prep_materials(ob, img):
    """single-user copies, metals turned diffuse (bake has no glossy), image node active"""
    for i, slot in enumerate(ob.material_slots):
        if slot.material is None:
            continue
        m = slot.material.copy()
        m.name = "bk_%s_%d" % (ob.name, i)
        slot.material = m
        b = principled(m)
        if b is not None and b.inputs["Metallic"].default_value > 0.5:
            c = list(b.inputs["Base Color"].default_value)
            b.inputs["Metallic"].default_value = 0.0
            b.inputs["Base Color"].default_value = (c[0] * 0.55, c[1] * 0.55, c[2] * 0.55, 1)
        nt = m.node_tree
        for n in nt.nodes:
            n.select = False
        tn = nt.nodes.new("ShaderNodeTexImage")
        tn.image = img
        tn.location = (-1600, -600)
        tn.select = True
        nt.nodes.active = tn


def make_uv(ob, res):
    me = ob.data
    for l in list(me.uv_layers):
        me.uv_layers.remove(l)
    me.uv_layers.new(name="Bake_UV")
    vl.objects.active = ob
    bpy.ops.object.select_all(action="DESELECT")
    ob.select_set(True)
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(angle_limit=math.radians(66), island_margin=max(0.0015, 5.0 / res),
                             area_weight=0.0, correct_aspect=True, scale_to_bounds=False)
    bpy.ops.object.mode_set(mode="OBJECT")
    me.uv_layers.active = me.uv_layers["Bake_UV"]
    me.uv_layers["Bake_UV"].active_render = True


def baked_material(name, img):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial"); out.location = (600, 0)
    em = nt.nodes.new("ShaderNodeEmission"); em.location = (300, 0)
    em.inputs["Strength"].default_value = 1.0
    tn = nt.nodes.new("ShaderNodeTexImage"); tn.location = (-100, 0)
    tn.image = img
    tn.interpolation = "Linear"
    nt.links.new(tn.outputs["Color"], em.inputs["Color"])
    nt.links.new(em.outputs["Emission"], out.inputs["Surface"])
    return m


def glass_material(name):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial"); out.location = (600, 0)
    mix = nt.nodes.new("ShaderNodeMixShader"); mix.location = (400, 0)
    mix.inputs["Fac"].default_value = 0.25
    tr = nt.nodes.new("ShaderNodeBsdfTransparent"); tr.location = (150, 100)
    em = nt.nodes.new("ShaderNodeEmission"); em.location = (150, -100)
    em.inputs["Color"].default_value = (0.75, 0.85, 0.95, 1); em.inputs["Strength"].default_value = 0.6
    nt.links.new(tr.outputs["BSDF"], mix.inputs[1])
    nt.links.new(em.outputs["Emission"], mix.inputs[2])
    nt.links.new(mix.outputs["Shader"], out.inputs["Surface"])
    try:
        m.surface_render_method = "BLENDED"
    except Exception:
        pass
    return m


# ------------------------------------------------------------------ bake loop
done = {}
order = sorted(targets, key=lambda o: -res_for(o))
for k, ob in enumerate(order):
    if ob.name.startswith(NO_BAKE):
        continue
    res = res_for(ob)
    t1 = time.time()
    path = "%s/%s.png" % (OUT_DIR, ob.name)
    if os.environ.get("RESUME") == "1" and os.path.exists(path):
        try:
            make_uv(ob, res)               # deterministic, matches the earlier run
            done[ob.name] = (None, path)
            log("resumed (already baked)", ob.name)
            continue
        except Exception as e:
            log("resume FAILED", ob.name, repr(e))
    muted = []
    if ob.name.startswith("L_Curtain"):
        # curtains are seen from the room: keep window sky/sun from burning through the pleats
        for lo in bpy.data.objects:
            if lo.type == "LIGHT" and (lo.name.startswith("P5L_Win") or lo.name.startswith("P5L_Sun")):
                lo.hide_render = True
                muted.append(lo)
    try:
        make_uv(ob, res)
        img = bpy.data.images.new("bake_" + ob.name, res, res, alpha=False, float_buffer=False)
        img.colorspace_settings.name = "sRGB"
        prep_materials(ob, img)
        bpy.ops.object.select_all(action="DESELECT")
        ob.select_set(True)
        vl.objects.active = ob
        bpy.ops.object.bake(type="COMBINED", pass_filter={"DIRECT", "INDIRECT", "DIFFUSE", "COLOR", "EMIT"},
                            margin=6, margin_type="EXTEND", use_clear=True)
        path = "%s/%s.png" % (OUT_DIR, ob.name)
        img.filepath_raw = path
        img.file_format = "PNG"
        img.save()
        done[ob.name] = (img, path)
        log("baked %2d/%d %-24s %4dpx  %.1fs" % (k + 1, len(order), ob.name, res, time.time() - t1))
    except Exception as e:
        log("FAILED", ob.name, repr(e))
    for lo in muted:
        lo.hide_render = False

# ------------------------------------------------------------------ swap in unlit baked materials
for name, (img, path) in done.items():
    ob = bpy.data.objects[name]
    im2 = bpy.data.images.load(path, check_existing=False)
    im2.name = "lm_" + name
    im2.colorspace_settings.name = "sRGB"
    im2.pack()
    if img is not None:
        bpy.data.images.remove(img)
    ob.data.materials.clear()
    ob.data.materials.append(baked_material("BK_" + name, im2))
    for p in ob.data.polygons:
        p.material_index = 0
for n in NO_BAKE:
    ob = bpy.data.objects.get(n)
    if ob:
        ob.data.materials.clear()
        ob.data.materials.append(glass_material("BK_" + n))

# ------------------------------------------------------------------ strip lights, merge fixtures
for o in list(bpy.data.objects):
    if o.type == "LIGHT":
        ld = o.data
        bpy.data.objects.remove(o, do_unlink=True)
        bpy.data.lights.remove(ld)
fx = [o for o in bpy.data.objects if o.name.startswith("P5F_Downlight_")]
if fx:
    bpy.ops.object.select_all(action="DESELECT")
    for o in fx:
        o.select_set(True)
    vl.objects.active = fx[0]
    bpy.ops.object.join()
    vl.objects.active.name = "P5F_Downlights"
    vl.objects.active.data.name = "P5F_Downlights"
    # origin back to world origin so the merged mesh keeps its place
    bpy.context.scene.cursor.location = (0, 0, 0)
    bpy.ops.object.origin_set(type="ORIGIN_CURSOR")

# ------------------------------------------------------------------ cheap EEVEE for the unlit scene
sc.render.engine = "BLENDER_EEVEE"
try:
    sc.eevee.use_raytracing = False
    sc.eevee.taa_render_samples = 32
    sc.eevee.taa_samples = 8
    sc.eevee.use_shadows = False
    sc.eevee.use_gtao = False
except Exception as e:
    log("eevee props:", e)
sc.view_settings.view_transform = "AgX"
sc.view_settings.exposure = 0.0

ce = bpy.data.objects.get("ARCH_Ceiling")
if ce:
    ce.hide_viewport = True
bpy.data.orphans_purge(do_recursive=True)

bpy.ops.wm.save_as_mainfile(filepath=OUT_BLEND)
log("saved", OUT_BLEND, "%.1f MB" % (os.path.getsize(OUT_BLEND) / 1e6))
log("DONE")
