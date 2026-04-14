"""SC#2 + SC#3 grep-invariant tests (Plan 04-07).

Locks Phase 4's "no client-side 3D reconstruction from focal length" gate
(SC#2 / DET-3D-05) and the "single projection entrypoint" gate
(SC#3 / DET-3D-06) as automated tests.

These tests are belt-and-suspenders coverage at the phase-exit boundary --
Plan 02 / 03 ship per-module invariants in tests/perception/test_geometry.py;
this file re-asserts them at the package level so the SC gates remain locked
even if a future refactor moves files between modules.
"""
from __future__ import annotations

import re
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]


def test_detection_boxes_has_no_focal_math():
    """SC#2 / DET-3D-05: DetectionBoxes.ts renders verbatim from wire format;
    no focal-length / back-projection / fovToFocal math leaked into the client."""
    tgt = _REPO_ROOT / "frontend" / "src" / "components" / "DetectionBoxes.ts"
    assert tgt.exists(), f"expected DetectionBoxes.ts at {tgt}"
    txt = tgt.read_text()
    forbidden = ["focal", "backProject", "projectBox", "fovToFocal"]
    offenders: list[str] = []
    for token in forbidden:
        # Case-sensitive match (FOV survives in Phase 2 docstrings/comments;
        # the focal-length tokens are the actual SC#2 violation surface).
        if token in txt:
            offenders.append(f"{tgt.name}: forbidden token {token!r}")
    assert offenders == [], (
        f"DetectionBoxes.ts must render OBBs verbatim from wire format "
        f"(DET-3D-05 / SC#2): {offenders}"
    )


def test_legacy_fov_deg_absent_from_perception():
    """SC#3 / DET-3D-06: ``_LEGACY_FOV_DEG`` absent from src/perception/ tree."""
    root = _REPO_ROOT / "src" / "perception"
    offenders = [
        str(p) for p in root.rglob("*.py") if "_LEGACY_FOV_DEG" in p.read_text()
    ]
    assert offenders == [], f"_LEGACY_FOV_DEG still present in: {offenders}"


def test_cloud_configs_absent_from_perception_modules():
    """Pitfall 10 / SC#3: ``CLOUD_CONFIGS`` token must not appear in the
    perception package; ``cloud_config`` module must not be imported by any
    perception module."""
    root = _REPO_ROOT / "src" / "perception"
    bad_token_hits: list[str] = []
    bad_import_hits: list[str] = []
    for py in root.rglob("*.py"):
        txt = py.read_text()
        if "CLOUD_CONFIGS" in txt:
            bad_token_hits.append(str(py))
        if re.search(
            r"^\s*(from\s+src\.bridge\.cloud_config|import\s+src\.bridge\.cloud_config)",
            txt,
            re.MULTILINE,
        ):
            bad_import_hits.append(str(py))
    assert bad_token_hits == [], (
        f"CLOUD_CONFIGS token in perception package: {bad_token_hits}"
    )
    assert bad_import_hits == [], (
        f"cloud_config imported by perception module: {bad_import_hits}"
    )


def test_math_tan_radians_in_geometry_only():
    """SC#3 / DET-3D-06: executable ``math.tan(`` / ``math.radians(`` calls
    appear in src/perception/ only inside src/perception/geometry.py.

    Lines that begin (after stripping leading whitespace) with a comment
    or docstring marker are skipped -- the ban covers EXECUTABLE math only,
    per Pitfall 9 (grep false-positive guard)."""
    root = _REPO_ROOT / "src" / "perception"
    pattern = re.compile(r"math\.(tan|radians)\s*\(")
    allowed = {"geometry.py"}
    offenders: list[str] = []
    for py in root.rglob("*.py"):
        for i, line in enumerate(py.read_text().split("\n"), start=1):
            stripped = line.lstrip()
            if stripped.startswith(("#", '"""', "'''", '"', "'")):
                continue
            if pattern.search(line) and py.name not in allowed:
                offenders.append(f"{py}:{i}:{line.strip()}")
    assert offenders == [], (
        f"math.tan/math.radians outside src/perception/geometry.py: {offenders}"
    )
