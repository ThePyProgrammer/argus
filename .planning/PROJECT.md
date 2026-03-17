# Multi-Robot 3D Reconstruction (SimWorld)

## What This Is

A simulation-based system where two Unitree Go2 quadruped robots autonomously explore an environment in SimWorld-Robotics (UE5), split the space between them, and produce a combined real-time 3D reconstruction map suitable for autonomous navigation. Built on top of DimOS as the agentic robotics framework.

## Core Value

Two simulated robots autonomously explore, build individual maps, and merge them into a single navigation-grade 3D map in real-time.

## Requirements

### Validated

<!-- Shipped and confirmed valuable. -->

(None yet — ship to validate)

### Active

<!-- Current scope. Building toward these. -->

- [ ] Two Go2 robots spawn and operate in SimWorld-Robotics environment
- [ ] Robots autonomously explore using a split-room coverage strategy
- [ ] Each robot runs onboard SLAM producing a local 3D map
- [ ] Local maps merge in real-time into a unified 3D reconstruction
- [ ] Output includes both occupancy grid (navigation) and point cloud (visualization)
- [ ] DimOS orchestrates robot coordination and task allocation
- [ ] SimWorld gym interface used for robot control and sensor data

### Out of Scope

- Physical/real-world deployment — simulation only
- Custom UE5 scene creation — using SimWorld's existing urban environments as stand-in for office-like spaces
- Traffic system integration — not relevant for indoor-like survey
- Vision-language navigation (SimWorld-MMNav benchmark) — different task
- Post-processing refinement pipeline — real-time map is the deliverable

## Context

- **SimWorld-Robotics** is a JHU research platform built on Unreal Engine 5 with procedural urban scene generation, multi-robot support, and an OpenAI gym interface. It already supports quadruped robots and multi-agent collaboration (SimWorld-MRS benchmark).
- **DimOS** is an agentic operating system for robotics referenced in the existing project documentation. It provides the coordination layer for multi-robot systems.
- The Go2's sensor suite needs to be determined during research — SimWorld simulates sensor data, but the exact sensors available (LiDAR, depth cameras, RGB) in the gym environment need investigation.
- SimWorld's multi-agent environment (`world_buffer.py`) and gym interface provide the foundation for two-robot coordination.
- The urban environment serves as a stand-in for office-like spaces — buildings, structures, and enclosed areas approximate indoor survey conditions.

## Constraints

- **Platform**: SimWorld-Robotics (UE5) — all work is simulation-only
- **Framework**: DimOS for robot orchestration and coordination
- **Robots**: Two Unitree Go2 quadrupeds (simulated)
- **Real-time**: Map must build live as robots explore, not post-processed
- **Interface**: Must use SimWorld's OpenAI gym interface for robot control

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Simulation-only (SimWorld) | Faster iteration, no hardware dependency | — Pending |
| Split-room exploration strategy | Efficient coverage, simpler coordination than overlap | — Pending |
| DimOS as coordination layer | Existing agentic framework in project docs | — Pending |
| Urban environment as office stand-in | Avoids custom UE5 scene work, leverages existing procedural generation | — Pending |
| Real-time map merging | Robots need live map for navigation during exploration | — Pending |

---
*Last updated: 2026-03-17 after initialization*
