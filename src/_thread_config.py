"""Process-global thread/inference-mode configuration.

MUST be imported as the first non-stdlib line of src/main.py, BEFORE any
module that transitively imports torch (backend.web.server, src.slam.*,
src.perception.*, ultralytics, transformers).

Per CONTEXT.md D-14 and research/ARCHITECTURE.md Decision D:
- detector_threads = max(2, C // (2 + N_robots))   [Phase 1: hardcoded default 2]
- Sets OMP/MKL/OPENBLAS env vars BEFORE torch import (oneDNN reads these once)
- Sets torch.set_num_threads + torch.set_num_interop_threads(1) AFTER env vars

Pitfall P4: oneDNN/MKL ignore torch.set_num_threads() if torch was already
called once. We must beat that race by being the first thing imported.

Pitfall P19: src/perception/detector.py:25 used to do `torch.set_num_threads(2)`
at module scope -- that call is removed; this module is the only place that
sets thread budgets at module scope.
"""

import logging
import os

_CONFIGURED = False
_DEFAULT_BUDGET = 2

logger = logging.getLogger(__name__)


def _set_env_if_absent(key: str, value: str) -> None:
    """Honor any user-supplied value; otherwise set our default."""
    if key not in os.environ:
        os.environ[key] = value


def get_detector_thread_budget(num_robots: int = 1) -> int:
    """Compute Phase 2+ per-detector thread budget.

    Phase 1: returns _DEFAULT_BUDGET (2) for any input, preserving the
    pre-Phase-1 thread setting from src/perception/detector.py:25.
    Phase 2+ may switch to the formula below by passing num_robots>=1.

    Formula (research Decision D): max(2, C // (2 + N_robots))
    """
    cpu = os.cpu_count() or 4
    return max(2, cpu // (2 + max(1, num_robots)))


def get_default_budget() -> int:
    """Return the process-global default thread budget (Phase 1 D-04 invariant).

    Phase 5 Plan 05-05 (D-07): ORT session construction in
    ``src/perception/backends/rtdetrv2_backend.py`` (Plan 05-07) reads this to
    set ``sess_options.intra_op_num_threads`` — the ORT backend MUST NOT
    hardcode a thread count (that would violate the Phase 1 invariant that
    ALL thread budget config flows through this file — see Pitfall P19).

    This is a plain public getter over the module-private ``_DEFAULT_BUDGET``
    so backends do not reach into the underscore-prefixed symbol directly.
    """
    return _DEFAULT_BUDGET


def _configure() -> None:
    global _CONFIGURED
    if _CONFIGURED:
        return

    budget = str(_DEFAULT_BUDGET)

    # Step 1: env vars BEFORE torch import (oneDNN/MKL/OpenBLAS read these once).
    _set_env_if_absent("OMP_NUM_THREADS", budget)
    _set_env_if_absent("MKL_NUM_THREADS", budget)
    _set_env_if_absent("OPENBLAS_NUM_THREADS", budget)
    _set_env_if_absent("NNPACK_DISABLE", "1")
    _set_env_if_absent("TORCH_CPP_LOG_LEVEL", "ERROR")

    # Step 2: torch settings AFTER env vars. If torch isn't installed (perception
    # extra not selected), skip silently -- the rest of the system still works.
    try:
        import torch  # noqa: PLC0415 -- intentional late import after env vars
        torch.set_num_threads(_DEFAULT_BUDGET)
        torch.set_num_interop_threads(1)
        torch_n = torch.get_num_threads()
    except ImportError:
        torch_n = "unavailable"

    logger.info(
        "thread_config: OMP=%s MKL=%s OPENBLAS=%s torch=%s torch_interop=1",
        os.environ.get("OMP_NUM_THREADS"),
        os.environ.get("MKL_NUM_THREADS"),
        os.environ.get("OPENBLAS_NUM_THREADS"),
        torch_n,
    )
    _CONFIGURED = True


_configure()
