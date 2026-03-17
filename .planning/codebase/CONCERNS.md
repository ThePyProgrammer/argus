# Codebase Concerns

**Analysis Date:** 2026-03-17

## Tech Debt

**MCP (Model Context Protocol) Implementation:**
- Issue: MCP support is marked as **experimental** (pre-release beta) with protocol version `2025-11-25` and should not be relied upon for production robotics workflows
- Files: `docs/claude-code.md` (lines 176-183)
- Impact: API stability not guaranteed; breaking changes may occur without warning; breaking Claude Code integrations in future releases
- Fix approach: Upgrade to stable MCP protocol once finalized; lock protocol version in config; add comprehensive integration tests with protocol version assertions

**LCM Platform-Specific Patches:**
- Issue: LCM requires custom Darwin/macOS fsync patch due to differences between `fsync` (Darwin) and `fdatasync` (Linux)
- Files: `flake.nix` (lines 147-168, lines 142-169)
- Impact: Divergent behavior across platforms; fragile - patch breaks if LCM versions change
- Fix approach: Upstream patch to LCM project or pin LCM version with known patch compatibility; add CI tests on macOS and Linux

**Darwin Compiler Header Workaround:**
- Issue: Custom `cc-no-usr-include` wrapper bypasses nix header paths for `pip install` packages that hardcode `-I/usr/include`
- Files: `flake.nix` (lines 48-73, line 203)
- Impact: Fragile wrapper breaks if pip packages change their compilation strategy; adds complexity to developer environment setup
- Fix approach: Monitor affected pip packages; consider declarative overrides in nixpkgs for problematic packages; upstream fixes to package maintainers

**NVIDIA Library Symlinks Workaround:**
- Issue: Manual symlink creation for NVIDIA libs in `/tmp/nix-nvidia-libs` to avoid glibc conflicts with system NVIDIA libraries
- Files: `flake.nix` (lines 204-210)
- Impact: Brittle workaround; only works on Linux with NVIDIA GPUs; silent failures if symlinks don't match available libs
- Fix approach: Consider using nixpkgs CUDA overlay instead; add explicit NVIDIA package detection and validation

## Known Limitations

**Skill Decorator Requirements:**
- Issue: `@skill`-decorated methods require mandatory docstrings, typed parameters, and `str` return values
- Files: `docs/agents.md` (lines 57-62)
- Impact: Restricts skill flexibility; complex types must be serialized to `str`; harder to migrate legacy code to skill format
- Fix approach: Document widely; provide migration helpers; consider relaxing return type in future

**Temporal Memory System:**
- Issue: Temporal memory (time-aware memory system) is marked as **experimental**
- Files: `docs/agents.md` (line 119); `docs/robots.md` (line 24 references `unitree-go2-temporal-memory` blueprint)
- Impact: Feature stability not guaranteed; may be removed or changed significantly
- Fix approach: Stabilize temporal memory module; add comprehensive tests; document limitations clearly for users

**MCP Architectural Limitation:**
- Issue: MCP does not support mixing `McpServer` with in-process `agent()` module in same blueprint
- Files: `docs/claude-code.md` (line 146)
- Impact: Constrains blueprint architecture; forces choice between agent types; complicates multi-agent workflows
- Fix approach: Implement multi-agent MCP support; clarify when each architecture is appropriate; add validation to catch conflicts

## Security Considerations

**Distributed Network Architecture Risk:**
- Risk: LCM multicast UDP is default transport; open network exposure without authentication layer
- Files: `docs/architecture.md` (lines 65-77)
- Current mitigation: LCM uses typed messages; SHM transport available for local-only deployment
- Recommendations: Document network isolation requirements; add optional authentication/encryption transport layer; provide security hardening guide for robot deployment

**MCP HTTP Server Exposure:**
- Risk: MCP server binds to `0.0.0.0` by default (all interfaces) on port 9990, exposing robot skills to any network client
- Files: `docs/claude-code.md` (lines 83-89); `docs/cli.md` (lines 107-108)
- Current mitigation: Single MCP server per instance; no per-skill auth granularity
- Recommendations: Default to `localhost` only; add firewall documentation; implement optional API key/token authentication; add rate limiting

**Skill Invocation Without Validation:**
- Risk: `@skill` methods called directly from MCP with user-controlled arguments; no built-in validation beyond type checking
- Files: `docs/agents.md` (lines 56-62)
- Current mitigation: Docstring provides context; skill author responsible for validation
- Recommendations: Add pre/post-condition framework; implement audit logging for skill calls; document security review checklist for new skills

**Environment Variable Exposure:**
- Risk: `.env` file and `OPENAI_API_KEY`, `ANTHROPIC_API_KEY` passed through CLI and environment
- Files: `docs/cli.md` (lines 133-143)
- Current mitigation: Documented as config precedence
- Recommendations: Add secret masking in logs; provide integration with secret management tools; warn if credentials in command history

## Performance Bottlenecks

