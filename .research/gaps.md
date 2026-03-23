# Gap Analysis

## Contradictions Found

1. **LDSO performance**: Axis 1 flags a contradiction — LDSO authors claim performance "comparable to state-of-the-art feature-based systems" but an independent study found "far worse results compared to sparse algorithms." Likely dataset-dependent but unresolved.

2. **OpenVINS multi-camera maturity**: Axis 1 lists OpenVINS as supporting "arbitrary N cameras" natively. Axis 5 reveals the maintainer admits this feature is "not fully tested" and users hit hard-coded `INVALID MAX CAMERAS` errors. The architecture supports it, but the implementation has rough edges.

3. **SVO Pro multi-camera availability**: Axis 1 states SVO Pro has "native multi-camera rig support." Axis 5 notes it's unclear whether the multi-camera research code is fully included in the open-source `rpg_svo_pro_open` release or held back.

4. **stella_vslam star count**: Axis 5 notes conflicting star counts (654 vs 1.1k) across sources — minor discrepancy, likely API caching.

5. **Basalt multi-camera**: Axis 1 claims "native multi-camera VIO" support. Axis 5 clarifies this is from research papers only — the feature "does not appear in the official Basalt codebase."

## Unanswered Questions

1. **No GPU hardware constraint implications**: Axes 2 and 5 both flag that the user lacks an NVIDIA GPU. This is a critical constraint that eliminates all deep learning SLAM methods (DROID-SLAM, DPV-SLAM, SL-SLAM) and cuVSLAM. None of the axes systematically filter the recommendation set for CPU-only operation. *However, this constraint comes from a memory note that may be stale — the user's current hardware should be verified.*

2. **MuJoCo simulation integration**: Axis 5 notes no surveyed SLAM system documents MuJoCo integration. Given the project pivoted to MuJoCo for simulation, this gap matters.

3. **Quantitative ICP-merging vs native multi-camera**: No axis provides a direct quantitative comparison. Axis 1 cites Multicam-SLAM showing 94-99% vs 21% tracking rates, but this compares single-camera vs multi-camera, not ICP-merged vs native multi-camera.

## Thin Areas

1. **Visual-inertial methods in Axis 2**: Deep learning VIO methods (beyond SuperVINS) are under-covered. Methods like Deep-EIO or learned IMU pre-integration are not mentioned.

2. **Outdoor/large-scale evaluation**: Almost all benchmarks cited are indoor (TUM, Replica, ScanNet, EuRoC). KITTI is the only outdoor dataset mentioned. If the pipeline needs outdoor operation, this is a coverage gap.

3. **Computational cost of multi-instance deployment**: No axis quantifies CPU/memory scaling when running N parallel SLAM instances (the current architecture). How does 4x ORB-SLAM3 instances scale on a multi-core CPU?

4. **Semantic SLAM methods**: Kimera is mentioned but semantic SLAM (object-level SLAM, panoptic SLAM) that could improve multi-camera merge quality is largely absent.

## Citation Audit

### Unsourced Claims Detected
- Axis 2: "DROID-SLAM requires ~20GB VRAM" — no source URL provided for VRAM figure
- Axis 2: "MINI-DROID-SLAM replaces standard GRU with Mini-GRU" — sourced but from MDPI Sensors, which is low-tier
- Axis 3: Several FPS figures are self-reported from individual papers without independent verification (noted as MEDIUM confidence by the axis)

### Axes with Full Citation Coverage
- Axis 1: All major claims sourced (38 sources)
- Axis 4: All claims sourced (22 sources)
- Axis 5: All claims sourced (38 sources)

Overall citation quality is good. Axis 2 and 3 have minor gaps but are transparent about confidence levels.

## Follow-up Research Needed

**Yes — one targeted follow-up recommended.** The most significant gap is the lack of CPU-only filtering and the absence of practical deployment guidance for running multiple SLAM instances without GPU. A follow-up should:

1. Identify which methods from all axes can run on CPU-only hardware at real-time rates with multiple simultaneous instances
2. Estimate computational scaling for N parallel instances of CPU-based methods (ORB-SLAM3, OpenVINS, Basalt, RTAB-Map)
3. Check for any recent (2025-2026) CPU-optimized SLAM methods not covered in the primary research
