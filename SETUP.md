# Setup on a new computer

Everything needed to continue this project is in this repo. Steps in order:

## 1. Install the tools
- **Git**, plus an SSH key added to GitHub (or HTTPS login). Then: `git clone git@github.com:CalliumD1456/robot-house-vr.git`
- **Blender** 5.2 LTS or later, plus the Blender MCP extension (so Claude can drive Blender).
- **Unity Hub** and **Unity 6000.6.6f1** with the **Android Build Support** module (Android SDK & NDK tools, OpenJDK). A different Unity version will ask to upgrade the project.
- **uv** (Python tool runner), used to run the Unity MCP server.
- **Claude desktop app**: sign in, link the session to this computer, connect GitHub, open the "Robot House VR Claude" Project, and connect the cloned folders.

## 2. Open the projects
- Blender: open `RobotHouseVRBlender/RobotHouse_GroundFloor.blend` (lit scene) or `RobotHouse_GroundFloor_Baked.blend` (baked, unlit, what gets exported to Unity).
- Unity: in Unity Hub choose Add -> `RobotHouseVRUnity`. First open takes a few minutes (it rebuilds `Library/`). The main scene is `Assets/Scenes/RobotHouse.unity`. Unity may open `SampleScene` instead; open the house scene from the Project window.
- The MCP for Unity package installs itself from `Packages/manifest.json` (OpenUPM scoped registry).

## 3. Start the Unity MCP server (after every reboot)
```
uvx --from mcpforunityserver==10.3.0 mcp-for-unity --transport http --http-url http://127.0.0.1:8080 --project-scoped-tools
```
Leave it running; Unity connects to it automatically.

## 4. Paths to edit
The Blender scripts were written on one machine and contain absolute paths (search for `/home/cal/`):
- `phase5/bake_phase5.py`: `BASE`, `OUT_DIR`, `OUT_BLEND`
- `tools/export_unity.py`: Unity project path and the baked `.blend` path
- `tools/unity_rpc.py`: none (talks to `127.0.0.1:8080`)

## 5. Building for Quest
- Unity: File -> Build Profiles -> Android, scene `RobotHouse`, then Build. Settings already in the project: OpenXR with Meta Quest feature and Touch controller profiles, Vulkan, ARM64, IL2CPP, minimum API 29.
- Headset: Developer Mode must be switched on once from the Meta Horizon phone app (needs a verified Meta developer account). Connect over USB-C and accept "Allow USB debugging".
- Install: `adb install -r Builds/RobotHouseVR.apk`, then open Library -> Unknown Sources -> Robot House VR.
- Unity's own adb is at `<UnityEditor>/Data/PlaybackEngines/AndroidPlayer/SDK/platform-tools/adb`.

## 6. Re-exporting the house from Blender to Unity
Run `tools/export_unity.py` against the baked `.blend` with Blender in background mode, then let Unity reimport. The model uses unlit baked textures, so no lights are needed in Unity.

## Not in the repo
- Reference photos, floor plan and sketch (kept in `Robot House Images`).
- QA renders, Unity `Library/`, and built `.apk` files.
