# Architecture

**Analysis Date:** 2026-03-17

## Pattern Overview

**Overall:** Modular actor-based architecture with automated stream wiring

**Key Characteristics:**
- Modules run as autonomous subsystems in forkserver worker processes
- Typed pub/sub channels (Streams) connect modules across process boundaries
- Blueprints compose and deploy module networks with automatic wiring
- Remote Procedure Calls (RPC) enable cross-process method invocation
- Dependency injection via Protocol-based Specs for runtime type resolution

## Layers

**Module Layer (Core Computation):**
- Purpose: Autonomous subsystems encapsulating single responsibilities (perception, control, planning, agents)
- Location: DimOS package (`dimos.core.Module`) - installed via pip, not in this repo
- Contains: Module classes with In/Out streams, @rpc/@skill decorated methods, lifecycle hooks
- Depends on: Stream primitives, RPC decorators, type system
- Used by: Blueprint layer for composition and orchestration

**Stream Layer (Pub/Sub Transport):**
- Purpose: Typed message channels between modules, handling serialization and transport mechanics
- Location: DimOS package (`dimos.core.streams`)
- Contains: In[T], Out[T], RemoteIn[T], RemoteOut[T] stream primitives
- Depends on: Type system, transport implementations, serialization backends
- Used by: Module layer (stream declarations), transport layer (routing)

**Blueprint Layer (Composition & Deployment):**
- Purpose: Compose modules into deployable systems, wire streams automatically, resolve dependencies
- Location: DimOS package (`dimos.core.blueprints`)
- Contains: Blueprint class, autoconnect() function, configuration injection
- Depends on: Module layer, Spec protocol layer
- Used by: Entry points (CLI, scripts) that build and execute systems

**Transport Layer (Cross-Process Communication):**
- Purpose: Serialize and route messages between processes using various backends
- Location: DimOS package (`dimos.transport.*`)
- Contains: LCMTransport, SHMTransport, pLCMTransport, ROSTransport, DDSTransport, JpegLcmTransport, JpegShmTransport
- Depends on: Message types, serialization libraries (LCM, protocol buffers, pickle, OpenCV JPEG)
- Used by: Stream layer (pluggable backends)

**RPC Layer (Remote Method Calls):**
- Purpose: Enable method invocation across process boundaries with automatic marshaling
- Location: DimOS package (`dimos.core.rpc`)
- Contains: @rpc decorator, @skill decorator (implies @rpc + agent exposure)
- Depends on: Transport layer, serialization, type system
- Used by: Modules (method declarations), agents (tool discovery)

**Spec/Dependency Injection Layer:**
- Purpose: Type-safe runtime resolution of module dependencies
- Location: DimOS package (`dimos.core.specs`)
- Contains: Spec base class, Protocol-based interface declarations
- Depends on: Python typing system
- Used by: Blueprint builder (dependency resolution at build time)

**Configuration Layer (GlobalConfig):**
- Purpose: Cascade-based configuration management for system behavior
- Location: DimOS package (`dimos.config.GlobalConfig`)
- Contains: Configuration fields for connection, mode, visualization, performance, navigation, perception, MCP, simulation, monitoring
- Depends on: CLI framework (Typer), environment variables
- Used by: Modules and blueprints for runtime behavior control

**CLI/Entry Point Layer:**
- Purpose: Command-line interface to start, monitor, and control DimOS instances
- Location: DimOS package (`dimos.cli`)
- Contains: run, status, stop, log, agent-send, mcp, topic, lcmspy, top commands
- Depends on: Blueprint layer, configuration layer, transport monitoring
- Used by: Users/operators via `dimos` command

## Data Flow

**Blueprint Build & Module Startup:**

1. User invokes `dimos run <blueprint>` with optional config flags
2. CLI resolves configuration cascade (defaults → .env → env vars → flags)
3. Blueprint builder is called with resolved GlobalConfig
4. Blueprint.build() triggers module instantiation and stream wiring:
   - Autoconnect matches stream names and types across modules
   - Spec dependencies are resolved by type
   - Transport backends are assigned per stream (or per transport policy)
