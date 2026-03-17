# Claude Code Integration

DimOS exposes robot skills as MCP (Model Context Protocol) tools that Claude Code can call directly. This lets you control robots through natural language in your terminal.

## How It Works

DimOS runs an MCP server (HTTP JSON-RPC 2.0) that exposes all `@skill`-decorated methods as tools. Claude Code connects to this server and can invoke any skill -- moving the robot, querying spatial memory, navigating to locations, etc.

```
Claude Code  --HTTP-->  DimOS MCP Server (port 9990)  --RPC-->  Robot Modules
```

## Setup

### 1. Start DimOS with MCP enabled

```bash
# Replay mode (no hardware needed)
dimos --replay run unitree-go2-agentic-mcp

# Or as a daemon
dimos --replay run unitree-go2-agentic-mcp --daemon

# Real robot
dimos run unitree-go2-agentic-mcp --robot-ip 192.168.123.161

# Simulation
dimos --simulation run unitree-g1-agentic-sim
# Note: G1 sim doesn't ship with MCP by default; see "Adding MCP to other blueprints" below
```

### 2. Register with Claude Code

```bash
claude mcp add --transport http --scope project dimos http://localhost:9990/mcp
```

### 3. Verify

```bash
claude mcp list
```

You should see `dimos` listed. Claude Code will now have access to all dimos skills as tools.

## Available MCP Tools

### Built-in (always available)

| Tool | Description |
|---|---|
| `server_status` | Reports PID, deployed modules, skill inventory |
| `list_modules` | Module-to-skill mappings |
| `agent_send` | Send messages to the running LLM agent |

### Go2 Robot Skills

| Tool | Description |
|---|---|
| `relative_move` | Move forward/backward/left/right by distance |
| `navigate_with_text` | Navigate to a described location |
| `observe` | Observe the environment |
| `tag_location` | Tag current position with a name |
| `stop_navigation` | Stop moving |
| `execute_sport_command` | Run motor routines (flips, dances, etc.) |
| `speak` | Text-to-speech output |
| `follow_person` | Follow a described person |
| `wait` | Pause for N seconds |
| `current_time` | Get current time |

### G1 Humanoid Skills (when using G1 blueprints)

| Tool | Description |
|---|---|
| `move` | Velocity-based movement (x, y, yaw, duration) |
| `execute_arm_command` | Arm gestures (Handshake, HighFive, Hug, etc.) |
| `execute_mode_command` | Switch movement mode (Walk, Run) |

## Configuration

```bash
# Change MCP port
export DIMOS_MCP_PORT=9990
dimos --mcp-port 9990 run unitree-go2-agentic-mcp

# Change MCP host
export DIMOS_MCP_HOST=0.0.0.0
dimos --mcp-host 0.0.0.0 run unitree-go2-agentic-mcp
```

## Debugging

### Test MCP independently

```bash
dimos mcp list-tools                           # See all tools
dimos mcp call relative_move --arg forward=0.5 # Test a tool
dimos mcp status                               # Server health
dimos mcp modules                              # Module -> skill map
```

### MCP Inspector

```bash
npx -y @modelcontextprotocol/inspector
# Set transport to "Streamable HTTP"
# URL: http://localhost:9990/mcp
# Connection mode: "Direct"
```

### Direct JSON-RPC

```bash
# Initialize
curl -X POST http://localhost:9990/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"initialize","id":1,"params":{}}'

# List tools
curl -X POST http://localhost:9990/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"tools/list","id":2,"params":{}}'

# Call a tool
curl -X POST http://localhost:9990/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"tools/call","id":3,"params":{"name":"relative_move","arguments":{"forward":0.5}}}'
```

## Adding MCP to Other Blueprints

Only `unitree-go2-agentic-mcp` ships with MCP enabled. To add MCP to other blueprints:

```python
from dimos.core.blueprints import autoconnect
from dimos.agents.mcp.mcp_server import McpServer
from dimos.agents.mcp.mcp_client import mcp_client

my_blueprint_with_mcp = autoconnect(
    my_existing_blueprint,
    McpServer.blueprint(),
    mcp_client(),
)
```

**Important:** Do not mix `McpServer` with the in-process `agent()` module in the same blueprint. Use `McpServer` + `mcp_client()` together as the agent layer.

## Example Session

```
$ dimos --replay run unitree-go2-agentic-mcp --daemon
Started dimos (PID 12345)

$ claude mcp add --transport http --scope project dimos http://localhost:9990/mcp

$ claude
> Move the robot forward 1 meter, then do a dance

Claude calls: relative_move(forward=1.0)
Claude calls: execute_sport_command(command_name="Dance1")

> What can you see?

Claude calls: observe()
Response: "I can see a desk with a monitor, a chair, and a door to the left..."

> Navigate to the door

Claude calls: navigate_with_text(query="the door to the left")

> Tag this location as "entrance"

Claude calls: tag_location(location_name="entrance")
```

## Limitations

- MCP support is **experimental** (pre-release beta)
- Protocol version: `2025-11-25`
- Transport: HTTP only (no stdio or SSE)
- One MCP server per dimos instance
- Custom skills must follow the `@skill` decorator rules (docstring required, typed params, return `str`)
