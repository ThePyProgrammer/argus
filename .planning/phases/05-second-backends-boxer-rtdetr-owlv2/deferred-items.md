# Phase 5 Deferred Items

Items discovered during execution that are out of scope for the current plan but must be addressed later.

---

## Plan 05-01: optimum / transformers version conflict (for Plan 05-04 to resolve)

**Discovered:** 2026-04-15 during 05-01 execution while running `uv lock --check`.

**Issue:** The Wave 0 scaffolding plan literal `"optimum[exporters]>=1.20.0"` (D-06) is silently broken at the working-set level when combined with the existing `perception` extra pin `"transformers>=5.3.0"`:

- **optimum 1.x** (the only line that exposes the `[exporters]` extra) caps `transformers<4.54.0`. Co-installing `argus[dev]` and `argus[perception]` is unsatisfiable: `uv lock --check --resolution=highest` with `<2.0` upper bound on optimum produces "your project's requirements are unsatisfiable" (transformers 5.3 vs <4.54).
- **optimum 2.x** (currently 2.1.0) DROPPED the `exporters` extra. `uv lock` resolves to `optimum==2.1.0` and emits `warning: The package optimum==2.1.0 does not have an extra named "exporters"`. The `optimum.exporters.onnx.main_export` symbol that RESEARCH § D-06 documents is NOT importable from optimum 2.x alone — it was extracted to a separate `optimum-onnx` package.
- **`optimum-onnx`** package (the new home of `main_export` for optimum 2.x) requires `transformers<4.58`, also incompatible with the project's `transformers>=5.3.0` pin.

**Impact:** Plan 05-04 (`scripts/download_models.py`) will fail at `from optimum.exporters.onnx import main_export` when run from a `argus[dev]` install, regardless of whether the user pre-installed `argus[perception]`.

**Why deferred to Plan 05-04, not auto-fixed in 05-01:**
- Resolution requires architectural choice (downgrade transformers pin? switch to optimum-onnx + override transformers? use a separate isolated dev venv for the export step? export RT-DETRv2 ONNX out-of-band one-time and commit the artifact?).
- Plan 05-01 is pure scaffolding — its job is to land the dep token the planner specified, not to redesign the export pipeline.
- The plan author explicitly chose `optimum[exporters]>=1.20.0` as the literal token — Wave 0 acceptance criteria match it byte-for-byte. Changing the token here would break grep-based verification.
- Pre-existing `uv lock` had this exact dep token resolving with the same warning; the warning is not new noise introduced by 05-01.

**Required action in Plan 05-04 (RT-DETRv2 download script):**
1. Pick one resolution path:
   - **(A)** Bump `optimum[exporters]` constraint up; switch `dev` extra to `optimum-onnx>=0.1.0` and accept that the `dev` install profile must downgrade `transformers` (split `dev` into `dev` + `dev-export` extras or use `tool.uv.environments` markers).
   - **(B)** Run the ONNX export inside an isolated subprocess venv (mirrors D-01 BoxeR pattern): create `subprocess_venvs/rtdetrv2_export/` with its own `transformers<4.54` + `optimum[exporters]==1.27.0`, invoke `optimum-cli export onnx ...` from there. Main venv stays clean.
   - **(C)** Pre-export RT-DETRv2 ONNX once (in any environment), publish to a sha256-pinned URL, fetch in `download_models.py` via plain HTTPS — drop optimum from the dep tree entirely.
2. Update `pyproject.toml` accordingly. Update `D-06` notes in 05-RESEARCH.md if the strategy changes from "optimum.exporters.onnx.main_export at runtime."
3. Confirm `uv lock --check` resolves clean (no warnings on missing extras).

**Verification command for 05-04:**
```bash
uv lock 2>&1 | grep -i "warning\|error" | grep -v "yanked"  # must be empty
uv run python -c "from optimum.exporters.onnx import main_export; print('OK')"  # must succeed
```
