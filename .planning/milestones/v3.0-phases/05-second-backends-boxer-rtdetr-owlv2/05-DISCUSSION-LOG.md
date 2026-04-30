# Phase 5: second-backends-boxer-rtdetr-owlv2 - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-15
**Phase:** 05-second-backends-boxer-rtdetr-owlv2
**Areas discussed:** BoxeR subprocess + 3D-OBB wire, RT-DETRv2 ONNX acquisition + runtime, OWLv2 open-vocab prompt plumbing, Checkpoints + offline + LICENSES

---

## Area 1: BoxeR subprocess + 3D-OBB wire

### Q1.1: Where should the BoxeR subprocess venv + setup script live?

| Option | Description | Selected |
|--------|-------------|----------|
| subprocess_venvs/boxer/ + scripts/setup_boxer_subprocess.sh | Isolated venv per heavy subprocess backend, setup script under scripts/. Gitignored. Idempotent. | ✓ |
| .venvs/boxer/ + setup_boxer_subprocess.sh at repo root | Convention near .venv. Repo-root script discoverable but cluttering. | |
| External path via BOXER_VENV env var | No committed script; user handles install. Violates SC#2's literal setup_boxer_subprocess.sh requirement. | |

**User's choice:** Option 1 (Recommended — matches SC#2 + v2.0 SLAM conventions).
**Notes:** Maps to D-01.

### Q1.2: How should the Phase 2 msgpack reply schema extend to carry 3D-native OBBs?

| Option | Description | Selected |
|--------|-------------|----------|
| Additive `boxes_3d` field, keep `bboxes` as 2D | Worker sends 2D bboxes + 3D OBBs. Additive migration, preserves CameraFeed 2D overlay. | ✓ |
| Overload `bboxes` with 12-float OBBs when 3D-native | Same field, different semantics per backend. Violates Phase 2 generic-schema principle; loses 2D overlay. | |
| Worker sends pre-serialized OrientedBox3D.to_wire() dicts | Tightens coupling — subprocess must know project's schema. | |

**User's choice:** Option 1 (Recommended — additive, safest).
**Notes:** Maps to D-02. Extends Phase 2 D-17 additively with optional list-of-dicts.

### Q1.3: Who owns the crash watchdog that triggers crash_fallback within 5 s?

| Option | Description | Selected |
|--------|-------------|----------|
| DetectorWorkerPool wraps bridge.call() and catches exceptions | Centralized fallback; mirrors SLAM exploration_loop.py:207 pattern. | ✓ |
| BoxeRBackend.__call__ internally catches + retries + degrades | Splits fallback across backend (retry) + pool (fallback). | |
| SubprocessDetectorBridge exposes on_crash callback | Callback-driven rather than exception-driven. New surface on bridge. | |

**User's choice:** Option 1 (Recommended — centralized, matches SLAM precedent).
**Notes:** Maps to D-03. Pool owns atomic backend swap using Phase 4 D-10 lifter-hot-swap pattern.

### Q1.4: After BoxeR crash + fallback, should BoxeR stay selectable?

