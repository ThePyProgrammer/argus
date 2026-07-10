# Remove Nix Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove Nix from the active Argus developer/runtime path while preserving the existing `uv`-based CLI, browser dashboard, benchmarks, frontend build, and test workflows.

**Architecture:** Keep `uv` as the Python environment and package manager, and replace the Nix wrapper with a direct `uv` wrapper. Delete the Nix flake files only after proving active workflows run outside `nix develop`. Document native system dependencies in README instead of encoding them in `flake.nix`.

**Tech Stack:** Python 3.12, `uv`, MuJoCo, Open3D, OpenCV, Rerun, FastAPI/Uvicorn/WebSockets, React/Vite/npm, Git LFS, Linux native graphics/system packages.

---

## Research Summary

Parallel repo research found:

- Active Nix runtime usage is limited to `run.sh`, `flake.nix`, and `flake.lock`.
- `README.md`, `docs/`, `scripts/`, and `pyproject.toml` currently have no active Nix references that must be edited.
- `.planning/` contains many Nix references, but they are historical planning/verification artifacts. Do not rewrite those unless the user explicitly asks to rewrite project history.
- `flake.nix` currently provides native/system dependencies, not Python dependency resolution. Python dependencies are already managed by `uv` and `pyproject.toml`.
- The user has already confirmed the core non-Nix workflow works outside `nix develop`.

The Nix-provided dependency categories to replace with OS packages/docs are:

- Python/runtime tooling: Python 3.12, compiler runtime, `pkg-config`.
- MuJoCo/OpenGL stack: OpenGL/Mesa/GLFW/X11/SDL2/udev/zlib.
- Open3D/OpenCV support: common C/C++ runtime libs plus image/GUI codecs as needed.
- Frontend: Node.js 18+ and npm; Nix did not provide these in the current flake.
- Git LFS for scene/model artifacts.

Likely legacy/optional from the flake:

- LCM and CycloneDDS: README says in-process transport replaced pLCM; no direct current import was found in active paths.
- PortAudio, GStreamer, ffmpeg, graphviz, imagemagick, pikchr, diagon: not required by the primary Argus browser dashboard or locomotion smoke benchmark unless optional tooling is used.

---

## File Structure

Modify:

- `run.sh`
  - Responsibility: convenience wrapper for running Argus from the repository root.
  - Change from `nix develop --command ...` to direct `uv run --python 3.12 argus "$@"`.

- `README.md`
  - Responsibility: user-facing setup and run instructions.
  - Add an explicit non-Nix native dependency section for Linux/Arch-CachyOS and Ubuntu/Debian.
  - Keep the existing `uv run argus ...` commands.
  - Remove no current Nix text unless a fresh grep finds active references.

Delete:

- `flake.nix`
  - Responsibility today: old Nix dev shell and devcontainer image definition.
  - Delete after `run.sh` no longer references it.

- `flake.lock`
  - Responsibility today: lockfile for deleted Nix flake.
  - Delete with `flake.nix`.

Do not modify by default:

- `.planning/**`
  - Historical planning artifacts. Nix references there document past environment issues and should remain as history.

---

### Task 1: Establish the Pre-Removal Evidence Gate

**Files:**
- Read only: `run.sh`
- Read only: `pyproject.toml`
- Read only: `README.md`
- Read only: `frontend/package.json`

- [ ] **Step 1: Confirm active Nix references before editing**

Run:

```bash
grep -RIn -E 'nix|Nix|flake\.nix|flake\.lock|nix develop|nix build' README.md docs scripts run.sh pyproject.toml Makefile frontend/package.json 2>/dev/null || true
```

Expected:

- `run.sh` is the only active runtime file with a Nix reference.
- `README.md`, `docs/`, `scripts/`, `pyproject.toml`, `Makefile`, and `frontend/package.json` either have no Nix references or only references that this plan explicitly updates.

- [ ] **Step 2: Confirm current Python CLI resolves outside Nix**

Run outside `nix develop`:

```bash
uv run --python 3.12 python -c "import mujoco, open3d, cv2, rerun; import src.main; print('ok')"
```

Expected:

```text
ok
```

If this fails, stop. Install the missing system package or Python extra first; do not remove Nix until this import gate passes.

- [ ] **Step 3: Confirm the installed console script works**

Run:

```bash
uv run --python 3.12 argus --help
```

Expected:

- Exit code 0.
- Output includes the `eval-locomotion` subcommand and flags such as `--control`, `--scene`, and `--port`.

- [ ] **Step 4: Commit nothing for this task**

This task is a read-only evidence gate. Do not commit.

---

### Task 2: Replace `run.sh` with a Direct `uv` Wrapper

**Files:**
- Modify: `run.sh`

- [ ] **Step 1: Replace the file content**

Change `run.sh` to exactly:

