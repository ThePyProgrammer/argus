# Model Checkpoints

This directory holds pinned-SHA model artifacts fetched by `make download-models`.
The root `.gitignore` excludes specific large binaries (ORBvoc, weight files) but
the directory itself is tracked via `.gitkeep` so the layout survives `git clean`.

## Layout (Phase 5 D-11)

```
models/<backend-slug>/<sha>/<artifact>
```

Concretely, after `make download-models` completes:

```
models/
├── .gitkeep
├── README.md                     # this file
├── orbslam3/                     # v2.0 — ORB-SLAM3 vocabulary (.gitignored per-file)
│   ├── ORBvoc.txt
│   └── ORBvoc.bin
├── unitree_go2/                  # v2.0 — robot assets
├── rtdetrv2/                     # v3.0 Phase 5 — RT-DETRv2 ONNX checkpoint
│   └── <RT_DETRV2_SHA>/          # see src/perception/backends/rtdetrv2_backend.py
│       ├── pt/                   # HF snapshot intermediate (PyTorch .safetensors)
│       ├── model.onnx            # production runtime artifact
│       ├── config.json
│       └── preprocessor_config.json
└── boxer/                        # v3.0 Phase 5 — BoxeR subprocess checkpoints
    └── <BOXER_SHA>/              # see src/perception/backends/boxer_backend.py
        ├── boxernet/             # BoxerNet weights
        ├── dinov3/               # DINOv3 ViT-S/16 feature backbone
        └── owlv2/                # OWLv2 internal detector (NOT an argus backend)
```

## Invariants

- `<backend-slug>` matches the backend `name=` in its `@detector_backend(...)` decorator.
- `<sha>` is the 40-char hex commit/revision SHA pinned in the backend module's `_SHA` constant.
- Artifacts inside `<sha>/` are immutable for the lifetime of that SHA. Updating a checkpoint
  requires bumping the SHA constant in the backend file AND updating `EXPECTED_SHA256` in
  `scripts/download_models.py`.
- `models/` itself is NOT globally gitignored; specific large binaries are excluded per-file
  in `.gitignore` (see ORBvoc entries). Phase 5 does NOT add per-file entries — the
  RT-DETRv2 + BoxeR checkpoints are large but not absurd (<200 MB combined) and their
  SHA-pinned paths make them cache-friendly.

## Who writes here?

- `scripts/download_models.py` (invoked via `make download-models`) — HuggingFace snapshot
  + optimum ONNX export for RT-DETRv2.
- `scripts/setup_boxer_subprocess.sh` (invoked via `make download-models-boxer`) — git
  clone + BoxeR's own `download_ckpts.sh` for boxer/ subtree.

Nothing else should write to this tree. Checkpoints are artifacts, not mutable state.
