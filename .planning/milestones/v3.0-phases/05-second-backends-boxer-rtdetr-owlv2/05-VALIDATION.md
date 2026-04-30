---
phase: 5
slug: second-backends-boxer-rtdetr-owlv2
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-15
---

# Phase 5 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Derived from `05-RESEARCH.md` § Validation Architecture.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (existing) + pytest-asyncio + pytest-timeout (already in `dev` extra) |
| **Config file** | `pyproject.toml [tool.pytest.ini_options]` (to be created in Wave 0 — registers `slow_boxer` and `network` markers) |
| **Quick run command** | `uv run pytest tests/perception/test_<module>.py::test_<name> -x --timeout=30` |
| **Full suite command** | `uv run pytest tests/ -x --timeout=300 -m "not slow_boxer and not network"` |
| **Estimated runtime** | ~90 seconds (quick subset); ~3 min (full with markers off) |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/perception/test_<file_changed>.py -x --timeout=30` (≤30 s)
- **After every plan wave:** Run `uv run pytest tests/perception/ tests/integration/ -x --timeout=300 -m "not slow_boxer and not network"` (≤2 min)
- **Before `/gsd-verify-work`:** Full suite must be green + manual SC#3 exercise (`kill -9 <boxer-pid>` → observe CrashToast in a live coordinator run)
- **Max feedback latency:** 30 s per task commit, 120 s per wave

---

## Per-Task Verification Map

Mapping derived from `05-RESEARCH.md` lines 921–937. Task IDs populated by planner during Wave assignment; file_exists is tracked by Wave 0 provisioning.

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 5-XX-01 | RT-DETRv2 backend | 2 | DET-MODELS-02 | — | Eval mode enforced (Phase 1 D-07); inference_mode no-op for ORT | unit | `uv run pytest tests/perception/test_rtdetrv2_backend.py -x` | ❌ W0 | ⬜ pending |
| 5-XX-02 | RT-DETRv2 backend | 2 | DET-MODELS-02 | — | Input validation: letterbox preserves aspect ratio | smoke | `uv run pytest tests/perception/test_rtdetrv2_backend.py::test_latency_p95_under_250ms` | ❌ W0 | ⬜ pending |
| 5-XX-03 | BoxeR backend composer | 2 | DET-MODELS-03 | — | Lazy bridge spawn (D-05) — construction doesn't touch filesystem or network | unit | `uv run pytest tests/perception/test_boxer_backend.py::test_construct_no_spawn` | ❌ W0 | ⬜ pending |
| 5-XX-04 | BoxeR backend composer | 2 | DET-MODELS-03 | T-5-05 | msgpack `strict_map_key=True` blocks malicious worker payload | integration | `uv run pytest tests/perception/test_boxer_backend.py::test_warmup_returns_3d -m slow_boxer` | ❌ W0 | ⬜ pending |
| 5-XX-05 | BoxeR backend composer | 2 | DET-MODELS-03 | — | Extent halving — quaternion constructor gets half_extents, not full (D-02 gotcha) | unit | `uv run pytest tests/perception/test_boxer_backend.py::test_extent_halving` | ❌ W0 | ⬜ pending |
| 5-XX-06 | Bridge schema extension | 1 | DET-MODELS-03 | T-5-02 | Existing Phase 2 echo test still green (additive schema) | unit | `uv run pytest tests/perception/test_subprocess_bridge_skeleton.py -x` | ✅ | ⬜ pending |
| 5-XX-07 | Pool crash handler | 2 | DET-MODELS-06 | — | BridgeHangError raised cleanly on RCVTIMEO | unit | `uv run pytest tests/perception/test_crash_fallback.py::test_bridge_hang_raises` | ❌ W0 | ⬜ pending |
| 5-XX-08 | Pool crash handler | 2 | DET-MODELS-06 | — | SubprocessDiedError raised when Popen exited | unit | `uv run pytest tests/perception/test_crash_fallback.py::test_subprocess_died_raises` | ❌ W0 | ⬜ pending |
| 5-XX-09 | Pool crash handler | 2 | DET-MODELS-06 | — | Pool emits `crash_fallback` WS + swaps to YOLOv11 atomically | unit | `uv run pytest tests/perception/test_crash_fallback.py::test_pool_swaps_to_yolo` | ❌ W0 | ⬜ pending |
| 5-XX-10 | E2E crash test | 3 | DET-MODELS-06 | — | `kill -9 <boxer-pid>` → CrashToast WS arrives within 5 s | integration | `uv run pytest tests/integration/test_boxer_crash_fallback.py -m slow_boxer --timeout=30` | ❌ W0 | ⬜ pending |
| 5-XX-11 | download_models script | 3 | DET-MODELS-07 | T-5-03 | sha256 verification on downloaded artifacts | integration | `uv run pytest tests/integration/test_download_models.py::test_download_rtdetrv2 -m network` | ❌ W0 | ⬜ pending |
| 5-XX-12 | setup_boxer script | 1 | DET-MODELS-07 | T-5-01 | Idempotent `.ready` short-circuit; no shell injection surface | integration | `uv run pytest tests/integration/test_download_models.py::test_setup_boxer_idempotent -m network` | ❌ W0 | ⬜ pending |
| 5-XX-13 | Offline boot gate | 3 | DET-MODELS-07 | T-5-06 | HF_HUB_OFFLINE=1 enforced + local_files_only | integration | `uv run pytest tests/integration/test_offline_boot.py -m slow_boxer --timeout=120` | ❌ W0 | ⬜ pending |
| 5-XX-14 | LICENSES.md | 0 | DET-MODELS-08 | — | LICENSES.md has BoxeR CC-BY-NC-4.0 row + AGPL/Apache/MIT entries | unit | `uv run pytest tests/test_licenses_md.py::test_boxer_cc_by_nc_present` | ❌ W0 | ⬜ pending |
| 5-XX-15 | BoxeR capability | 2 | DET-MODELS-08 | — | `BoxeRBackend.CAPABILITIES["license"] == "CC-BY-NC-4.0"` | unit | `uv run pytest tests/perception/test_boxer_backend.py::test_capability_license` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

**Threat references** (resolved in RESEARCH § Security Domain):
- **T-5-01** — Subprocess command injection in `setup_boxer_subprocess.sh` (Tampering) — repo-relative literal args only
- **T-5-02** — Msgpack deserialization of untrusted worker payload (Tampering) — Phase 2 hardening via `strict_map_key=True, raw=False`
- **T-5-03** — Checkpoint poisoning via malicious HF model (Tampering) — `revision=SHA` pin + sha256 manifest + `local_files_only=True`
- **T-5-04** — ZMQ socket squatting (Tampering) — Phase 2 unique `ipc:///tmp/detector_bridge_<pid>_<id(self)>` endpoint
- **T-5-05** — Popen stdout buffer DoS (Denial of Service) — Wave 0 task: drain worker stdout/stderr in background thread or set `stdout=subprocess.DEVNULL`
- **T-5-06** — Path traversal in `models/<backend>/<sha>/` (Tampering) — all paths from module constants, not user input

