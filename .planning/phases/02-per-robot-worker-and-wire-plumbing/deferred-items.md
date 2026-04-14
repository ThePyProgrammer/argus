## Deferred: pre-existing test-ordering bug in tests/perception

Running `pytest tests/perception/test_protocol_contracts.py tests/perception/test_registry.py`
together yields 7 registry failures — `ValueError: CAPABILITIES['input_type'] must be DetectorInput, got DetectorInput`.
Cause: `test_perception_types_import_does_not_load_heavy_deps` deletes `src.perception.types`
from sys.modules and re-imports it, invalidating `DetectorInput` class identity for downstream
tests that imported `DetectorInput` at module scope. Pre-existing on base commit 1a804fe.

Each file runs green in isolation (18/18 and 16/16). Out of scope for Plan 02-01.
