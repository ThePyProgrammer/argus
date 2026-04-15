"""DET-MODELS-08 — LICENSES.md content verification (Plan 05-08 activation).

LICENSES.md was created by Plan 05-02. These tests verify it has the
required entries + NC compliance mechanism section.
"""
from __future__ import annotations

from pathlib import Path


LICENSES_PATH = Path(__file__).parent.parent / "LICENSES.md"


def test_licenses_md_exists() -> None:
    assert LICENSES_PATH.is_file(), f"LICENSES.md missing at {LICENSES_PATH}"


def test_boxer_cc_by_nc_present() -> None:
    content = LICENSES_PATH.read_text()
    assert "CC-BY-NC-4.0" in content
    assert "facebook/BoxeR" in content or "facebookresearch/boxer" in content


def test_agpl_apache_mit_entries_present() -> None:
    content = LICENSES_PATH.read_text()
    # Per D-14 schema — all three SPDX tags must appear for the corresponding deps.
    assert "AGPL-3.0" in content   # Ultralytics YOLOv11
    assert "Apache-2.0" in content  # RT-DETRv2 (and many others)
    assert "MIT" in content        # ONNX Runtime, FastAPI


def test_nc_compliance_section_present() -> None:
    content = LICENSES_PATH.read_text()
    assert "## NC Compliance Mechanism" in content or "NC Compliance Mechanism" in content