---

## Wave 0 Requirements

*Sourced from RESEARCH § Validation Architecture → "Wave 0 Gaps" subsection (lines 945–957).*

- [ ] `tests/perception/test_rtdetrv2_backend.py` — stubs for DET-MODELS-02
- [ ] `tests/perception/test_boxer_backend.py` — stubs for DET-MODELS-03 (composer + capability)
- [ ] `tests/perception/test_crash_fallback.py` — stubs for DET-MODELS-06 (bridge exceptions + pool swap)
- [ ] `tests/integration/test_boxer_crash_fallback.py` — stub for DET-MODELS-06 e2e (slow_boxer marker)
- [ ] `tests/integration/test_download_models.py` — stubs for DET-MODELS-07 (network marker)
- [ ] `tests/integration/test_offline_boot.py` — stub for DET-MODELS-07 offline gate
- [ ] `tests/test_licenses_md.py` — stub for DET-MODELS-08
- [ ] `tests/perception/fixtures/sample_480x640_with_chair.npz` — RGB+depth fixture (reuse existing fixtures if present)
- [ ] `pyproject.toml [tool.pytest.ini_options]` — register `slow_boxer` and `network` markers (silences pytest warnings)
- [ ] `pyproject.toml [project.optional-dependencies].dev` — add `optimum[exporters]>=1.20.0`
- [ ] `pyproject.toml [project.optional-dependencies].perception` — add `onnxruntime>=1.19.0`

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| SC#1 — RT-DETRv2 dropdown selection → ≤30 s restart overlay → OBBs at ≥3 FPS on default MuJoCo scene | DET-MODELS-02 | Requires live coordinator + browser; FPS perception is user-visible | `uv run argus serve` in one terminal; open `http://localhost:8000`; select RTDETRv2 from Detector dropdown; observe restart overlay dismisses ≤30 s; count OBB frames in Three.js viewer for 10 s, expect ≥30 (≥3 FPS) |
| SC#2 — BoxeR dropdown selection → subprocess venv boots → 3D-native OBBs in Three.js (bypassing lifter) | DET-MODELS-03 | Requires live subprocess boot + Three.js render | Pre-run: `make download-models-boxer`. Start coordinator; select BoxeR; confirm LifterDropdown auto-hides (Phase 3 D-08); verify OBBs render with non-identity orientation (visible rotation on rotated chair in MuJoCo fixture scene) |
| SC#3 — `kill -9 <boxer-pid>` → `crash_fallback` WS within 5 s → auto-switch to YOLOv11 → CrashToast visible | DET-MODELS-06 | Requires timing observation + frontend toast render | Run coordinator with BoxeR active; `ps aux | grep boxer_worker`; `kill -9 <pid>`; start timer; observe CrashToast appears + Detector dropdown switches to YOLOv11. Assert elapsed ≤5 s. |
| SC#4 offline smoke — network-disabled coordinator boots all backends post-fetch | DET-MODELS-07 | Host-level network gating (iptables or firewall) can't be fully automated in a pytest session | After `make download-models`, unplug/disable network; `HF_HUB_OFFLINE=1 uv run argus serve`; open UI; select each backend in turn; verify all boot without errors |
| SC#5 — Capability badge renders `CC-BY-NC-4.0` for BoxeR in DetectorDropdown + DetectorSection | DET-MODELS-08 | Visual inspection of Phase 3 capability badge rendering | Open UI; hover BoxeR in Detector dropdown; verify `license` badge shows `CC-BY-NC-4.0`; select BoxeR; verify same badge appears in the active-detector capability row |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies (D-XX → test map above)
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify (enforced by planner when assigning plans to tasks)
- [ ] Wave 0 covers all MISSING test files (see Wave 0 Requirements section)
- [ ] No watch-mode flags in commands (all tests are one-shot)
- [ ] Feedback latency < 30 s per task commit, < 120 s per wave merge
- [ ] `nyquist_compliant: true` set in frontmatter (flip after Wave 0 test files land)

**Approval:** pending (planner to confirm test-file-to-plan mapping once plans are drafted)
