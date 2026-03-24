---
phase: quick
plan: 260324-gov
type: execute
wave: 1
depends_on: []
files_modified:
  - frontend/src/components/SliderField.tsx
  - frontend/src/components/SliderField.css
  - frontend/src/components/ParameterPanel.tsx
  - frontend/src/components/pipeline/NodeInspector.tsx
  - frontend/src/components/ControlPanel.tsx
autonomous: true
requirements: []
must_haves:
  truths:
    - "SliderField component renders a styled range slider paired with an editable number input"
    - "ParameterPanel and NodeInspector use SliderField instead of inline slider+input markup"
    - "ControlPanel speed and cloud offset sliders use SliderField with showInput=false"
    - "Custom CSS gives the slider a polished dark-theme look (colored track, visible thumb, proper sizing)"
  artifacts:
    - path: "frontend/src/components/SliderField.tsx"
      provides: "Reusable slider+number input component"
    - path: "frontend/src/components/SliderField.css"
      provides: "Custom range slider styling for dark theme"
  key_links:
    - from: "frontend/src/components/ParameterPanel.tsx"
      to: "frontend/src/components/SliderField.tsx"
      via: "import SliderField"
    - from: "frontend/src/components/pipeline/NodeInspector.tsx"
      to: "frontend/src/components/SliderField.tsx"
      via: "import SliderField"
    - from: "frontend/src/components/ControlPanel.tsx"
      to: "frontend/src/components/SliderField.tsx"
      via: "import SliderField"
---

<objective>
Extract the duplicated slider + editable number field pattern into a reusable SliderField component with polished dark-theme styling, then replace all 4 slider instances across the codebase.

Purpose: Eliminate code duplication (ParameterPanel and NodeInspector have near-identical 35-line slider blocks) and improve visual quality with custom CSS track/thumb styling.
Output: SliderField.tsx component, SliderField.css styles, 3 updated consumer files.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@frontend/src/components/ParameterPanel.tsx (lines 73-111 — slider+number pattern)
@frontend/src/components/pipeline/NodeInspector.tsx (lines 134-176 — slider+number pattern)
@frontend/src/components/ControlPanel.tsx (lines 103-111 — speed slider, lines 329-342 — cloud offset sliders)
</context>

<tasks>

<task type="auto">
  <name>Task 1: Create SliderField component with polished dark-theme CSS</name>
  <files>frontend/src/components/SliderField.tsx, frontend/src/components/SliderField.css</files>
  <action>
Create `SliderField.tsx` with these props:

```typescript
interface SliderFieldProps {
  min: number;
  max: number;
  step: number;
  value: number;
  onChange: (value: number) => void;
  label?: string;
  isInteger?: boolean;
  disabled?: boolean;
  showInput?: boolean;  // default true
  className?: string;
}
```

Implementation details:
- Range input with flex:1 and the number input at 64px width side by side (when showInput=true)
- Number input has clamping logic: clamp parsed value between min/max, skip NaN
- If isInteger is true, round value in onChange before emitting
- Apply CSS class `slider-field` to wrapper div, `slider-field__range` to range input, `slider-field__number` to number input

Create `SliderField.css` with custom range slider styling:
- Use `::-webkit-slider-runnable-track` and `::-moz-range-track` for track: height 6px, border-radius 3px, background #2a2a3e (dark track)
- Use `::-webkit-slider-thumb` and `::-moz-range-thumb` for thumb: 16px circle, background #6366f1 (indigo-500), border 2px solid #818cf8, cursor pointer, box-shadow for depth
- Thumb hover state: background #818cf8, scale(1.1) transform
- Number input styling: background #1a1a2e, color #e0e0e0, border 1px solid #444, border-radius 3px, padding 3px 5px, font-size 11px, width 64px
- Focus states: border-color #6366f1 on both inputs
- Wrapper: display flex, gap 8px, align-items center
- Reset default appearance on range inputs (-webkit-appearance: none)
  </action>
  <verify>
    <automated>cd /home/prannayag/pragnition/robotics/dimensional-applications/frontend && npx tsc --noEmit --pretty 2>&1 | head -30</automated>
  </verify>
  <done>SliderField.tsx exports a working React component, SliderField.css provides polished dark-theme slider styling with custom track/thumb, TypeScript compiles without errors</done>
</task>

