"""DET-METRICS-03 SC#3: `mAP` and related tokens are forbidden in UI code.

Enforces CONTEXT D-10:
- `git grep -n mAP -- frontend/src/` MUST return no matches in production UI
  source (test files under `frontend/src/**/__tests__/` are excluded because
  they legitimately enumerate the forbidden-token list as string literals for
  their own assertions — they are NOT rendering paths).
- `map_50`, `map_75`, `mean_average_precision` likewise.
- The runtime guard `_assert_no_map_keys` + `_FORBIDDEN_METRIC_KEYS`
  MUST remain declared in backend/web/streaming_viz.py (removal of the
  runtime guard would defeat D-10 dual enforcement).

Replaces Wave 0 scaffold (tests/contract/test_no_map_in_ui.py).
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]


def _git_grep(pattern: str, *pathspecs: str) -> subprocess.CompletedProcess:
    """Run `git grep -n <pattern> -- <pathspecs...>` with defensive cwd.

    Per Pitfall 5: accept returncode in {0, 1}; anything else (>=2) is
    a test infrastructure error, not a policy failure.

    Uses git pathspec exclusion syntax (`:!path`) to scope OUT
    frontend/src/**/__tests__/ — those test files legitimately list the
    forbidden tokens as string literals in their own invariant assertions,
    which is not a UI-rendering leak and must not trip this check.
    """
    result = subprocess.run(
        ["git", "grep", "-n", pattern, "--", *pathspecs],
        cwd=REPO_ROOT,
        capture_output=True,
    )
    if result.returncode not in (0, 1):
        pytest.fail(
            f"git grep returned {result.returncode} (expected 0 or 1); "
            f"stderr={result.stderr.decode(errors='replace')}"
        )
    return result


@pytest.mark.parametrize("token", ["mAP", "map_50", "map_75", "mean_average_precision"])
def test_forbidden_token_absent_in_frontend_src(token: str) -> None:
    """SC#3: forbidden tokens must not appear in frontend/src/ production source.

    Scope excludes `frontend/src/**/__tests__/` — those test files assert on
    the forbidden-token vocabulary itself and legitimately contain the
    strings. They are not rendering paths, so they cannot leak `mAP` to UI.
    """
    result = _git_grep(
        token,
        "frontend/src/",
        ":!frontend/src/**/__tests__/**",
    )
    # returncode == 1 means "no match" — the invariant holds.
    # returncode == 0 means "match found" — the invariant is violated.
    assert result.returncode == 1, (
        f"Forbidden token `{token}` found in frontend/src/ (non-test):\n"
        f"{result.stdout.decode(errors='replace')}"
    )


def test_runtime_guard_declared_in_streaming_viz() -> None:
    """D-10 belt-and-suspenders: the payload-time runtime guard MUST be
    present in backend/web/streaming_viz.py. Protects against a regression
    that removes the runtime guard while leaving this grep test in place
    (which would yield a false-green SC#3 if future UI code evaded the
    grep scope)."""
    src = (REPO_ROOT / "backend" / "web" / "streaming_viz.py").read_text(encoding="utf-8")
    assert "_FORBIDDEN_METRIC_KEYS" in src, (
        "Runtime guard set `_FORBIDDEN_METRIC_KEYS` missing from "
        "backend/web/streaming_viz.py (Plan 08 invariant)"
    )
    assert "_assert_no_map_keys" in src, (
        "Runtime guard function `_assert_no_map_keys` missing from "
        "backend/web/streaming_viz.py (Plan 08 invariant)"
    )
