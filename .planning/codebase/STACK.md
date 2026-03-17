# Technology Stack

**Analysis Date:** 2026-03-17

## Languages

**Primary:**
- Python 3.12 - Core robotics framework, agent orchestration, and module implementations

**Secondary:**
- C++ - Via LCM interop, Open3D, Drake, and robot driver integrations
- Lua - Language interop support via LCM transport
- TypeScript - Language interop support via LCM transport

## Runtime

**Environment:**
- Python 3.12 (installed via Nix flake)
- Requires Python 3.10+

**Package Manager:**
- pip / uv (modern virtual environment setup)
- Lockfile: Present via venv at `.venv/`

**Development Shell:**
- Nix flakes for reproducible dev environment (`flake.nix`, `flake.lock`)
- Supports both standard (`nix develop`) and isolated (`nix develop .#isolated`) shells

## Frameworks

**Core:**
- dimos 0.0.11 - Main robotics OS framework for agent-native robotics
  - Module-based architecture with streaming pub/sub
  - Blueprint composition system for wiring modules
  - RPC and skill decoration for cross-process communication

**Agents & LLM:**
- LangChain 1.2.3 - Agent orchestration and tool calling
- LangChain-OpenAI 1.x - GPT-4o integration
- LangChain-Anthropic - Support for Claude/Anthropic models
- OpenAI - Direct OpenAI API access
- Ollama 0.6.0+ - Local LLM inference (offline)
- Anthropic 0.85.0+ - Claude API integration

**Web & API:**
- FastAPI 0.115.6+ - REST API framework for blueprints
- Uvicorn 0.34.0+ - ASGI server
- FFmpeg-python - Media handling via ffmpeg-python
- SSE-Starlette 2.2.1+ - Server-sent events support

**Perception & Vision:**
- Ultralytics 8.3.70+ - Object detection (YOLO), person tracking
- Transformers 4.49.0 - Vision transformers and foundational models
- Moondream - Vision-language model
- OpenClip 3.2.0 - CLIP embeddings for spatial memory search
- OpenCV - Computer vision operations (cv2)
- Pillow - Image processing
- PyTurboJPEG 1.8.2 - JPEG compression for bandwidth-efficient video

**Spatial Memory & Database:**
- ChromaDB (langchain-chroma <2.0) - Vector database for spatial memory
- LangChain-HuggingFace <2.0 - Embeddings via HuggingFace
- Sentence-Transformers - Text/image embedding models

**Visualization:**
- Rerun SDK 0.20.0+ - 3D/2D data visualization and debugging
- dimos-viewer 0.30.0a4 - Custom visualization backend

**Simulation:**
- MuJoCo 3.3.4+ - Physics simulation engine
- PyGame 2.6.1+ - Event handling and graphics
- Playground 0.0.5 - Simulation utilities

**Message Passing & Transport:**
- dimos-lcm 0.1.2 - LCM (Lightweight Communications & Marshalling)
- CycloneDDS 0.10.5+ - DDS pub/sub (optional via `dimos[dds]`)
- reactivex - Reactive programming for stream operations
- protobuf <7.0, >=6.33.5 - Binary message serialization

**CLI & Terminal UI:**
- Typer <1.0 - CLI framework for dimos commands
- Textual 3.7.1 - TUI framework
- TerminalTextEffects 0.12.2 - CLI effects
- Plotext 5.3.2 - Terminal plotting

**Data & Serialization:**
- Pydantic - Data validation and serialization
- Pydantic-Settings <3.0 - Configuration management
- Annotation-Protocol 1.4.0+ - Protocol-based dependency injection

**Numeric & Processing:**
- NumPy 1.26.4+ - Numerical arrays and operations
- SciPy 1.15.1+ - Scientific computing
- Numba 0.60.0+ - JIT compilation for performance
- FilterPy 1.4.5+ - Kalman filtering
- LAP 0.5.12+ - Hungarian algorithm for object tracking

**Robot Integrations:**
- unitree-webrtc-connect-leshy 2.0.7+ - Unitree robot WebRTC connection
- piper-sdk - AgileX Piper arm control
- xarm-python-sdk 1.17.0+ - xArm manipulation
- pyrealsense2 - Intel RealSense camera
- Drake (manipulation extra) - Motion planning
- pymavlink - MAVLink drone protocol

**Logging & Monitoring:**
- Structlog <26, >=25.5.0 - Structured logging
- Colorlog 6.9.0 - Colored terminal output
- PSUtil 7.0.0+ - System monitoring

**Audio & Speech:**
- OpenAI Whisper - Speech-to-text (STT)
- sounddevice - Audio input/output
- PortAudio (Nix) - Audio I/O library
- soundfile - WAV/FLAC file operations

**Graphics & Rendering (Nix):**
- GTK 3 - GUI toolkit
- GLib/GObject - Core GNOME libraries
- GStreamer (all plugins) - Multimedia framework
- OpenGL, Mesa, GLFW - 3D graphics
- SDL2 - Multimedia library
- X11 stack - Display server (Linux only)
- libGL, libGLU - OpenGL support

**Other Core Dependencies:**
- plum-dispatch 2.5.7 - Multiple dispatch
- sortedcontainers 2.4.0 - Ordered data structures
- lazy_loader - Dynamic module loading
- pin 3.3.0+ - Dependency resolution
- python-dotenv - Environment variable loading
- toolz 1.1.0+ - Functional utilities

## Configuration

**Environment:**
- Configuration via environment variables (prefixed with `DIMOS_`)
- `.env` file support for local overrides
- GlobalConfig cascade: defaults → .env → env vars → blueprint → CLI flags

**Build:**
- Nix flake-based dev environment (`flake.nix`, `flake.lock`)
- Python venv for isolated dependencies
- No setup.py or pyproject.toml in this repo (installed from external dimos package)

**Key Configuration Variables:**
- `OPENAI_API_KEY` - OpenAI API key for GPT-4o agent
- `ANTHROPIC_API_KEY` - Anthropic API key for Claude models
- `ROBOT_IP` - Target robot IP address
- `DIMOS_MCP_PORT` - MCP server port (default 9990)
- `DIMOS_MCP_HOST` - MCP server host (default 0.0.0.0)

## Platform Requirements

**Development:**
- Python 3.10, 3.11, or 3.12
- Nix (for reproducible development environment)
- Git LFS (for recording data)
- System libraries: portaudio, ffmpeg, graphics stack (X11/OpenGL on Linux)
- Supported on Linux and macOS

**Production:**
- Linux (Ubuntu 22.04/24.04 tested, NixOS supported)
- macOS (experimental)
- Docker (via Nix-built container: `nix build .#devcontainer`)
- GPU: CUDA support via `dimos[cuda]` extra (for fast inference)
- CPU inference via `dimos[cpu]` extra (ONNXRuntime, ctransformers)

**Optional Runtimes:**
- MuJoCo - For physics simulation
- Ollama - For local LLM execution
- ROS 2 - For interop (bridges available)
- Docker - For containerized deployment

---

*Stack analysis: 2026-03-17*
