---
phase: quick
plan: 260324-ffy
type: execute
wave: 1
depends_on: []
files_modified:
  - frontend/src/stores/metricsStore.ts
  - frontend/src/components/SceneViewer.tsx
autonomous: true
must_haves:
  truths:
    - "Selecting Voxel Grid or Mesh persists across page reload"
    - "Toggling output hidden persists across page reload"
    - "SceneViewer initializes with the persisted output mode visible (not always Point Cloud)"
  artifacts:
    - path: "frontend/src/stores/metricsStore.ts"
      provides: "localStorage read on init, localStorage write on set"
    - path: "frontend/src/components/SceneViewer.tsx"
      provides: "Respects persisted outputMode on mount instead of hardcoding cloud"
  key_links:
    - from: "metricsStore.ts"
      to: "localStorage"
      via: "getItem on init, setItem in setOutputMode/setOutputHidden"
      pattern: "localStorage\\.(get|set)Item.*outputMode"
    - from: "SceneViewer.tsx"
      to: "metricsStore"
      via: "reads outputMode on mount for initial visibility"
      pattern: "useMetricsStore\\.getState\\(\\)\\.outputMode"
---

<objective>
Persist outputMode and outputHidden across page reloads using localStorage.

Purpose: Currently reloading always resets to Point Cloud mode, losing the user's selection.
Output: metricsStore reads/writes localStorage; SceneViewer respects persisted mode on mount.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@frontend/src/stores/metricsStore.ts
@frontend/src/components/SceneViewer.tsx
</context>

<tasks>

<task type="auto">
  <name>Task 1: Persist outputMode and outputHidden in metricsStore via localStorage</name>
  <files>frontend/src/stores/metricsStore.ts</files>
  <action>
    1. Add two localStorage keys: `c2-outputMode` and `c2-outputHidden`.

    2. Update initial state to read from localStorage:
       - `outputMode`: read `localStorage.getItem('c2-outputMode')` — if value is one of 'cloud', 'voxel', 'mesh', use it; otherwise default to 'cloud'.
       - `outputHidden`: read `localStorage.getItem('c2-outputHidden')` — if value is 'true', use true; otherwise default to false.

    3. Update `setOutputMode` setter to also call `localStorage.setItem('c2-outputMode', mode)` before the `set()` call.

    4. Update `setOutputHidden` setter to also call `localStorage.setItem('c2-outputHidden', String(hidden))` before the `set()` call.

    Keep changes minimal — only touch the two setters and the two initial values.
  </action>
  <verify>
    <automated>cd /home/prannayag/pragnition/robotics/dimensional-applications/frontend && npx tsc --noEmit 2>&1 | head -20</automated>
  </verify>
  <done>metricsStore initializes outputMode/outputHidden from localStorage and writes back on every change. TypeScript compiles clean.</done>
</task>

<task type="auto">
  <name>Task 2: SceneViewer respects persisted outputMode on mount</name>
  <files>frontend/src/components/SceneViewer.tsx</files>
  <action>
    In the useEffect where output mode managers are initialized (around line 170-171):

    1. Replace the hardcoded `let currentMode: 'cloud' | 'voxel' | 'mesh' = 'cloud';` with `let currentMode = useMetricsStore.getState().outputMode;` to read the current (persisted) mode.

    2. Replace the hardcoded `pointCloudManager.setVisible(true);` with logic that sets the correct manager visible based on currentMode:
       ```
       const initialManager = getManager(currentMode);
       initialManager.setVisible(true);
       ```
       This ensures that if the persisted mode is 'voxel', the voxelManager is made visible on mount (not pointCloudManager).

    3. Also check `useMetricsStore.getState().outputHidden` — if true, do NOT set any manager visible on init (the output should stay hidden).
  </action>
  <verify>
    <automated>cd /home/prannayag/pragnition/robotics/dimensional-applications/frontend && npx tsc --noEmit 2>&1 | head -20</automated>
  </verify>
  <done>SceneViewer initializes with the persisted output mode. Reloading after selecting Voxel Grid shows voxels, not point cloud. Reloading with output hidden keeps it hidden.</done>
</task>

</tasks>

<verification>
1. `cd frontend && npx tsc --noEmit` — no type errors
2. Manual test: select Voxel Grid, reload page — Voxel Grid should remain selected and visible
3. Manual test: hide output, reload page — output should remain hidden
4. Manual test: select Mesh, reload page — Mesh should remain selected
</verification>

<success_criteria>
- outputMode and outputHidden persist in localStorage under keys c2-outputMode and c2-outputHidden
- Page reload restores the last selected output mode in both the UI toggle state and the 3D scene
- Page reload restores the hidden state
- No TypeScript compilation errors
</success_criteria>

<output>
After completion, create `.planning/quick/260324-ffy-persist-output-mode-across-page-reloads/260324-ffy-SUMMARY.md`
</output>
