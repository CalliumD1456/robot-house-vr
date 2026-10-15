# Robot House VR

Ground-floor model of the Robot House, built in Blender with scripts and shown as a Meta Quest VR demo in Unity.

- `RobotHouseVRBlender/phase1..5` - phase-by-phase `bpy` build scripts (plan, shell, staircase, furniture, materials/lighting) and `phase5/bake_phase5.py` (Cycles light bake). Run in order inside Blender; units are metres, +X east, +Y north.
- `RobotHouseVRBlender/tools` - `export_unity.py` (baked scene to FBX + textures in the Unity project) and `unity_rpc.py` (helper for driving the Unity MCP server).
- `RobotHouseVRUnity` - Unity 6000.6.6f1 project (URP, OpenXR, XR Interaction Toolkit, Meta OpenXR). Main scene: `Assets/Scenes/RobotHouse.unity`.

The `.blend` files are not tracked; regenerate them from the scripts. Building for Quest needs Unity's Android Build Support module.