| Option | Description | Selected |
|--------|-------------|----------|
| Mark available: false session-scoped ("restart to retry") | Greyed-out dropdown entry with reason. Prevents crash loops. | ✓ |
| Stay selectable — user can manually re-switch | Risk of crash loop if root cause unresolved. | |
| Auto-retry once after 10 s, then mark unavailable | Adds state machine for marginal benefit (OOM/missing-weight crashes aren't transient). | |

**User's choice:** Option 1 (Recommended — honest failure mode).
**Notes:** Maps to D-04. DetectorRegistry.set_available("boxer", False, reason=...) renders via Phase 3 D-06.

---

## Area 2: RT-DETRv2 ONNX acquisition + runtime

### Q2.1: How should the RT-DETRv2 ONNX artifact be acquired?

| Option | Description | Selected |
|--------|-------------|----------|
| On-demand export via transformers+optimum on first run, cached to models/ | First boot downloads weights, exports ONNX, persists. revision=<sha> flows through. | ✓ |
| Ship repo-committed .onnx via git-lfs | +70 MB clone, requires lfs on CI. Deterministic but heavy. | |
| Download pre-exported ONNX from HF third-party mirror | Non-upstream source violates supply-chain hygiene. | |

**User's choice:** Option 1 (Recommended — upstream-sourced, offline after first fetch).
**Notes:** Maps to D-06. optimum goes into dev extra (download-time only).

### Q2.2: Which ONNX runtime + execution provider?

| Option | Description | Selected |
|--------|-------------|----------|
| onnxruntime CPU EP added to perception extra | Portable, ~3× faster than PyTorch CPU for transformers. | ✓ |
| onnxruntime-openvino EP for Intel | Intel-only; fails on AMD/ARM CI. | |
| Keep PyTorch CPU + torch.compile | ~550 ms/frame at 320 px — blows SC#1 ≤250 ms budget. | |

**User's choice:** Option 1 (Recommended — meets SC#1).
**Notes:** Maps to D-07.

### Q2.3: Input resolution — fixed or dynamic?

| Option | Description | Selected |
|--------|-------------|----------|
| Fixed 320×320 at ONNX export | Matches SC#1 target exactly; simpler session cache. | ✓ |
| Dynamic input shape | Cold-start recompile per shape; latency variance. | |
| Lock at 640×640 (YOLO-native) | ~700 ms/frame at 640 — blows SC#1. | |

**User's choice:** Option 1 (Recommended — SC#1 literal target).
**Notes:** Maps to D-08. Letterbox-resize preserves aspect ratio.

### Q2.4: ONNX session scope — per-worker or shared?

| Option | Description | Selected |
|--------|-------------|----------|
| One session per DetectorWorker | Matches Phase 2 symmetric backend instantiation. ~80 MB × N robots. | ✓ |
| Single shared session across workers | Saves RAM but GIL/session-lock contention. Premature optimization. | |

**User's choice:** Option 1 (Recommended — symmetric with Phase 2 pattern).
**Notes:** Maps to D-09.

---

## Area 3: OWLv2 open-vocab prompt plumbing

### Q3.1: How should text-prompt UI surface be delivered to backend?

| Option | Description | Selected |
|--------|-------------|----------|
| DetectorParameterPanel text field → debounced detector_param_update WS | Reuses Phase 3 D-03 live-tunable param path. Zero new WS types. | ✓ (voided by scope drop) |
| Dedicated PromptInput component + new WS message type | New message type, new component. More files to maintain. | |
| POST /api/detectors/prompt + full restart per change | Brutal UX — 5 restarts per typed word. Rejected. | |

**User's choice:** Option 1 (Recommended).
**Notes:** Decision voided by D-10 (OWLv2 dropped).

### Q3.2: Should text encoder output be cached?

| Option | Description | Selected |
|--------|-------------|----------|
| Cache encoded prompt embedding; re-encode on prompt change | ~4 s → ~1.5 s per frame. | ✓ (voided by scope drop) |
| Re-encode every frame | Blows SC#5 upper bound 4 s → >6 s. | |
| Pre-encode at prompt-set time stored outside backend | Breaks backend encapsulation. | |

**User's choice:** Option 1 (Recommended).
**Notes:** Decision voided by D-10.

### Q3.3: Single or multi-prompt per frame?

| Option | Description | Selected |
|--------|-------------|----------|
| Single prompt only; multi-prompt deferred | Simpler UX; matches pluggability-regression goal. | |
| Multi-prompt via comma-separated input | Needs per-prompt color/threshold UI. Substantial frontend work. | ✓ (voided by scope drop) |

**User's choice:** Option 2 (multi-prompt).
**Notes:** Voided by D-10 (N/A without OWLv2).

### Q3.4: How to surface "on-demand, not real-time"?

| Option | Description | Selected |
|--------|-------------|----------|
| Add realtime: false capability key + distinct badge | Extensible boolean key; warning-style pill. | |
| Stuff into cpu_latency_hint_ms with string value | Conflates latency + mode concepts. | |
| Description-only, no badge | Misses the badge surface. | |
| Other (user free-text) | **"my default it should be realtime, so if the model doesn't support realtime then maybe it shouldn't be integrated?"** | ✓ |

**User's choice:** Other — questioned whether OWLv2 should be integrated at all.
**Notes:** This triggered the scope discussion below. Led to D-10 (OWLv2 dropped from Phase 5).

### Area 3 Scope Resolution — plain-text follow-up

Claude presented three options in plain text after user's freeform response:
1. Drop OWLv2 entirely (amend ROADMAP + REQUIREMENTS).
2. Keep OWLv2 but gate selection behind a one-time ConfirmModal warning about degraded mode.
3. Keep OWLv2 as a one-shot label tool, not a live backend.

**User's choice:** Option 1 — drop OWLv2.
**Notes:** Captured as D-10 in CONTEXT.md. REQUIREMENTS.md amendments: DET-MODELS-04 marked `[~]` with strikethrough + Out-of-Scope entry; traceability table entry struck; coverage recount 42 → 41. ROADMAP.md amendments: Phase 5 bullet/goal/requirements/SCs updated — SC#5 removed, SC#6 (LICENSES) renumbered to SC#5.

---

## Area 4: Checkpoints + offline + LICENSES

### Q4.1: What should models/ dir layout look like?

| Option | Description | Selected |
|--------|-------------|----------|
| models/<backend-slug>/<sha>/ — backend-name owned | Consistent with v2.0 models/orbslam3/ + models/unitree_go2/. | ✓ |
| models/huggingface/<repo-slug>/<sha>/ — HF-cache mirror | BoxeR isn't on HF — needs two layouts. | |
| models/<sha>/ flat | Opaque hash dirs; needs manifest indirection. | |

**User's choice:** Option 1 (Recommended).
**Notes:** Maps to D-11.

### Q4.2: SHA revision pinning + offline enforcement?

| Option | Description | Selected |
|--------|-------------|----------|
| revision=<sha> kwarg + HF_HUB_OFFLINE=1 after pre-fetch | Module-level SHA constants; local_files_only=True. Deterministic. | ✓ |
| Centralized MANIFEST.toml | Overkill at 2 backends. | |
| Env vars per backend at launch | Pushes pinning out of version control. Rejected. | |

**User's choice:** Option 1 (Recommended).
**Notes:** Maps to D-12. BoxeR SHA = git commit SHA (not HF revision).

### Q4.3: Where does make download-models logic live?

| Option | Description | Selected |
|--------|-------------|----------|
| Thin Makefile → scripts/download_models.py | Python easier to test + debug than shell. Sub-targets per backend. | ✓ |
| Pure Makefile recipes (wget + optimum-cli) | Shell error handling + cross-platform concerns. | |
| scripts/download_models.py only, no Makefile target | Violates SC#4's literal "make download-models". | |

**User's choice:** Option 1 (Recommended).
**Notes:** Maps to D-13.

### Q4.4: LICENSES.md structure + CC-BY-NC surfacing?

| Option | Description | Selected |
|--------|-------------|----------|
| LICENSES.md + license: "CC-BY-NC-4.0" capability badge | Badge renders via Phase 3 D-05 path. No consent modal. | ✓ |
| ConfirmModal gating BoxeR selection | Stacks with Phase 3 D-14 Switch modal. Awkward UX. | |
| LICENSES/ subdir only, no aggregated LICENSES.md | Violates SC#6 (now SC#5) literal requirement. | |

**User's choice:** Option 1 (Recommended).
**Notes:** Maps to D-14.

---

## Final Close-out

**Q:** Ready for context, or explore more gray areas?

**Options presented:**
- Ready for context (Recommended)
- One more area — warmup UX budgeting (≤30 s SC#1)
- One more area — per-class color palette for 80+ COCO classes

**User's choice:** Ready for context.
**Notes:** Moved to write_context step.

---

## Claude's Discretion

Noted in CONTEXT.md <decisions> section under "Claude's Discretion". Exact HF + git SHAs, ort.SessionOptions tuning beyond thread count, sha256 rollback cleanup strategy, BoxeR worker heartbeat cadence.

## Deferred Ideas

See CONTEXT.md <deferred> section. 10 items captured, including:
- OWLv2 as a live backend (rejected this milestone)
- Text-prompted open-vocab UI (deferred with OWLv2)
- Multi-prompt input (N/A without OWLv2)
- Warmup UX for slow-first-run export
- OpenVINO EP
- Dynamic ONNX input shape
- Shared ORT session
- Manifest sha pinning
- Per-class palette expansion
- BoxeR CC-BY-NC ConfirmModal gate
- Auto-retry after BoxeR crash

---

*Phase: 05-second-backends-boxer-rtdetr-owlv2*
*Discussion: 2026-04-15*
