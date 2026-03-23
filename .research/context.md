# Research Context

## Topic
Systematic literature review of visual SLAM methodologies suitable for integration into a multi-camera SLAM pipeline that currently uses ICP-based merging of per-camera SLAM outputs.

## Scope & Parameters
- **In scope**: All visual SLAM methods — monocular, stereo, RGB-D, visual-inertial, deep learning-based (learned features, end-to-end, neural implicit/explicit representations), and hybrid visual methods
- **Explicitly out of scope**: LiDAR SLAM, LiDAR-inertial SLAM, or any method requiring LiDAR sensors. The entire purpose of this system is to replace LiDAR with camera-based approaches.
- **Focus**: Methods that can be integrated into an existing multi-camera pipeline where individual camera SLAM outputs are merged via ICP or similar registration
- **Constraint**: Only real-time capable methods (must run at or near sensor framerate)

## Depth Level
Standard — 4-5 research axes with moderate detail, 1 follow-up pass if gaps found.

## Target Audience
The developer(s) of this multi-camera SLAM pipeline — technical, implementation-oriented audience who need to evaluate and integrate these methods.

## Key Questions to Answer
1. What are all the major visual SLAM methodologies (classical, feature-based, direct, semi-direct, deep learning, neural implicit/explicit) that can run in real-time?
2. For each method: what is the output representation (point cloud, mesh, voxels, Gaussians, etc.) and how compatible is it with ICP-based merging?
3. What are the trade-offs between traditional (ORB-SLAM3, DSO, SVO) vs. learned (DROID-SLAM, DPVO, NICE-SLAM, SplaTAM) approaches for multi-camera fusion?
4. Which methods natively support multi-camera setups vs. requiring per-camera instances merged externally?
5. What is the state of the art as of 2025-2026 in real-time visual SLAM, and which emerging methods show the most promise?
6. For each method: what are the hardware requirements (GPU, CPU), open-source availability, and maturity of the codebase?

## Constraints & Preferences
- Real-time operation is a hard requirement — exclude offline-only methods
- Integration feasibility is the primary evaluation lens (API surface, output format, ease of plugging into existing pipeline)
- No LiDAR — this system exists to replace LiDAR with cameras
- Should cover both established/mature methods and cutting-edge approaches

## Output Format Preference
Narrative survey organized by category with embedded comparison tables per category. Each category should have:
- Written analysis of the approach, strengths, limitations
- Structured comparison table: method, year, sensor type, output representation, real-time capability, GPU required, open-source status, integration notes, key papers
