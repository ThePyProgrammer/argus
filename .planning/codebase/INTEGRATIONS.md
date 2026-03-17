# External Integrations

**Analysis Date:** 2026-03-17

## APIs & External Services

**LLM & Language Models:**
- OpenAI (GPT-4o) - Default agentic reasoning model
  - SDK: `langchain-openai`, `openai`
  - Auth: `OPENAI_API_KEY` env var
  - Used by: Agent module for task planning and reasoning

- Anthropic (Claude models) - Alternative LLM support
  - SDK: `anthropic`
  - Auth: `ANTHROPIC_API_KEY` env var
  - Used by: Optional agent configuration

- Ollama - Local LLM inference (offline)
  - SDK: `langchain-ollama`, `ollama`
  - Connection: HTTP localhost by default
  - Used by: `unitree-go2-agentic-ollama`, `dimos[agents]` extra

**Vision & Perception:**
- Moondream - Vision-language model for scene understanding
  - SDK: Integrated via `moondream` package
  - Used by: `--detection-model moondream` default

- HuggingFace Transformers Hub
  - SDK: `transformers`, `langchain-huggingface`
  - Models: BERT embeddings, vision transformers
  - Used by: Perception pipeline, spatial memory embeddings

- Ultralytics - Object detection models (YOLO)
  - SDK: `ultralytics`
  - Models: Auto-downloaded from Ultralytics hub
  - Used by: Detection modules across all robot blueprints

**Speech & Audio:**
- OpenAI Whisper - Speech-to-text
  - SDK: `openai-whisper`
  - Used by: Web human input module for voice commands
  - Connection: Local inference via PyTorch

**Maps & Navigation:**
- Google Maps API - Optional navigation integration
  - SDK: `googlemaps`
  - Auth: Google API key (optional)
  - Used by: `google_maps_skill` for geolocation queries
  - Blueprints: GPS navigation when available

- OpenStreetMap - Open mapping data
  - SDK: Integrated via utilities
  - Used by: Outdoor navigation skills
  - Blueprints: GPS-based waypoint navigation

## Data Storage

**Databases:**
- ChromaDB - Vector database for spatial memory
  - Client: `langchain-chroma`
  - Purpose: Persistent storage of CLIP embeddings, scene descriptions, object detections
  - Scope: Per-run memory (tagged locations, visual search index)
  - Configuration: In-process by default, can be externalized

- PostgreSQL (optional, psql extra)
  - Client: `psycopg2-binary`
  - Purpose: Production spatial memory persistence
  - When used: `dimos[psql]` extra for distributed deployments

**File Storage:**
- Local filesystem only
  - Recorded replay data stored at `~/.local/state/dimos/logs/`
  - Recording format: LCM topic subscriptions

## Authentication & Identity

**API Keys Required:**
- `OPENAI_API_KEY` - For GPT-4o agent (optional, enables agentic control)
- `ANTHROPIC_API_KEY` - For Claude models (optional)
- Google Maps API key - For `google_maps_skill` (optional)

**Default (No Auth):**
- Robot connection via IP address + WebRTC/LCM (no authentication required)
- Local Ollama - Unauthenticated local HTTP
- Whisper STT - Local model inference

## Monitoring & Observability

**Error Tracking:**
- Not detected - Errors logged via structlog, no external error tracking service configured

**Logs:**
- Structured logging via `structlog` with JSON output
- Location: `~/.local/state/dimos/logs/<run-id>/main.jsonl`
- CLI: `dimos log -f` for live following
- Format: JSON with context, level, message fields

**Visualization & Debugging:**
- Rerun SDK - Real-time 3D/2D visualization
  - Web-based or local viewer
  - Connection: Optional (default viewer: `rerun`)
  - Alternatives: `rerun-web`, `foxglove`, or none

- Agent monitoring: `dimos agentspy` CLI tool for real-time agent reasoning traces

## CI/CD & Deployment

**Hosting:**
- Docker container via Nix build: `nix build .#devcontainer`
- Image: `dimensionalos/dimos-dev:latest`
- Deployment: Bare metal (robot + control machine) or cloud edge

**CI Pipeline:**
- Not detected - Pre-commit hooks available via `pre-commit install`
- Testing: `pytest` with asyncio support (dev extra)
- Type checking: `mypy` (dev extra)
- Linting: `ruff` (dev extra)

**Development Workflow:**
- Pre-commit hooks: Configured via `.pre-commit-config.yaml` if present
- Test suite: `pytest` with plugins for async, mocking, env variables, timeout
- Code quality: Ruff for linting, MyPy for type checking

## Environment Configuration

**Required env vars:**
- `OPENAI_API_KEY` - For GPT-4o (optional, `--replay` mode works without it)
- `ROBOT_IP` - For real robot control (optional, replay/simulation work without)

**Optional env vars:**
- `ANTHROPIC_API_KEY` - For Claude models
- `DIMOS_MCP_PORT` - MCP server port (default 9990)
- `DIMOS_MCP_HOST` - MCP server listen host (default 0.0.0.0)
- `GIT_LFS_SKIP_SMUDGE` - Set to 1 for shallow clones of dimos repo

**Secrets location:**
- Environment variables only (no .env file committed)
- `.env` file pattern supported but should not be committed

## Webhooks & Callbacks

**Incoming (HTTP Endpoints):**
- MCP Server on port 9990 - JSON-RPC 2.0 interface for Claude Code integration
  - Endpoint: `POST http://localhost:9990/mcp`
  - Methods: `initialize`, `tools/list`, `tools/call`
  - Protocol: HTTP only (no stdio/SSE in current beta)

- Web Human Input module (when enabled)
  - Port: 5555 (configurable)
  - Features: Text chat, voice input (Whisper), browser UI

- FastAPI web interface (when web extra enabled)
  - Configurable port, provides REST endpoints for blueprint control

**Outgoing:**
- Robot WebRTC connection - Two-way video/command channel to Unitree robots
- LCM broadcast - Multicast UDP (224.0.0.251:7667 default) for module communication
- Optional ROS 2 bridge - Bidirectional topic translation
- Optional DDS transport - CycloneDDS pub/sub for fleet communication

## Multi-Robot / Fleet Integration

**Fleet Control:**
- Multiple robot IPs via `--robot-ips "192.168.1.161,192.168.1.162"`
- Blueprints: `unitree-go2-fleet`, `phone-go2-fleet-teleop`
- Communication: LCM multicast with per-robot topics, CycloneDDS for distributed deployments

**Robot Hardware Support:**
- Unitree Go2 Pro/Air (quadruped) - Primary, full stack support
- Unitree B1 (quadruped) - Experimental
- Unitree G1 (humanoid) - 11 blueprints with simulation
- xArm (6/7 DOF arms) - Manipulation via Drake planning
- AgileX Piper (arm) - Cartesian control
- DJI/MAVLink drones - Via RosettaDrone bridge
- Generic USB cameras, RealSense, ZED, Livox LiDAR - Pluggable sensor modules

## Cloud Integrations

**Not Detected:**
- No S3 / cloud storage integration
- No cloud compute (all inference local or via API keys)
- No serverless functions
- No managed message queues

---

*Integration audit: 2026-03-17*
