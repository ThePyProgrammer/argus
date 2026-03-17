# CLI Reference

The `dimos` CLI is the primary entry point. Built with Typer.

## Core Commands

```bash
dimos run <blueprint> [--daemon]    # Start a blueprint (optionally backgrounded)
dimos status                        # Show running instance info (PID, uptime, blueprint)
dimos stop [--force]                # Graceful stop (SIGTERM -> SIGKILL after 5s)
dimos restart [--force]             # Stop + re-exec with original args
dimos list                          # List all non-demo blueprints
dimos show-config                   # Print resolved GlobalConfig values
```

## Logging

```bash
dimos log                           # View current run logs
dimos log -f                        # Follow logs (tail -f style)
dimos log -n 100                    # Last 100 lines
dimos log --json                    # JSON-formatted output
dimos log -r <run-id>               # Logs for a specific run
```

Logs are stored at `~/.local/state/dimos/logs/<run-id>/main.jsonl`.

## Agent Interaction

```bash
dimos agent-send "explore the room"    # Send text to running agent via LCM
dimos humancli                          # Interactive agent terminal
dimos agentspy                          # Agent monitoring tool
```

## MCP Subcommands

```bash
dimos mcp list-tools                    # JSON list of all exposed skills
dimos mcp call <tool> --arg key=value   # Invoke a tool
dimos mcp call <tool> --json-args '{}'  # Invoke with JSON args
dimos mcp status                        # Server health (PID, modules, skills)
dimos mcp modules                       # Module-to-skills mapping
```

## Topic Subcommands

```bash
dimos topic echo <topic>               # Subscribe and print messages on a topic
dimos topic send <topic> <expr>        # Publish a message to a topic
```

## Other Tools

```bash
dimos lcmspy                           # LCM spy monitoring
dimos top                              # Live resource monitor TUI
dimos rerun-bridge                     # Launch Rerun visualization standalone
```

## Global Flags

Every `GlobalConfig` field is available as a CLI flag:

### Connection
| Flag | Default | Description |
|---|---|---|
| `--robot-ip` | None | Robot IP address |
| `--robot-ips` | None | Multiple robot IPs (fleet mode) |

### Mode
| Flag | Default | Description |
|---|---|---|
| `--simulation` | false | Enable MuJoCo simulation |
| `--replay` | false | Use recorded replay data |
| `--replay-dir` | "go2_sf_office" | Replay data directory |

### Visualization
| Flag | Default | Description |
|---|---|---|
| `--viewer` | "rerun" | Backend: `rerun`, `rerun-web`, `foxglove`, `none` |

### Performance
| Flag | Default | Description |
|---|---|---|
| `--n-workers` | 2 | Worker process count |
| `--memory-limit` | "auto" | Memory limit per worker |

### Navigation
| Flag | Default | Description |
|---|---|---|
| `--planner-strategy` | "simple" | Path planning strategy |
| `--planner-robot-speed` | None | Robot speed for planning |
| `--obstacle-avoidance` | true | Enable obstacle avoidance |
| `--robot-width` | 0.3 | Robot width in meters |
| `--robot-rotation-diameter` | 0.6 | Rotation diameter |

### Perception
| Flag | Default | Description |
|---|---|---|
| `--detection-model` | "moondream" | Vision-language model name |
| `--new-memory` | false | Start fresh spatial memory |

### MCP
| Flag | Default | Description |
|---|---|---|
| `--mcp-port` | 9990 | MCP server port |
| `--mcp-host` | "0.0.0.0" | MCP server host |

### Simulation
| Flag | Default | Description |
|---|---|---|
| `--mujoco-camera-position` | None | Camera position in sim |
| `--mujoco-room` | None | Simulation room |
| `--mujoco-start-pos` | "-1.0, 1.0" | Start position |
| `--mujoco-steps-per-frame` | 7 | Physics steps per frame |

### Monitoring
| Flag | Default | Description |
|---|---|---|
| `--dtop` | false | Enable dtop monitoring |

## Configuration Cascade

Settings are resolved in this order (later overrides earlier):

1. **Defaults** -- hardcoded in `GlobalConfig`
2. **`.env` file** -- in project root
3. **Environment variables** -- prefixed with `DIMOS_` (e.g., `DIMOS_MCP_PORT=9990`)
4. **Blueprint overrides** -- set in code
5. **CLI flags** -- highest priority

## Environment Variables

Common env vars:

```bash
ROBOT_IP=192.168.123.161       # Robot IP
OPENAI_API_KEY=sk-...          # For GPT-4o agent
ANTHROPIC_API_KEY=sk-ant-...   # For Anthropic models
DIMOS_MCP_PORT=9990            # MCP server port
DIMOS_MCP_HOST=0.0.0.0        # MCP server host
```

## Install Extras

```bash
pip install 'dimos[base]'                    # agents + web + perception + vis + sim
pip install 'dimos[base,unitree]'            # + Unitree support
pip install 'dimos[agents]'                  # LangChain, Ollama, Anthropic, OpenAI, Whisper
pip install 'dimos[perception]'              # Ultralytics, transformers, Moondream
pip install 'dimos[manipulation]'            # Drake, Piper SDK, RealSense, xArm SDK
pip install 'dimos[web]'                     # FastAPI, uvicorn
pip install 'dimos[sim]'                     # MuJoCo, PyGame
pip install 'dimos[cuda]'                    # GPU inference
pip install 'dimos[cpu]'                     # CPU inference
pip install 'dimos[dev]'                     # Ruff, MyPy, pytest
```

For dev install:
```bash
git clone https://github.com/dimensionalOS/dimos.git
cd dimos
uv sync --all-extras --no-extra dds
```