```bash
#!/usr/bin/env bash
set -euo pipefail

# Convenience wrapper for running Argus from the repository root.
exec uv run --python 3.12 argus "$@"
```

Implementation command if editing manually:

```bash
python - <<'PY'
from pathlib import Path
Path('run.sh').write_text('''#!/usr/bin/env bash
set -euo pipefail

# Convenience wrapper for running Argus from the repository root.
exec uv run --python 3.12 argus "$@"
''')
PY
chmod +x run.sh
```

- [ ] **Step 2: Verify the wrapper help path**

Run:

```bash
./run.sh --help
```

Expected:

- Exit code 0.
- Help output from `src.main` appears.
- No `nix` command is invoked.

- [ ] **Step 3: Verify no active Nix reference remains in `run.sh`**

Run:

```bash
! grep -nE 'nix|Nix|nix develop' run.sh
```

Expected:

- Exit code 0.
- No output.

- [ ] **Step 4: Commit the wrapper change**

```bash
git add run.sh
git commit -m "chore: run argus without nix wrapper"
```

---

### Task 3: Document Non-Nix Native Setup in README

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Add native dependency notes under Quick Start prerequisites**

In `README.md`, replace the current prerequisite list at `README.md` under `## Quick Start` / `### Prerequisites` with:

```markdown
- [uv](https://docs.astral.sh/uv/) (Python package manager)
- Python 3.12 via `uv python install 3.12`
- Node.js 18+ and npm (for the frontend build/dev server)
- Git LFS (for DimOS scene data and large fixtures)
- Native graphics/runtime libraries for MuJoCo, Open3D, and OpenCV
```

- [ ] **Step 2: Add Linux package examples immediately after prerequisites**

Insert this block after the prerequisite list and before the existing shell setup commands:

```markdown
On Arch/CachyOS, the native package baseline is typically:

```bash
sudo pacman -S --needed base-devel git-lfs nodejs npm mesa glfw-x11 libx11 libxi libxrandr libxinerama libxcursor libxfixes libxrender libxdamage libxcomposite libxext libxcb libxss libxxf86vm sdl2 zlib ffmpeg pkgconf cmake ninja
```

On Ubuntu/Debian, the equivalent baseline is typically:

```bash
sudo apt-get update
sudo apt-get install -y build-essential git-lfs nodejs npm libgl1 libglx-mesa0 libglu1-mesa libglfw3 libx11-6 libxi6 libxrandr2 libxinerama1 libxcursor1 libxfixes3 libxrender1 libxdamage1 libxcomposite1 libxext6 libxcb1 libxss1 libxxf86vm1 libsdl2-2.0-0 zlib1g ffmpeg pkg-config cmake ninja-build
```

If `uv run python -c "import mujoco, open3d, cv2, rerun"` fails, install the missing native library reported by the dynamic linker before running Argus.
```

- [ ] **Step 3: Keep the existing `uv` setup commands, but remove stale `dimos` path assumptions if present**

Ensure the Quick Start still contains these commands or their equivalent:

```bash
uv python install 3.12
uv venv --python 3.12
uv pip install -e .
```

If the README still references `./dimos` but the repository does not contain a `dimos/` directory, either remove that command or replace it with the current local dependency path. The current repository has `SimWorld-Robotics/`, not `dimos/`, so do not leave a guaranteed-broken `uv pip install -e ./dimos` command unless you first verify `./dimos` exists.

- [ ] **Step 4: Verify README has no active Nix setup instruction**

Run:

```bash
grep -nE 'nix|Nix|flake\.nix|nix develop|nix build' README.md || true
```

Expected:

- No output, unless the README intentionally says Nix is no longer required.
- Prefer no output to avoid confusing new users.

- [ ] **Step 5: Commit README setup docs**

```bash
git add README.md
git commit -m "docs: document non-nix setup requirements"
```

---

### Task 4: Remove the Nix Flake Files

**Files:**
- Delete: `flake.nix`
- Delete: `flake.lock`

- [ ] **Step 1: Confirm no active file still calls Nix**

Run:

```bash
grep -RIn -E 'nix develop|nix build|flake\.nix|flake\.lock' README.md docs scripts run.sh pyproject.toml Makefile frontend/package.json 2>/dev/null || true
```

Expected:

- No active references that instruct users or scripts to use Nix.

- [ ] **Step 2: Delete the flake files**

Run:

```bash
rm flake.nix flake.lock
```

- [ ] **Step 3: Verify deletion**

Run:

```bash
test ! -e flake.nix && test ! -e flake.lock && echo 'nix files removed'
```

Expected:

```text
nix files removed
```

- [ ] **Step 4: Commit flake removal**

```bash
git add -u flake.nix flake.lock
git commit -m "chore: remove nix flake environment"
```

---

### Task 5: Verify Backend and Benchmark Workflows Without Nix

**Files:**
- No source changes expected.

