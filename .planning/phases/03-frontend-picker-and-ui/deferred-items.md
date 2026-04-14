# Phase 03 — Deferred Items (out-of-scope discoveries)

## From Plan 03-06

- **`rerun` module not installed in dev env** — `python -c "import src.main"` fails on `import rerun as rr` at `src/main.py:36`. Pre-existing condition (reproduces on baseline before Plan 03-06 changes via `git stash` test). NOT caused by this plan; AST parse of `src/main.py` succeeds. Recommend a dev-env install task or making the rerun import optional in a future infra plan. Out of scope for 03-06 (which only touches the restart block at lines 491-580).
- **`tests/perception/test_lifter_routes.py` not present** — Plan 03-06 verification block lists this file but it is created in a different plan within Phase 03 (the lifter REST routes plan, see CONTEXT D-10). Run that plan's tests after that plan ships; for 03-06 the worker_pool test pair is the authoritative verification.
