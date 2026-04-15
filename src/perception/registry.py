"""Detector + Detection3D registries with decorator-based registration.

Two separate registries live here per CONTEXT.md D-06 and research Decision A:
  - DetectorRegistry         -> 2D detectors (YOLOv11, RT-DETRv2, OWLv2, BoxeR, ...)
  - Detection3DRegistry      -> 3D lifters (MedianDepthLifter, PointClusterLifter, ...)

Upgrades over src/slam/registry.py pattern:
  - D-05: list_backends() calls @classmethod available() -> (bool, str | None).
          Registry never invents install-hint text.
  - D-06: register() validates MANDATORY CAPABILITIES keys synchronously.
          Missing key -> ValueError at import time, loud failure.

Pitfall P9: this module imports ONLY stdlib + src.perception.types.DetectorInput.
Heavy deps (torch, ultralytics, transformers) are reached via lazy class-path
loading inside list_backends() / create() only.

Backend registration pattern (Plan 05 YOLOv11Backend):
  @detector_backend(name="yolov11", display="YOLOv11-nano")
  class YOLOv11Backend(TorchBackendMixin):
      CAPABILITIES = {
          "framework": "ultralytics",
          "license": "AGPL-3.0",
          "cpu_latency_hint_ms": 120,
          "outputs_3d_natively": False,
          "input_type": DetectorInput.RGB_ONLY,
      }
      ...
"""

from __future__ import annotations

import importlib
import logging
from typing import Any

from src.perception.types import DetectorInput

logger = logging.getLogger(__name__)


# Mandatory CAPABILITIES keys per CONTEXT.md D-06 (2D) and
# research/ARCHITECTURE.md Detection3DProtocol (3D).
_DETECTOR_REQUIRED_KEYS = (
    "framework",
    "license",
    "cpu_latency_hint_ms",
    "outputs_3d_natively",
    "input_type",
)
_DETECTOR_TYPED_KEYS: dict[str, type] = {
    "input_type": DetectorInput,
}

_DETECTION_3D_REQUIRED_KEYS = (
    "requires_depth",
    "requires_point_cloud",
    "outputs_oriented",
    "license",
)
_DETECTION_3D_TYPED_KEYS: dict[str, type] = {}


def _validate_capabilities(
    name: str,
    klass: type,
    required_keys: tuple[str, ...],
    typed_keys: dict[str, type],
    kind: str,
) -> None:
    """Enforce D-06 mandatory-key contract at register() time.

    Raises ValueError with a deterministic sorted message if any key is missing
    or has the wrong type.
    """
    caps = getattr(klass, "CAPABILITIES", None)
    if not isinstance(caps, dict):
        raise ValueError(
            f"{kind} '{name}' missing CAPABILITIES dict on {klass.__qualname__}. "
            f"Per CONTEXT.md D-06, every backend must declare CAPABILITIES."
        )
    missing = sorted(k for k in required_keys if k not in caps)
    if missing:
        raise ValueError(
            f"{kind} '{name}' ({klass.__qualname__}) missing CAPABILITIES keys: "
            f"{missing}. Required: {list(required_keys)}."
        )
    for key, expected_type in typed_keys.items():
        value = caps[key]
        if not isinstance(value, expected_type):
            raise ValueError(
                f"{kind} '{name}' CAPABILITIES['{key}'] must be "
                f"{expected_type.__name__}, got {type(value).__name__} ({value!r})."
            )


def _load_class(class_path: str) -> type | None:
    """Lazily import and return a class from its dotted path.

    Returns None if the module or class cannot be found. Callers use None
    to decide whether the backend is importable in the current environment.
    """
    try:
        module_path, class_name = class_path.rsplit(".", 1)
        module = importlib.import_module(module_path)
        return getattr(module, class_name)
    except (ImportError, AttributeError, ValueError) as exc:
        logger.debug("Cannot load %s: %s", class_path, exc)
        return None