<task type="auto">
  <name>Task 2: Replace all slider instances with SliderField</name>
  <files>frontend/src/components/ParameterPanel.tsx, frontend/src/components/pipeline/NodeInspector.tsx, frontend/src/components/ControlPanel.tsx</files>
  <action>
**ParameterPanel.tsx** (lines 73-111): Replace the entire `{(prop.type === 'number' || prop.type === 'integer') && (...)}` block with:
```tsx
<SliderField
  min={prop.minimum ?? 0}
  max={prop.maximum ?? 1}
  step={prop.type === 'integer' ? 1 : ((prop.maximum ?? 1) - (prop.minimum ?? 0)) / 100}
  value={currentValue as number}
  onChange={(val) => handleParamChange(key, val, prop.live_tunable)}
  isInteger={prop.type === 'integer'}
/>
```
Add `import SliderField from './SliderField'` and `import './SliderField.css'` at top.

**NodeInspector.tsx** (lines 134-176): Same replacement pattern:
```tsx
<SliderField
  min={(prop.minimum as number) ?? 0}
  max={(prop.maximum as number) ?? 1}
  step={prop.type === 'integer' ? 1 : (((prop.maximum as number) ?? 1) - ((prop.minimum as number) ?? 0)) / 100}
  value={currentValue as number}
  onChange={(val) => handleParamChange(key, val, !!prop.live_tunable)}
  isInteger={prop.type === 'integer'}
/>
```
Add `import SliderField from '../SliderField'` and `import '../SliderField.css'` at top. Note: NodeInspector is in `pipeline/` subdirectory.

**ControlPanel.tsx** — Speed slider (lines 103-111): Replace with:
```tsx
<SliderField min={0.1} max={5.0} step={0.1} value={simSpeed} onChange={(val) => handleSpeedChange({ target: { value: String(val) } } as any)} showInput={false} />
```
Actually, check if handleSpeedChange can be simplified. If it just does `setSimSpeed(parseFloat(e.target.value))`, pass the setter directly: `onChange={(val) => setSimSpeed(val)}` and remove the synthetic event wrapper. If it does more, keep the wrapper.

**ControlPanel.tsx** — Cloud offset sliders (lines 329-342): Replace each axis slider with:
```tsx
<SliderField
  min={-10} max={10} step={0.1}
  value={cloudOffset[i]}
  onChange={(val) => {
    const newOffset: [number, number, number] = [...cloudOffset];
    newOffset[i] = val;
    setCloudOffset(newOffset);
  }}
  showInput={false}
/>
```
Keep the axis label and value display divs that wrap each slider — only replace the `<input type="range">` element.

Add `import SliderField from './SliderField'` and `import './SliderField.css'` at top of ControlPanel.tsx.
  </action>
  <verify>
    <automated>cd /home/prannayag/pragnition/robotics/dimensional-applications/frontend && npx tsc --noEmit --pretty 2>&1 | head -30 && echo "---BUILD CHECK---" && npx vite build --mode development 2>&1 | tail -5</automated>
  </verify>
  <done>All 4 slider instances replaced with SliderField. No duplicate slider+input markup remains in ParameterPanel, NodeInspector, or ControlPanel. TypeScript compiles, Vite builds successfully. Slider behavior is identical to before (clamping, integer detection, onChange propagation).</done>
</task>

</tasks>

<verification>
1. `cd frontend && npx tsc --noEmit` passes with zero errors
2. `cd frontend && npx vite build --mode development` succeeds
3. Grep confirms no remaining inline `type="range"` inputs in the 3 consumer files: `grep -n 'type="range"' frontend/src/components/ParameterPanel.tsx frontend/src/components/pipeline/NodeInspector.tsx frontend/src/components/ControlPanel.tsx` returns empty
4. SliderField.tsx exists and exports the component
</verification>

<success_criteria>
- SliderField component is reusable with min/max/step/value/onChange props plus optional label, isInteger, disabled, showInput
- Custom CSS provides polished dark-theme styling (indigo accent color, visible thumb, proper track height)
- All 4 slider instances across 3 files replaced
- Zero TypeScript errors, successful Vite build
</success_criteria>

<output>
After completion, create `.planning/quick/260324-gov-extract-slider-number-field-as-reusable-/260324-gov-SUMMARY.md`
</output>
