---
phase: quick
plan: 260324-hb0
subsystem: scene-rendering
tags: [glb, mujoco, materials, frontend-toggle]
key-files:
  created:
    - scripts/convert_scene_glb.py (parse_mujoco_materials, convert_colored_with_trimesh, --colored flag)
    - frontend/public/scene_colored.glb (19MB, 21 meshes with textures/colors)
  modified:
    - frontend/src/stores/controlStore.ts (sceneColored state, toggleSceneColored)
    - frontend/src/hooks/useSceneLoader.ts (dynamic GLB path based on sceneColored)
    - frontend/src/components/ControlPanel.tsx (Colored Scene / Grey Scene toggle button)
decisions:
  - "Texture-first, flat-color fallback: meshes with BaseColor PNG get TextureVisuals, others get face_colors from RGBA"
  - "Skip convex hulls and mat_invisible meshes (1193 of 1214 OBJs are collision geometry)"
metrics:
  duration: 4min
  completed: "2026-03-24T04:35:09Z"
  tasks: 2
  files: 5
---

# Quick Task 260324-hb0: Add Colored Scene GLB with Material Colors

Colored GLB generation from MuJoCo XML material definitions with per-mesh BaseColor textures and RGBA face colors, plus frontend toggle to switch between colored and grey scene rendering.

## What Was Done

### Task 1: Colored GLB Generation (b00b228)

Added three new components to `scripts/convert_scene_glb.py`:

- `parse_mujoco_materials(xml_path)` -- parses MuJoCo XML to extract material RGBA colors, texture file mappings, and mesh-to-material associations
- `convert_colored_with_trimesh(input_dir, output, xml_path)` -- loads OBJ meshes, applies textures (via PIL/trimesh TextureVisuals) or flat RGBA face colors, skips convex hulls and invisible materials
- `--colored` and `--xml` CLI flags for additive colored GLB generation

Result: 21 visual meshes exported (13 textured + 8 flat colored), 1193 convex/invisible skipped. Output: 19MB `scene_colored.glb` vs 4.6MB grey `scene.glb`.

### Task 2: Frontend Toggle (a28d18f)

- `controlStore.ts`: Added `sceneColored: boolean` state and `toggleSceneColored()` action
- `useSceneLoader.ts`: Subscribes to `sceneColored`, loads `/scene_colored.glb` or `/scene.glb` dynamically. Cleanup removes old scene from parent before re-loading with new URL.
- `ControlPanel.tsx`: "Colored Scene" / "Grey Scene" toggle button, conditionally rendered only when scene is visible. Green background (#1b5e20) when colored active.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] trimesh not in project dependencies**
- **Found during:** Task 1
- **Issue:** trimesh and pillow were not in pyproject.toml dependencies, `uv run` could not import them
- **Fix:** Ran `uv add trimesh pillow` to add to project dependencies
- **Files modified:** pyproject.toml, uv.lock

**2. [Rule 3 - Blocking] dimos/ directory not available in git worktree**
- **Found during:** Task 1
- **Issue:** The `dimos/` data directory is not git-tracked, so it does not exist in the worktree
- **Fix:** Used `--xml` and `--input-dir` flags with absolute paths pointing to main repo data directory
- **Files modified:** None (runtime workaround)

## Verification

- `frontend/public/scene_colored.glb` exists (19MB, 21 meshes)
- `frontend/public/scene.glb` exists unchanged (4.6MB)
- TypeScript compiles with no errors in modified files (pre-existing errors in DetectionBoxes/SceneViewer/useWebSocket are unrelated)

## Known Stubs

None -- all data paths are wired.

## Self-Check: PASSED

All 6 files verified present. Both commits (b00b228, a28d18f) confirmed in git log.
