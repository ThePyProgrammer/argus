"""Built-in perception detector backends.

Importing this package triggers @detector_backend side-effect registration on
every built-in backend that imports cleanly. Mirrors src/slam/backends/__init__.py
per CONTEXT.md D-07.

Phase 1 ships only YOLOv11Backend. Phase 5 adds RT-DETRv2, OWLv2, BoxeR —
each guarded with try/except ImportError so a missing optional dep does not
crash startup.

main.py imports this module via:
    import src.perception.backends  # noqa: F401 -- triggers detector registration
"""

from src.perception.backends import yolov11_backend  # noqa: F401 -- registers 'yolov11'
from . import rtdetrv2_backend  # noqa: F401 -- Phase 5 DET-MODELS-02 registration

# Phase 5 additions land here as try/except-guarded imports, mirroring
# src.slam.backends' orbslam3 / openvins / svopro pattern. Not yet shipped.
