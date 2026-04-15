"""DET-MODELS-02 — RT-DETRv2 ONNX backend tests (Wave 0 skeleton, Plan 05-04).

Plan 05-07 (Wave 2) fills in the real assertions. Until then every test is
skipped via pytest.skip at its first line so `pytest --collect-only` sees the
full coverage map while `pytest` stays green.
"""
from __future__ import annotations

import pytest


def test_construct_no_onnx_file_raises() -> None:
    pytest.skip("Plan 05-07 (Wave 2) fills in: construction raises when model.onnx missing (D-06 hint).")


def test_construct_with_onnx_file_succeeds(tmp_path) -> None:
    pytest.skip("Plan 05-07 (Wave 2) fills in: backend constructs cleanly when pinned ONNX artifact exists.")


def test_preprocess_letterbox_480x640_to_320x320() -> None:
    pytest.skip("Plan 05-07 (Wave 2) fills in: letterbox preserves aspect ratio, pads with black.")


def test_warmup_runs_one_inference() -> None:
    pytest.skip("Plan 05-07 (Wave 2) fills in: warmup(dummy_frame) returns Detections2D with inference_ms > 0.")


def test_latency_p95_under_250ms() -> None:
    pytest.skip("Plan 05-07 (Wave 2) fills in: 30-inference P95 < 250 ms on 320x320 (SC#1 proxy).")


def test_capabilities_include_framework_and_license() -> None:
    pytest.skip("Plan 05-07 (Wave 2) fills in: CAPABILITIES['framework'] == 'onnxruntime', license == 'Apache-2.0'.")


def test_thread_budget_inherits_from_thread_config() -> None:
    pytest.skip("Plan 05-07 (Wave 2) fills in: intra_op_num_threads reads _thread_config.get_default_budget (D-07).")