**High-Bandwidth Stream Transport:**
- Problem: Default LCM transport is multicast UDP; adequate for low-frequency control but becomes bottleneck for video/point clouds
- Files: `docs/architecture.md` (lines 69-80)
- Cause: General-purpose LCM marshalling overhead; network saturation on multi-megabit/s sensor streams
- Improvement path: Documentation already notes SHM/JpegShmTransport alternatives; add performance benchmarks; consider async codecs for large messages; implement adaptive bitrate selection

**Spatial Memory Vector Search:**
- Problem: ChromaDB vector database queries can be slow with large accumulated memory (100k+ embeddings)
- Files: `docs/agents.md` (lines 122-128)
- Cause: Full-table scan behavior in large vector stores; CLIP embedding extraction per-frame adds latency
- Improvement path: Implement spatial indexing (HNSW/IVF); add batch embedding; implement memory eviction policy; add query result caching; benchmark against million+ object queries

**Multi-Module Worker Process Overhead:**
- Problem: Default `--n-workers=2` may cause bottleneck if modules exceed worker pool capacity
- Files: `docs/cli.md` (lines 84-86)
- Cause: Forkserver model; IPC serialization overhead between processes
- Improvement path: Add dynamic worker scaling; implement work-stealing scheduler; profile IPC bottlenecks; add worker pool saturation warnings

## Fragile Areas

**Blueprint Autoconnection Matching:**
- Files: `docs/architecture.md` (lines 41-56)
- Why fragile: Streams wired by `(name, type)` matching; ambiguity detection possible but not documented; silent failures if schemas drift between modules
- Safe modification: Always test blueprint composition changes; add type checking in blueprint tests; document expected stream contracts; use explicit remappings for complex blueprints
- Test coverage: Blueprint composition should have explicit tests verifying all expected connections

**Spec Pattern (Dependency Injection):**
- Files: `docs/architecture.md` (lines 87-99)
- Why fragile: Protocol-based specs resolve at build time; circular dependencies possible; ambiguity if multiple modules implement same Spec
- Safe modification: Use explicit spec assignment rather than relying on auto-detection; validate Spec contracts in tests; document spec requirements per module
- Test coverage: Test Spec resolution with multiple candidate modules; test failure modes

**LCM Topic Namespace Collisions:**
- Files: `docs/cli.md` (lines 46-51)
- Why fragile: No namespace isolation; arbitrary topic names can collide if blueprints extend without coordination; LCM spy shows all topics globally
- Safe modification: Use hierarchical topic naming convention; document topic namespace scheme; add namespace validation in blueprint builder
- Test coverage: Add tests verifying topic names don't collide in complex blueprints

**Agent System Prompt Brittleness:**
- Files: `docs/agents.md` (lines 96-103)
- Why fragile: Default Daneel persona hardcoded; prompt changes can unexpectedly affect behavior; no version tracking for prompts
- Safe modification: Version control system prompts; test major prompt changes with recorded robot data; add prompt validation for common patterns
- Test coverage: Add regression tests for agent behavior with standard test queries

**MCP Tool Discovery:**
- Files: `docs/claude-code.md` (lines 46-82)
- Why fragile: Tool list generated dynamically from `@skill` decorators; removed/renamed skills break Claude Code workflows; no deprecation mechanism
- Safe modification: Add skill versioning/deprecation warnings; maintain backwards compatibility shim for removed skills; validate all skills on startup
- Test coverage: Test that all advertised MCP tools exist and are callable; test skill removal/renames don't crash MCP server

## Scaling Limits

**Single Process LCM Multicast:**
- Current capacity: ~20 concurrent modules before LCM network tuning needed
- Limit: Multicast UDP saturation and LCM queue overflow on systems with poor network tuning (`net.core.rmem_max`)
- Scaling path: Require `sudo sysctl -w net.core.rmem_max=67108864` for production deployments (documented); use SHM transport for local-only; implement DDS bridge for larger fleets

**ChromaDB Memory Footprint:**
- Current capacity: 10k-50k embeddings before noticeable memory growth
- Limit: 1M+ embeddings causes OOM on typical development hardware; vector store doesn't prune old entries
- Scaling path: Implement spatial/temporal clustering; add memory eviction policy; add persistent storage backend; consider Qdrant/Weaviate for distributed deployments

**Worker Process Pool:**
- Current capacity: 2 default workers; linear growth with modules
- Limit: IPC serialization becomes bottleneck with 50+ modules or high-frequency streams
- Scaling path: Profile IPC latency; add dynamic worker scaling; consider shared memory transport for high-frequency paths; implement async RPC batching

**MCP HTTP Server Single Instance:**
- Current capacity: One server per dimos instance
- Limit: Single-threaded HTTP server becomes bottleneck with many concurrent Claude Code requests
- Scaling path: Add MCP server clustering; implement request queuing; add concurrent request limit with backpressure

## Dependencies at Risk

**LCM Maintenance Risk:**
- Risk: LCM is mature but minimal maintenance; LGPL license; C library with Python bindings
- Impact: Breaks if glibc changes; no active development for performance improvements; Darwin fsync issue shows platform-specific fragility
- Migration plan: Monitor LCM upstream; consider migrating to ROS 2 DDS transport for new projects; abstract transport layer to simplify future migration

