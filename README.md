# Dimensional Applications

Development environment and documentation for working with [DimOS](https://github.com/dimensionalOS/dimos) -- an agentic operating system for generalist robotics.

## Quick Start

```bash
# Enter the Nix dev shell (provides Python 3.12, system deps, etc.)
nix develop

# Install dimos with common extras
pip install 'dimos[base,unitree]'

# Run in replay mode (no hardware or API keys needed)
dimos --replay run unitree-go2

# Run with LLM agent
export OPENAI_API_KEY=...
dimos --replay run unitree-go2-agentic

# Run with MCP server (for Claude Code integration)
dimos --replay run unitree-go2-agentic-mcp --daemon
```

## Documentation

| Document | Description |
|---|---|
| [Architecture](docs/architecture.md) | Modules, streams, blueprints, transports |
| [Robots & Hardware](docs/robots.md) | Supported platforms, sensors, blueprints |
| [Agents & Skills](docs/agents.md) | LLM agents, MCP, skills system |
| [CLI Reference](docs/cli.md) | All commands, flags, configuration |
| [Claude Code Integration](docs/claude-code.md) | Using dimos as an MCP server with Claude Code |
| [Examples](docs/examples.md) | Workflows for replay, simulation, real robots |

## Nix Environment

This repo provides a Nix flake with two dev shells:

- `nix develop` -- blends with your current environment
- `nix develop .#isolated` -- strict isolated shell (xome-based, fake home)

The flake provides: Python 3.12, portaudio, ffmpeg, OpenGL/X11/GTK, GStreamer, LCM, CycloneDDS, Open3D build deps, and documentation tools.

A Docker image can be built with `nix build .#devcontainer`.