def _probe_availability(klass: type) -> tuple[bool, str | None]:
    """Call @classmethod available() per CONTEXT.md D-05.

    If the backend class doesn't expose available() (legacy / third-party),
    default to (True, None) -- we've already imported it successfully.
    """
    probe = getattr(klass, "available", None)
    if probe is None:
        return True, None
    try:
        result = probe()
    except Exception as exc:  # defensive: a misbehaving probe must not crash the registry
        logger.warning("available() probe failed for %s: %s", klass.__qualname__, exc)
        return False, f"available() probe raised: {exc}"
    if not (isinstance(result, tuple) and len(result) == 2):
        logger.warning(
            "available() for %s must return (bool, str | None); got %r",
            klass.__qualname__,
            result,
        )
        return False, f"available() returned malformed result: {result!r}"
    return bool(result[0]), (None if result[1] is None else str(result[1]))


class DetectorRegistry:
    """Central registry for 2D detector backends (CONTEXT.md D-06).

    Default = "yolov11". Capabilities are validated at register() time; backends
    missing any mandatory CAPABILITIES key fail import loudly.
    """

    _backends: dict[str, dict] = {}
    _default: str = "yolov11"

    @classmethod
    def register(cls, name: str, display: str, class_path: str, klass: type) -> None:
        """Register a detector backend. Validates CAPABILITIES synchronously."""
        _validate_capabilities(
            name, klass, _DETECTOR_REQUIRED_KEYS, _DETECTOR_TYPED_KEYS, kind="Detector"
        )
        cls._backends[name] = {"class_path": class_path, "display": display}
        logger.debug("Registered detector backend: %s (%s)", name, class_path)

    @classmethod
    def list_backends(cls) -> list[dict]:
        """List all registered detectors with availability + capability metadata.

        Plan 05-05 D-04: honors any ``set_available`` override (session-scoped,
        used by the pool's crash handler to mark a crashed backend unavailable
        until the process restarts). The override ONLY applies when the class
        loads successfully — if the dotted class path cannot be resolved, we
        still surface ``available=False`` with a "Cannot load ..." reason,
        because evaluating the override on a missing class would be bogus.
        """
        result: list[dict] = []
        for name, info in list(cls._backends.items()):
            entry: dict[str, Any] = {"name": name, "display": info["display"]}
            klass = _load_class(info["class_path"])
            if klass is None:
                entry["available"] = False
                entry["reason"] = f"Cannot load {info['class_path']}"
                entry["capabilities"] = {}
                entry["parameter_schema"] = {}
            else:
                override = info.get("_override_available")
                if override is not None:
                    available, reason = override
                    entry["available"] = bool(available)
                    if not available:
                        entry["reason"] = reason or (
                            "Marked unavailable by set_available()."
                        )
                    entry["capabilities"] = dict(getattr(klass, "CAPABILITIES", {}))
                    entry["parameter_schema"] = dict(
                        getattr(klass, "PARAMETER_SCHEMA", {})
                    )
                else:
                    available, reason = _probe_availability(klass)
                    entry["available"] = available
                    if not available:
                        entry["reason"] = reason or (
                            f"{klass.__qualname__}.available() reported unavailable"
                        )
                    entry["capabilities"] = dict(getattr(klass, "CAPABILITIES", {}))
                    entry["parameter_schema"] = dict(
                        getattr(klass, "PARAMETER_SCHEMA", {})
                    )
            result.append(entry)
        return result

    @classmethod
    def create(cls, name: str | None = None, **kwargs: Any) -> Any:
        """Instantiate a detector backend by name.

        Raises ValueError for unknown names, ImportError for unloadable classes.
        """
        if name is None:
            name = cls._default
        if name not in cls._backends:
            raise ValueError(
                f"Unknown detector backend '{name}'. "
                f"Available: {list(cls._backends.keys())}"
            )
        info = cls._backends[name]
        klass = _load_class(info["class_path"])
        if klass is None:
            raise ImportError(f"Cannot load detector class: {info['class_path']}")
        return klass(**kwargs)

    @classmethod
    def set_available(
        cls, name: str, available: bool, reason: str | None = None
    ) -> None:
        """Override availability for a registered backend (session-scoped, D-04).

        Used by :meth:`DetectorWorkerPool.on_backend_crash` (Plan 05-09) to lock
        out a crashed backend until the process restarts. Frontend
        ``DetectorDropdown`` reads ``available`` / ``reason`` from
        :meth:`list_backends` and greys out the entry per Phase 3 D-06.

        Semantics:
            * ``available=False, reason="..."`` — overrides the
              ``klass.available()`` probe and forces unavailable. The stored
              reason is surfaced verbatim via ``list_backends()``; when
              ``reason`` is ``None`` a default "Marked unavailable by
              set_available()." fallback is used.
            * ``available=True, reason=None`` — clears any prior override and
              re-surfaces the probe result (i.e. restores healthy backend).
            * Not intended for general use — this is the pool's crash-handler
              hook. Raises ``ValueError`` if ``name`` is not registered.

        Session-scoped: stored inside the in-process ``_backends`` dict. On the
        next process start, registry rebuilds with probe-fresh availability.
        D-04 explicitly rejects auto-retry loops — one crash means the backend
        is dead until restart.
        """
        if name not in cls._backends:
            raise ValueError(
                f"Unknown detector backend '{name}'. "
                f"Available: {list(cls._backends.keys())}"
            )
        cls._backends[name]["_override_available"] = (bool(available), reason)

    @classmethod
    def get_default(cls) -> str:
        return cls._default

    @classmethod
    def _clear(cls) -> None:
        """Test helper only. Clears all registered backends, including any
        ``set_available`` overrides — override state lives inside the
        per-backend dict so resetting ``cls._backends = {}`` drops it too."""
        cls._backends = {}