**ChromaDB Stability:**
- Risk: ChromaDB relatively new (2023+); API changes between versions; SQLite backend default but not production-recommended
- Impact: Vector database schema changes; no backwards compatibility guarantees; persistence issues on network storage
- Migration plan: Pin ChromaDB version; add data migration tests; document backup strategy; plan migration to Qdrant/Milvus if scaling needs arise

**GPT-4o Dependency:**
- Risk: Default agent uses OpenAI GPT-4o; closed-source model; rate limits and costs; API changes without notice
- Impact: Agent functionality blocked if OpenAI API unavailable; cost scaling with deployment count; feature constraints based on API version
- Migration plan: Add Ollama agent as preferred local alternative; document OSS model options; add graceful fallback if API unavailable

**MuJoCo Simulation:**
- Risk: DeepMind MuJoCo; license changed from proprietary to MuJoCo 2.1+ (free but with licensing conditions)
- Impact: Simulation blueprints break if MuJoCo unavailable; physics accuracy depends on MuJoCo version
- Migration plan: Document MuJoCo licensing; consider Gazebo as alternative; implement simulator abstraction layer

## Test Coverage Gaps

**Cross-Platform Nix Environment:**
- What's not tested: Darwin (macOS) LCM fsync patch; NVIDIA GPU symlink workaround; pkg-config paths on Apple Silicon
- Files: `flake.nix` (lines 142-168, 204-210)
- Risk: Patches and workarounds only validated during manual testing; CI likely Linux-only; macOS developers may encounter broken environments
- Priority: High - affects developer experience and deployment consistency

**MCP Protocol Stability:**
- What's not tested: MCP protocol version compatibility; breaking changes between Claude Code versions; MCP server crash recovery
- Files: `docs/claude-code.md` (lines 176-183)
- Risk: MCP is experimental; no contract tests with Claude Code integration; silent failures if protocol diverges
- Priority: High - experimental feature; must stabilize before production use

**Blueprint Composition Edge Cases:**
- What's not tested: Circular Spec dependencies; ambiguous stream name matching; remapping with type mismatches; disabled modules with dependent modules
- Files: `docs/architecture.md` (lines 41-56, 87-99)
- Risk: Silent failures during blueprint.build(); complex blueprints may fail in unpredictable ways; no error recovery
- Priority: High - foundational pattern; breaks all dependent blueprints

**Skill Parameter Validation:**
- What's not tested: Unsupported parameter types passed to `@skill`; docstring parsing edge cases; circular return value serialization
- Files: `docs/agents.md` (lines 56-62)
- Risk: Skills fail at runtime with unclear errors; type validation not enforced; breaking changes to `@skill` decorator rules
- Priority: Medium - affects skill authors; good error messages would reduce debugging time

**Multi-Robot Fleet Coordination:**
- What's not tested: Fleet mode with 3+ robots; robot death/recovery during fleet operation; load balancing with heterogeneous robot types
- Files: `docs/robots.md` (lines 19); `docs/examples.md` (lines 95-102)
- Risk: Fleet control only lightly tested; scaling to 10+ robots may reveal LCM broadcast issues; no documented failure modes
- Priority: Medium - advanced feature; most deployments use single robot

**Teleop Input Latency:**
- What's not tested: VR teleop latency with real-time constraints; network jitter impact on arm control; graceful degradation with packet loss
- Files: `docs/robots.md` (lines 100-111); various teleop blueprints
- Risk: Teleop feels laggy in production; no documented latency targets; no jitter compensation
- Priority: Medium - UX critical for VR teleop; but limited deployment scope

## Missing Critical Features

**Skill Deprecation Mechanism:**
- Problem: No way to deprecate skills gracefully; skill removal breaks existing Claude Code workflows
- Blocks: Large-scale skill library maintenance; backwards compatibility guarantees
- Solution: Add deprecation decorator; implement compatibility shims; version skills; add warnings to deprecated skill calls

**Spatial Memory Pruning:**
- Problem: ChromaDB accumulates embeddings indefinitely; no automatic cleanup or memory management
- Blocks: Long-running robots; memory management; repeatable deployments
- Solution: Implement spatial/temporal clustering; add configurable memory limits; add eviction policies; add explicit memory management commands

**Skill Authorization/Capability Boundaries:**
- Problem: All skills equally accessible via MCP; no way to restrict dangerous skills (e.g., backflip, fast movement)
- Blocks: Safe human-robot collaboration; multi-user deployments; production safety requirements
- Solution: Add skill capability levels; implement per-user/role access control; add emergency stop integration; document safety model

**Network Isolation & Security Hardening:**
- Problem: No built-in authentication, encryption, or rate limiting for MCP/LCM
- Blocks: Deployment in shared networks; IoT integration; compliance requirements
- Solution: Add optional mTLS for MCP; implement API key authentication; add network namespace isolation; document security architecture

**Observability & Debugging Tools:**
- Problem: Limited built-in tracing; MCP errors not well-documented; blueprint composition failures are opaque
- Blocks: Production debugging; root cause analysis of failures; performance profiling
- Solution: Add structured logging with correlation IDs; implement distributed tracing; add MCP request/response logging; enhance error messages

---

*Concerns audit: 2026-03-17*
