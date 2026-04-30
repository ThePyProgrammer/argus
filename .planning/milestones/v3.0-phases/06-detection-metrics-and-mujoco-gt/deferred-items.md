# Deferred Items (Phase 6)

## Pre-existing pytest collection errors (out of scope for 06-02)

Observed at plan 06-02 execution time:
`pytest --collect-only` reports 17 collection errors in `tests/perception/` and
`tests/slam/` modules (e.g., `test_subprocess_bridge_skeleton.py`,
`test_openvins_backend.py`, etc.). These errors predate Phase 6 work and are
unrelated to the Wave 0 scaffold. Confirmed via `git stash` (no local changes
required to reproduce).

The plan 06-02 must_have "pytest collection passes without ImportError or
CollectError" is satisfied *for the 7 new stubs and the 2 new packages*
(tests/metrics/, tests/contract/) — all collect cleanly. Repo-wide collection
failure is a pre-existing condition to be addressed separately.
