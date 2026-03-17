# Examples

## Running Modes

DimOS has three operating modes that don't require physical hardware:

### Replay Mode (no hardware, no API keys)

Replays recorded sensor data through the full pipeline. Best for testing and development.

```bash
# Basic perception + mapping
dimos --replay run unitree-go2

# With object detection
dimos --replay run unitree-go2-detection

# Full spatial memory pipeline
dimos --replay run unitree-go2-spatial

# With LLM agent (needs OPENAI_API_KEY)
dimos --replay run unitree-go2-agentic

# With MCP server for Claude Code
dimos --replay run unitree-go2-agentic-mcp
```

### Simulation Mode (MuJoCo)

Full physics simulation. No hardware needed but more compute-intensive than replay.

```bash
# G1 humanoid in MuJoCo
dimos --simulation run unitree-g1-agentic-sim

# G1 basic simulation
dimos --simulation run unitree-g1-basic-sim

# G1 sim with visualization
dimos --simulation run unitree-g1-sim

# xArm7 trajectory planning
dimos run xarm7-trajectory-sim
```

### Real Robot

Connects to physical hardware over the network.

```bash
# Go2 quadruped
dimos run unitree-go2-agentic --robot-ip 192.168.123.161

# G1 humanoid
dimos run unitree-g1-agentic --robot-ip 192.168.123.161

# Drone
dimos run drone-agentic --robot-ip 192.168.1.100
```

## Common Workflows

### Agentic Control (LLM-driven)

```bash
# Start agent in daemon mode
export OPENAI_API_KEY=sk-...
dimos --replay run unitree-go2-agentic --daemon

# Send commands
dimos agent-send "walk forward 2 meters"
dimos agent-send "do a backflip"
dimos agent-send "explore the room and tag interesting locations"

# Interactive mode
dimos humancli

# Monitor agent reasoning
dimos agentspy
```

### Claude Code Integration

```bash
# Start MCP-enabled blueprint
dimos --replay run unitree-go2-agentic-mcp --daemon

# Register with Claude Code
claude mcp add --transport http --scope project dimos http://localhost:9990/mcp

# Now use Claude Code normally -- it can call robot skills
```

### Fleet Control

```bash
# Multiple robots
dimos run unitree-go2-fleet --robot-ips "192.168.123.161,192.168.123.162"

# Phone-based fleet teleop
dimos run phone-go2-fleet-teleop --robot-ips "192.168.123.161,192.168.123.162"
```

### Teleop

```bash
# VR teleop (Quest)
dimos run arm-teleop

# Dual arm VR
dimos run arm-teleop-dual

# Phone teleop
dimos run phone-go2-teleop --robot-ip 192.168.123.161

# Keyboard teleop
dimos run keyboard-teleop-xarm6 --robot-ip 192.168.1.100
```

### Manipulation

```bash
# xArm with perception + agent
dimos run xarm-perception-agent --robot-ip 192.168.1.100

# Dual arm planning
dimos run dual-xarm6-planner --robot-ip 192.168.1.100

# xArm7 coordinated planning with agent
dimos run xarm7-planner-coordinator-agent --robot-ip 192.168.1.100
```

### LiDAR Mapping

```bash
# Basic Mid-360 connection
dimos run mid360

# With FastLIO2 SLAM
dimos run mid360-fastlio

# With voxel mapping
dimos run mid360-fastlio-voxels
```

## Python API

### Minimal Blueprint

```python
from dimos.core.blueprints import autoconnect

blueprint = autoconnect(
    camera(),
    Grayscale.blueprint(),
    rerun_bridge(),
)
blueprint.build().loop()
```

### Go2 with Agent

```python
from dimos.core.blueprints import autoconnect
from dimos.robot.unitree.go2.connection import go2_connection
from dimos.agents.agent import agent

blueprint = autoconnect(
    go2_connection(),
    agent(),
)
blueprint.build().loop()
```

### Custom Skill Module

```python
from dimos.core import Module
from dimos.agents.annotation import skill

class MySkills(Module):
    @skill
    def greet(self, name: str) -> str:
        """Greet a person by name."""
        return f"Hello, {name}!"

    @skill
    def count_objects(self) -> str:
        """Count the number of detected objects in the scene."""
        # Access spatial memory or detection results
        count = len(self._detections)
        return f"I can see {count} objects."
```

### Language Interop

DimOS supports control from C++, Lua, and TypeScript via LCM transport for non-Python integrations.

## Visualization

DimOS supports multiple visualization backends:

```bash
# Rerun (default)
dimos --viewer rerun run unitree-go2

# Rerun web (browser-based)
dimos --viewer rerun-web run unitree-go2

# Foxglove
dimos --viewer foxglove run unitree-go2

# No visualization
dimos --viewer none run unitree-go2
```

## Monitoring

```bash
# Resource monitor TUI
dimos top

# LCM message spy
dimos lcmspy

# Agent activity spy
dimos agentspy

# Run status
dimos status

# Follow logs
dimos log -f
```
