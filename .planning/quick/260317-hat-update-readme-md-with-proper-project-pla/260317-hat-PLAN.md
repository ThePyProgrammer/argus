---
phase: quick
plan: 260317-hat
type: execute
wave: 1
depends_on: []
files_modified: [README.md]
autonomous: true
requirements: [SIM-01, SIM-02, SIM-03, SIM-04, SLAM-01, SLAM-02, SLAM-03, SLAM-04, EXPL-01, EXPL-02, EXPL-03, COORD-01, COORD-02, COORD-03, MERGE-01, MERGE-02, MERGE-03, MERGE-04, VIZ-01, VIZ-02, VIZ-03]

must_haves:
  truths:
    - "README accurately describes the multi-robot 3D reconstruction project, not just a generic DimOS dev environment"
    - "README conveys the project scope, architecture, and phased roadmap at a glance"
    - "README preserves existing Nix dev shell and quick-start instructions that still apply"
  artifacts:
    - path: "README.md"
      provides: "Project overview, architecture summary, roadmap, setup instructions"
      min_lines: 60
  key_links: []
---

<objective>
Rewrite README.md to accurately describe the Multi-Robot 3D Reconstruction (SimWorld) project.

Purpose: The current README describes a generic DimOS development environment. The project has been scoped into a specific multi-robot autonomous exploration and 3D reconstruction system. The README should reflect the actual project: what it builds, the technical stack, the phased roadmap, and how to get started.

Output: Updated README.md
</objective>

<execution_context>
@/home/prannayag/.claude/get-shit-done/workflows/execute-plan.md
@/home/prannayag/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/REQUIREMENTS.md
@.planning/research/SUMMARY.md
@README.md
</context>

<tasks>

<task type="auto">
  <name>Task 1: Rewrite README.md with project plan and architecture overview</name>
  <files>README.md</files>
  <action>
Rewrite README.md with the following structure. Preserve the Nix environment section and quick-start commands (they still apply), but reframe everything around the actual project.

**Title and intro:**
- Title: "Multi-Robot 3D Reconstruction (SimWorld)"
- One-paragraph summary: Two simulated Unitree Go2 quadrupeds autonomously explore a SimWorld-Robotics (UE5) environment, each running independent SLAM, merging maps into a unified real-time 3D reconstruction. Built on DimOS as the agentic robotics framework.

**Architecture section:**
- Brief description of the two-instance DimOS architecture (separate blueprint per robot, NOT fleet mode)
- Stack summary table: DimOS 0.0.11, RTAB-Map 0.23.1 (via ROS 2 Humble), OctoMap 1.10.0, Open3D 0.18+, SimWorld-Robotics (UE5)
- Key architectural insight: known spawn transforms eliminate ICP-based alignment; map merging is coordinate transform + voxel fusion

**Roadmap section:**
- 4-phase roadmap as a numbered list with brief descriptions:
  1. Simulation Bridge and Single-Robot SLAM
  2. Autonomous Exploration
  3. Multi-Robot Coordination and Map Merging
  4. Visualization and Integration
- Current status: Phase 1 (not started)

**Requirements overview:**
- Bullet list of the 5 requirement categories (Simulation Bridge, SLAM Pipeline, Autonomous Exploration, Multi-Robot Coordination, Map Merging, Visualization) with count of requirements per category
- Link to .planning/REQUIREMENTS.md for full details

**Development setup section:**
- Keep the existing Nix flake instructions (nix develop, nix develop .#isolated)
- Keep the existing pip install and dimos commands
- Keep Docker build note

**Project status section:**
- Current phase: 1 of 4
- Progress: 0%
- Link to .planning/ROADMAP.md for detailed phase plans

**Documentation table:**
- Keep the existing docs/ links table

Do NOT include emojis. Use clean, technical markdown. Keep the README concise -- aim for 80-120 lines total.
  </action>
  <verify>
    <automated>test -f README.md && wc -l README.md | awk '{if ($1 >= 60 && $1 <= 150) print "PASS: " $1 " lines"; else print "FAIL: " $1 " lines"}'</automated>
  </verify>
  <done>README.md describes the multi-robot 3D reconstruction project with architecture, roadmap, requirements overview, and preserved dev setup instructions. Line count between 60-150.</done>
</task>

</tasks>

<verification>
- README.md exists and is well-formed markdown
- Contains project title "Multi-Robot 3D Reconstruction"
- Contains architecture section with stack info
- Contains 4-phase roadmap
- Contains Nix dev shell setup instructions
- Does not contain emojis
</verification>

<success_criteria>
README.md accurately represents the multi-robot 3D reconstruction project scope, architecture, phased roadmap, and development setup. A new reader understands what the project builds, how it is structured, and how to get started.
</success_criteria>

<output>
After completion, create `.planning/quick/260317-hat-update-readme-md-with-proper-project-pla/260317-hat-SUMMARY.md`
</output>