5. Each module is launched in a worker process via forkserver
6. Modules call start() lifecycle hook, subscribe to input streams
7. Stream connections transition: UNBOUND → READY → CONNECTED
8. Main process continues, monitoring module health

**Streaming Data Path:**

1. Module A publishes message to Out[T] stream
2. Stream serializes message using assigned Transport
3. For local streams (same process): direct callback invocation
4. For remote streams (different process): Transport sends serialized bytes (LCM multicast, SHM, etc.)
5. Module B receives via In[T] stream, Transport deserializes
6. Module B's subscription callback (_on_message) invoked with typed message
7. Module B may process and publish to its own Out[T] streams

**RPC Call Path:**

1. Caller invokes @rpc or @skill decorated method on module reference
2. If local: direct function call with return value
3. If remote: RPC marshals arguments, sends request through Stream-based transport
4. Remote module receives RPC request, invokes actual method
5. Return value marshaled back through same transport
6. Caller receives typed return value

**Agent Skill Discovery & Tool Binding:**

1. Agent module (in-process or via MCP client) scans running modules at startup
2. Discovers all @skill decorated methods using reflection
3. Extracts docstrings, parameter types, return types
4. Converts skills to LangChain StructuredTools with schemas
5. LLM agent uses tool calling to invoke skills
6. Agent calls skill via RPC (if remote module) or direct method (if in-process)

**MCP Server Data Flow (Claude Code Integration):**

1. DimOS starts McpServer module in blueprint
2. McpServer exposes HTTP JSON-RPC 2.0 endpoint on port 9990
3. Claude Code connects via `claude mcp add --transport http dimos http://localhost:9990/mcp`
4. Claude Code calls tools/list endpoint to discover available skills
5. Claude Code calls tools/call endpoint with tool name + arguments
6. McpServer forwards to in-process skill modules (or to agent if agent-forward mode)
7. Skill executes via RPC to target module
8. Result marshaled back through HTTP to Claude Code

**State Management:**

- **Module State:** Encapsulated within each module instance, accessed via @property or @rpc methods
- **Global State:** Minimal; configuration (GlobalConfig) injected at startup
- **Stream State:** Pub/sub is stateless; subscribers receive published messages in order
- **Spatial Memory State:** ChromaDB persistent vector database shared via In/Out streams
- **Agent State:** LangChain conversation history + tool bindings, stored in-process
- **Stream Connection State:** UNBOUND (not yet wired) → READY (connected but no activity) → CONNECTED (messages flowing)

## Key Abstractions

**Module:**
- Purpose: Autonomous subsystem with single responsibility
- Examples: `dimos.core.Module` base class, `CameraModule`, `DetectionModule`, `Agent`, `Navigator`, `McpServer`
- Pattern: Declares In[T]/Out[T] streams, implements lifecycle hooks (start, stop), exposes @rpc/@skill methods

**Stream (In[T]/Out[T]):**
- Purpose: Typed message channel with pub/sub semantics
- Examples: `In[Image]`, `Out[Detection]`, `In[PoseStamped]`, `Out[str]` (messages)
- Pattern: Type-safe at declaration; transport and serialization pluggable; state transitions UNBOUND → READY → CONNECTED

**Blueprint:**
- Purpose: Declarative composition of modules + streams into deployable system
- Examples: `unitree-go2`, `unitree-go2-agentic`, `unitree-go2-agentic-mcp`
- Pattern: Factory functions that return blueprint objects; autoconnect() wires streams by (name, type) matching

**Spec/Protocol (Dependency Injection):**
- Purpose: Interface for runtime module dependency resolution
- Examples: `NavigatorSpec`, `PerceptionSpec`, `AgentSpec` (Python Protocol classes)
- Pattern: Module declares `_navigator: NavigatorSpec`, blueprint resolves to concrete module instance with that interface

