# ADR-0008: Isolate Heavy and Crashy Backends in Subprocesses

| Field | Value |
|-------|-------|
| Status | Accepted |
| Date | 2026-04-30 |
| Category | Integration Strategy |
| Deciders | Project maintainers |
| Consulted | `.planning/PROJECT.md`, `.planning/REQUIREMENTS.md`, `.planning/research/STACK.md`, `.planning/research/ARCHITECTURE.md`, `.planning/research/PITFALLS.md` |
| Informed | Backend, model integration, and operations contributors |
| Supersedes | In-process execution for all model backends |
| Superseded by |  |
| Related | ADR-0004, ADR-0006, ADR-0011 |

## Context

Argus supports optional SLAM and detection backends with heavy dependencies, native code, large model weights, or unstable runtime behavior. v2.0 used subprocess isolation with ZMQ and msgpack for crash-prone SLAM backends. v3.0 applies the same failure-domain boundary to BoxeR and other heavy detectors through a distinct `SubprocessDetectorBridge`.

## Options Considered

1. **Separate subprocess bridge per subsystem** — isolate heavy detector and SLAM backends with ZMQ/msgpack IPC and watchdogs.
2. **Run every backend in the main process** — simpler calls, shared memory, but shared failure and thread-pool state.
3. **External service deployment** — run models behind independent HTTP/gRPC services.
4. **Status quo / do nothing** — only isolate previously integrated SLAM backends.

## Decision

**In the context of** CPU-only robotics simulation with optional heavy model backends, **facing** crash risk, dependency conflicts, and torch/thread-pool interference, **we decided for** subprocess isolation for heavy or crashy backends using subsystem-specific ZMQ/msgpack bridges **to achieve** contained failures and recoverable fallbacks, **accepting** IPC complexity and serialization overhead.

## Rationale

The failure boundary matters more than eliminating a small IPC cost. A hung or OOMing model should not kill the simulation loop or FastAPI server. Separate SLAM and detector bridges keep failure attribution and fallback behavior unambiguous.

## Consequences

### Positive

- Crashes and hangs can trigger backend-specific fallback rather than process-wide failure.
- Dependency conflicts and Python environment differences can be contained in worker venvs.
- Torch and OpenMP thread-pool configuration can be isolated for model subprocesses.

### Negative

- IPC protocols require explicit serialization contracts and tests.
- Subprocess lifecycle, watchdogs, and cleanup add operational complexity.
- Debugging across process boundaries is harder than in-process stack traces.

### Neutral / Follow-up

- Lightweight backends may remain in-process if they obey thread and inference-mode constraints.
- Subprocess message formats should use flat arrays for model outputs rather than nested dataclasses.

## References

- `.planning/PROJECT.md` — Subprocess isolation for C++ backends
- `.planning/REQUIREMENTS.md` — DET-MODELS-03 and DET-MODELS-06
- `.planning/research/STACK.md` — BoxeR subprocess integration approach
- `.planning/research/PITFALLS.md` — thread collision, crashes, and msgpack serialization pitfalls
