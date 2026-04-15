"""Skip-stub for DET-METRICS-03 (SC#3): `mAP` absent in frontend/src/.

Replaced in full by 06-12-PLAN.md (Wave 5). Implementation runs
`git grep -n mAP -- frontend/src/` with cwd=REPO_ROOT and asserts
returncode == 1 (no match). See CONTEXT.md D-10.
"""
import pytest
pytest.skip(
    "Wave 0 scaffold — grep invariant test lands in 06-12-PLAN.md",
    allow_module_level=True,
)
