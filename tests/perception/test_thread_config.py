"""Invariant: only src/_thread_config.py may call torch.set_num_threads at module scope.

Per CONTEXT.md D-14 and research/PITFALLS.md P4 + P19: torch thread settings
must be applied process-globally via src/_thread_config.py imported first
in main.py. Any module-scope re-call elsewhere creates a thread-pool collision
that silently halves SLAM throughput when a transformer detector is added.

This is a grep-based test (per CONTEXT.md "Specifics" section). It is
intentionally simple and conservative: it flags ANY occurrence of
`torch.set_num_threads(` outside src/_thread_config.py at indent <= 4 spaces.
Function-body uses (indent > 4) are allowed but currently nonexistent.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
ALLOWED_FILE = SRC_ROOT / "_thread_config.py"

# Match `torch.set_num_threads(` at line start with at most 4 leading spaces
# (i.e., module scope or top-level class body -- never inside a function).
_MODULE_SCOPE_RE = re.compile(r"^\s{0,4}torch\.set_num_threads\s*\(")
_INTEROP_RE = re.compile(r"^\s{0,4}torch\.set_num_interop_threads\s*\(")


def _iter_python_files() -> list[Path]:
    return sorted(p for p in SRC_ROOT.rglob("*.py") if p.is_file())


@pytest.mark.parametrize("py_file", _iter_python_files(), ids=lambda p: str(p.relative_to(REPO_ROOT)))
def test_no_module_scope_set_num_threads(py_file: Path) -> None:
    """Only src/_thread_config.py may call torch.set_num_threads at module scope."""
    if py_file == ALLOWED_FILE:
        pytest.skip("src/_thread_config.py is the one allowed call site")

    text = py_file.read_text(encoding="utf-8")
    violations: list[tuple[int, str]] = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        if _MODULE_SCOPE_RE.match(line) or _INTEROP_RE.match(line):
            violations.append((lineno, line.rstrip()))

    if violations:
        details = "\n".join(f"  {py_file}:{ln}: {src}" for ln, src in violations)
        pytest.fail(
            f"Module-scope torch thread setting found outside src/_thread_config.py:\n"
            f"{details}\n"
            f"Fix: move the call into src/_thread_config.py per CONTEXT.md D-14 / Pitfall P4."
        )


def test_thread_config_module_actually_calls_set_num_threads() -> None:
    """Sanity: src/_thread_config.py MUST contain the call we forbid elsewhere."""
    text = ALLOWED_FILE.read_text(encoding="utf-8")
    assert "torch.set_num_threads" in text, (
        "src/_thread_config.py is the only allowed call site but contains no "
        "torch.set_num_threads call -- D-14 invariant is empty."
    )
    assert "torch.set_num_interop_threads" in text, (
        "src/_thread_config.py must also call torch.set_num_interop_threads(1)."
    )


# ---------------------------------------------------------------------------
# Plan 05-05: get_default_budget() public getter (D-07 — ORT consumers).
# ---------------------------------------------------------------------------


def test_get_default_budget_returns_int() -> None:
    """D-07: ORT backends read the process-global thread budget via this getter.

    Phase 1 D-04 invariant: ALL thread budget config flows through _thread_config.
    Plan 05-07's RT-DETRv2 backend sets
    ``sess_options.intra_op_num_threads = get_default_budget()`` — the backend
    MUST NOT hardcode a thread count.
    """
    from src._thread_config import _DEFAULT_BUDGET, get_default_budget

    result = get_default_budget()
    assert isinstance(result, int)
    assert result == _DEFAULT_BUDGET
    assert result >= 1