- [ ] **Step 1: Verify import gate**

Run outside `nix develop`:

```bash
uv run --python 3.12 python -c "import mujoco, open3d, cv2, fastapi, websockets, gymnasium, rerun; import src.main; print('ok')"
```

Expected:

```text
ok
```

- [ ] **Step 2: Verify wrapper command help**

Run:

```bash
./run.sh --help
```

Expected:

- Exit code 0.
- CLI help appears.

- [ ] **Step 3: Verify short static dashboard run**

Run:

```bash
timeout 30s uv run --python 3.12 argus --scene office --static --multi-max-steps 20
```

Expected:

- The command starts Argus and prints `Starting Argus at http://localhost:8000`.
- It exits via timeout with status 124, or exits cleanly if the simulation completes first.
- No error mentions missing `libGL`, `libstdc++`, `libudev`, `X11`, `GLFW`, `mujoco`, `open3d`, `uvicorn`, or `fastapi`.

- [ ] **Step 4: Verify locomotion smoke benchmark**

Run:

```bash
uv run --python 3.12 argus eval-locomotion --controller analytical_trot --scenario flat_ground --seed 101 --seed 202
```

Expected:

- Exit code 0, unless the benchmark honestly reports locomotion failure under its own criteria.
- Output includes `run_dir:`, `summary:`, and `comparison:` paths.
- Artifacts are written under `outputs/locomotion-evals/`.

- [ ] **Step 5: Verify backend tests**

Run:

```bash
uv run --python 3.12 --extra dev python -m pytest tests/ -x --timeout=30
```

Expected:

- Test collection succeeds.
- No failures caused by missing Nix/system libraries.
- If unrelated project tests fail, document the first failure and confirm it is not an environment regression before continuing.

- [ ] **Step 6: Commit nothing for this task**

This task verifies prior commits. Do not commit unless you had to fix a real issue.

---

### Task 6: Verify Frontend Workflow Without Nix

**Files:**
- No source changes expected.

- [ ] **Step 1: Install frontend dependencies with npm**

Run:

```bash
npm --prefix frontend install
```

Expected:

- Exit code 0.
- `frontend/node_modules/` exists locally but is not tracked by git.

- [ ] **Step 2: Build the frontend**

Run:

```bash
npm --prefix frontend run build
```

Expected:

- TypeScript build and Vite build succeed.
- No missing Node/npm dependency errors.

- [ ] **Step 3: Run frontend tests**

Run:

```bash
npm --prefix frontend run test
```

Expected:

- Vitest exits 0.

- [ ] **Step 4: Confirm frontend dev command remains documented**

Run:

```bash
grep -n "npm run dev" README.md frontend/package.json
```

Expected:

- README includes the frontend dev server command.
- `frontend/package.json` includes the `dev` script.

- [ ] **Step 5: Commit nothing for this task**

This task verifies prior commits. Do not commit unless you had to fix a real issue.

---

### Task 7: Final Active-Reference Audit

**Files:**
- No source changes expected unless audit finds stale active references.

- [ ] **Step 1: Audit active files for Nix references**

Run:

```bash
grep -RIn -E 'nix|Nix|flake\.nix|flake\.lock|nix develop|nix build' README.md docs scripts run.sh pyproject.toml Makefile frontend/package.json 2>/dev/null || true
```

Expected:

- No output from active user-facing docs/scripts.

- [ ] **Step 2: Audit git status**

Run:

```bash
git status --short
```

Expected:

- Only expected tracked changes are present.
- No generated folders such as `frontend/node_modules/`, frontend build output, or evaluation output are staged.

- [ ] **Step 3: If generated artifacts are untracked, leave them uncommitted**

Do not delete user data. If generated artifacts appear, verify `.gitignore` already excludes them or leave them untracked and mention them in the final report.

- [ ] **Step 4: Final commit only if stale active references were fixed**

If Task 7 required any README/docs/script cleanup, commit it:

```bash
git add README.md docs scripts run.sh pyproject.toml Makefile frontend/package.json
git commit -m "docs: remove stale nix references"
```

If no files changed, do not create an empty commit.

---

## Self-Review

### Spec Coverage

- Remove Nix runtime wrapper: Task 2.
- Remove Nix files: Task 4.
- Research hidden scope: Research Summary plus Tasks 1, 5, 6, and 7.
- Preserve working system: Tasks 5 and 6.
- Document replacement setup: Task 3.
- Avoid rewriting history: File Structure and Task 7 explicitly exclude `.planning/**` by default.

### Placeholder Scan

No `TBD`, `TODO`, `implement later`, or unspecified test steps are present. Every task has exact paths, commands, and expected outcomes.

### Type and Command Consistency

All runtime commands use `uv run --python 3.12`. The wrapper uses `argus`, matching `[project.scripts] argus = "src.main:main"` in `pyproject.toml`.
