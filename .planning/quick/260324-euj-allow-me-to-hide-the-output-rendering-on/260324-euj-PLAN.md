---
phase: quick
plan: 260324-euj
type: execute
wave: 1
depends_on: []
files_modified:
  - frontend/src/App.tsx
  - frontend/src/App.css
  - frontend/src/components/SceneViewer.tsx
autonomous: true
must_haves:
  truths:
    - "User can toggle the 3D viewer / pipeline editor area hidden"
    - "When hidden, the sidebar expands to fill the full viewport width"
    - "Toggling back restores the viewer area without reloading the scene"
  artifacts:
    - path: "frontend/src/App.tsx"
      provides: "Output visibility toggle state and conditional rendering"
    - path: "frontend/src/App.css"
      provides: "Grid layout adaptation for hidden viewer mode"
  key_links:
    - from: "frontend/src/App.tsx"
      to: "frontend/src/App.css"
      via: "CSS class toggle on app-container"
      pattern: "output-hidden"
---

<objective>
Add a toggle to the C2 portal that lets the user hide the main output rendering area (3D viewer / pipeline editor, metrics panel, and camera strip), leaving only the sidebar visible and expanded to full width.

Purpose: Allow the user to reduce GPU/rendering load and focus on controls/configuration without the visual output consuming resources and screen space.
Output: A toggle button in the sidebar header that collapses/expands the output areas.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@frontend/src/App.tsx
@frontend/src/App.css
@frontend/src/components/Sidebar.tsx
@frontend/src/components/SceneViewer.tsx
@frontend/src/components/ViewToggle.tsx
</context>

<tasks>

<task type="auto">
  <name>Task 1: Add output visibility toggle state and layout switching</name>
  <files>frontend/src/App.tsx, frontend/src/App.css</files>
  <action>
In App.tsx:
1. Add `const [outputHidden, setOutputHidden] = useState(false)` state.
2. Apply CSS class `output-hidden` to the `.app-container` div when `outputHidden` is true: `className={outputHidden ? 'app-container output-hidden' : 'app-container'}`.
3. Conditionally render the viewer-area, metrics-area, and camera-strip-area divs only when `!outputHidden`. Use conditional rendering (not display:none) so the Three.js renderer is fully unmounted and GPU resources are freed.
4. Pass `outputHidden` and `setOutputHidden` as props to `<Sidebar />` (or pass just a toggle callback `onToggleOutput={() => setOutputHidden(h => !h)}` and `outputHidden`).

In App.css:
1. Add `.app-container.output-hidden` rule that changes the grid to a single column layout:
   ```css
   .app-container.output-hidden {
     grid-template-columns: 1fr;
     grid-template-rows: 1fr;
   }
   .app-container.output-hidden .sidebar-area {
     grid-column: 1;
     grid-row: 1;
     border-left: none;
   }
   ```
  </action>
  <verify>
    <automated>cd /home/prannayag/pragnition/robotics/dimensional-applications/frontend && npx tsc --noEmit 2>&1 | head -30</automated>
  </verify>
  <done>App.tsx has outputHidden state, conditionally renders output areas, applies CSS class. App.css has output-hidden grid layout. TypeScript compiles without errors.</done>
</task>

<task type="auto">
  <name>Task 2: Add toggle button to Sidebar header</name>
  <files>frontend/src/components/Sidebar.tsx</files>
  <action>
1. Update Sidebar component to accept optional props: `outputHidden?: boolean` and `onToggleOutput?: () => void`.
2. In the Sidebar header area (the top div with stats), add a toggle button:
   - Position: right side of the header, before or after the stats
   - Style: small icon-style button matching the dark theme (background: #2a2a4a, hover: #3a3a5a, border-radius: 4px, height: 28px, padding: 0 10px)
   - Label: Show an eye icon using Unicode -- when output is visible show "Hide Output" with a crossed-eye character, when hidden show "Show Output" with an eye character. Use simple text: `outputHidden ? 'Show Output' : 'Hide Output'`
   - onClick: call `onToggleOutput`
   - Only render the button if `onToggleOutput` is provided (backward compatible)
3. The button should have `font-size: 11px`, `color: #aaa`, `font-weight: 500`, and match existing UI conventions (inline styles, dark theme palette from the codebase).
  </action>
  <verify>
    <automated>cd /home/prannayag/pragnition/robotics/dimensional-applications/frontend && npx tsc --noEmit 2>&1 | head -30</automated>
  </verify>
  <done>Sidebar has a "Hide Output" / "Show Output" toggle button in its header. Button is styled consistently with the dark theme. TypeScript compiles clean.</done>
</task>

</tasks>

<verification>
1. `cd frontend && npx tsc --noEmit` -- no type errors
2. `cd frontend && npm run build` -- production build succeeds
3. Visual: Run app, click "Hide Output" in sidebar header -- viewer/metrics/cameras disappear, sidebar fills screen. Click "Show Output" -- everything returns.
</verification>

<success_criteria>
- Toggle button visible in sidebar header
- Clicking it hides the 3D viewer, metrics panel, and camera strip
- Sidebar expands to full width when output is hidden
- Clicking again restores the full layout with working 3D scene
- No TypeScript errors, production build passes
</success_criteria>

<output>
After completion, create `.planning/quick/260324-euj-allow-me-to-hide-the-output-rendering-on/260324-euj-SUMMARY.md`
</output>