**Transport:**
- Purpose: Mechanism for serializing and routing messages between processes
- Examples: LCMTransport (multicast UDP), SHMTransport (shared memory), ROSTransport (ROS 2 bridge), DDSTransport
- Pattern: Pluggable per stream or globally; LCM is default for low-bandwidth, SHM for high-bandwidth (video/point clouds)

**@skill Decorator:**
- Purpose: Exposes module method to agents and MCP with required validation
- Pattern: Requires docstring, typed parameters, string return; implies @rpc; enables tool calling from LLM agents
- Used by: Agent skill discovery, MCP tool listing, Claude Code

**@rpc Decorator:**
- Purpose: Marks method as remotely callable across process boundaries
- Pattern: Automatically marshals arguments/return values; works with all transports
- Used by: Inter-module communication, agent skill invocation

**GlobalConfig:**
- Purpose: Unified configuration object passed to all modules at build time
- Contains: Connection (robot-ip, robot-ips), Mode (simulation, replay, replay-dir), Visualization (viewer), Performance (n-workers, memory-limit), Navigation, Perception, MCP, Monitoring
- Pattern: Cascade resolution (defaults → .env → env vars → CLI flags → blueprint overrides)

## Entry Points

**CLI (dimos command):**
- Location: DimOS package (`dimos.cli`)
- Triggers: User invokes `dimos run <blueprint>` or other subcommands
- Responsibilities: Parse config, instantiate blueprint, deploy modules, handle lifecycle (stop, restart), expose monitoring/debugging tools

**Blueprint Functions:**
- Location: Module-specific blueprints (e.g., `dimos.robot.unitree.go2.blueprints.unitree_go2()`)
- Triggers: Called by `dimos run` with resolved GlobalConfig
- Responsibilities: Compose modules, configure streams, return Blueprint object ready for build()

**Python API (import + build):**
- Location: Direct imports of modules and autoconnect
- Triggers: User writes Python script importing dimos modules
- Responsibilities: Assemble blueprint programmatically, call build().loop() to deploy and block

**MCP Server:**
- Location: DimOS package (`dimos.agents.mcp.mcp_server`)
- Triggers: Blueprint includes McpServer module
- Responsibilities: Expose skills via HTTP JSON-RPC 2.0, serve Claude Code and other MCP clients

## Error Handling

**Strategy:** Hierarchical with recovery protocols; failures in modules logged and surfaced to agents

**Patterns:**

- **Stream Connection Failures:** Module startup fails if stream cannot connect within timeout; error logged to console and agent message
- **RPC Timeouts:** Remote method calls timeout after configurable duration; error returned to caller, agent offered retry
- **Module Crashes:** Worker process crash detected by parent; module marked FAILED in monitoring; agent may reattempt or escalate
- **Serialization Errors:** Message deserialization failures logged; stream continues (dropped message); no backpressure
- **Spec Resolution Ambiguity:** Multiple modules matching same Spec detected at build time; build fails with clear error listing candidates
- **Configuration Errors:** GlobalConfig validation at startup; missing required fields or invalid values cause early exit with usage help

## Cross-Cutting Concerns

**Logging:** Python standard logging module; each module logs to `dimos.<module_name>` logger; JSON formatted to `~/.local/state/dimos/logs/<run-id>/main.jsonl` via structured logging

**Validation:**
- Parameter validation in @skill methods (type annotations enforced by tool schema generation)
- Stream type checking at autoconnect time (name + type matching)
- Configuration schema validation via GlobalConfig dataclass
- RPC argument marshaling validates types

**Authentication:**
- Robot IP authentication via network-level (direct Unitree protocol)
- MCP authentication: HTTP endpoint accessible to localhost only by default (configurable via --mcp-host)
- API keys (OpenAI, Anthropic) injected via environment variables, not in config files

**Permission/Authorization:**
- No explicit permission system; skill methods assume caller has authority to execute them
- Physical robot safety enforced at low level (motor command validation, speed limits)
- MCP server access control: currently open on configured host:port (security responsibility on network layer)

---

*Architecture analysis: 2026-03-17*
