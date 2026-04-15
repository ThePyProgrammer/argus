"""DET-MODELS-08 — LICENSES.md content verification (Wave 0 skeleton, Plan 05-04).

Unlike the other Wave 0 skeletons, this test ALREADY has an implementation
after Plan 05-02 lands (LICENSES.md is created in that plan). We still use
pytest.skip stubs here so Wave 0 validation is clean across all 7 files;
Plan 05-02 removes these skips in its own commit.
"""
from __future__ import annotations

from pathlib import Path

import pytest


LICENSES_PATH = Path(__file__).parent.parent / "LICENSES.md"


def test_licenses_md_exists() -> None:
    pytest.skip("Plan 05-02 fills in: simple file existence check.")


def test_boxer_cc_by_nc_present() -> None:
    pytest.skip("Plan 05-02 fills in: LICENSES.md contains 'CC-BY-NC-4.0'.")


def test_agpl_apache_mit_entries_present() -> None:
    pytest.skip("Plan 05-02 fills in: LICENSES.md lists AGPL-3.0, Apache-2.0, MIT rows.")


def test_nc_compliance_section_present() -> None:
    pytest.skip("Plan 05-02 fills in: 'NC Compliance Mechanism' H2 section exists.")
