
import bpy, os
OUT="/home/cal/Documents/RobotHouseVR/RobotHouseVRUnity/Assets/RobotHouse"
os.makedirs(OUT, exist_ok=True)
for o in bpy.data.objects:
    o.hide_viewport=False; o.hide_render=False
    try: o.hide_set(False)
    except: pass
for c in bpy.context.view_layer.layer_collection.children: c.exclude=False
meshes=[o for o in bpy.data.objects if o.type=="MESH"]
# swap emission-baked mats for Principled with base colour = baked image (FBX exporter understands this)
for o in meshes:
    for i,s in enumerate(o.material_slots):
        m=s.material
        if not m: continue
        img=None
        for n in m.node_tree.nodes:
            if n.type=="TEX_IMAGE": img=n.image
        glass = "Glass" in o.name
        nm=bpy.data.materials.new("M_"+o.name); nm.use_nodes=True
        nt=nm.node_tree; b=nt.nodes["Principled BSDF"]
        b.inputs["Roughness"].default_value=1.0
        b.inputs["Specular IOR Level"].default_value=0.0
        if glass:
            b.inputs["Base Color"].default_value=(0.75,0.85,0.95,1); b.inputs["Alpha"].default_value=0.25
        elif img:
            t=nt.nodes.new("ShaderNodeTexImage"); t.image=img
            nt.links.new(t.outputs["Color"], b.inputs["Base Color"])
        s.material=nm
for o in bpy.data.objects: o.select_set(o.type=="MESH")
bpy.ops.export_scene.fbx(filepath=OUT+"/RobotHouse_GroundFloor.fbx", use_selection=True,
    object_types={"MESH"}, apply_unit_scale=True, apply_scale_options="FBX_SCALE_ALL",
    axis_forward="-Z", axis_up="Y", path_mode="COPY", embed_textures=False,
    mesh_smooth_type="FACE", use_mesh_modifiers=True, bake_space_transform=True)
print("EXPORT_DONE", len(meshes))