class Detection3DRegistry:
    """Central registry for 3D lifter backends (research Decision A)."""

    _backends: dict[str, dict] = {}
    _default: str = "median_depth"

    @classmethod
    def register(cls, name: str, display: str, class_path: str, klass: type) -> None:
        _validate_capabilities(
            name,
            klass,
            _DETECTION_3D_REQUIRED_KEYS,
            _DETECTION_3D_TYPED_KEYS,
            kind="Detection3D",
        )
        cls._backends[name] = {"class_path": class_path, "display": display}
        logger.debug("Registered detection_3d backend: %s (%s)", name, class_path)

    @classmethod
    def list_backends(cls) -> list[dict]:
        result: list[dict] = []
        for name, info in list(cls._backends.items()):
            entry: dict[str, Any] = {"name": name, "display": info["display"]}
            klass = _load_class(info["class_path"])
            if klass is None:
                entry["available"] = False
                entry["reason"] = f"Cannot load {info['class_path']}"
                entry["capabilities"] = {}
                entry["parameter_schema"] = {}
            else:
                available, reason = _probe_availability(klass)
                entry["available"] = available
                if not available:
                    entry["reason"] = reason or (
                        f"{klass.__qualname__}.available() reported unavailable"
                    )
                entry["capabilities"] = dict(getattr(klass, "CAPABILITIES", {}))
                entry["parameter_schema"] = dict(getattr(klass, "PARAMETER_SCHEMA", {}))
            result.append(entry)
        return result

    @classmethod
    def create(cls, name: str | None = None, **kwargs: Any) -> Any:
        if name is None:
            name = cls._default
        if name not in cls._backends:
            raise ValueError(
                f"Unknown detection_3d backend '{name}'. "
                f"Available: {list(cls._backends.keys())}"
            )
        info = cls._backends[name]
        klass = _load_class(info["class_path"])
        if klass is None:
            raise ImportError(f"Cannot load detection_3d class: {info['class_path']}")
        return klass(**kwargs)

    @classmethod
    def get_default(cls) -> str:
        return cls._default

    @classmethod
    def _clear(cls) -> None:
        cls._backends = {}


def detector_backend(name: str, display: str):
    """Decorator: register a class as a DetectorProtocol backend.

    Usage::

        @detector_backend(name="yolov11", display="YOLOv11-nano")
        class YOLOv11Backend(TorchBackendMixin):
            CAPABILITIES = {...}
            ...
    """

    def decorator(klass: type) -> type:
        class_path = f"{klass.__module__}.{klass.__qualname__}"
        DetectorRegistry.register(name, display, class_path, klass)
        return klass

    return decorator


def detection_3d(name: str, display: str):
    """Decorator: register a class as a Detection3DProtocol lifter.

    Usage::

        @detection_3d(name="median_depth", display="Median Depth (legacy)")
        class MedianDepthLifter:
            CAPABILITIES = {...}
            ...
    """

    def decorator(klass: type) -> type:
        class_path = f"{klass.__module__}.{klass.__qualname__}"
        Detection3DRegistry.register(name, display, class_path, klass)
        return klass

    return decorator
