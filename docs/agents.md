# Agents & Skills

DimOS provides LLM-powered agents that discover and use robot skills through a unified interface.

## Agent Types

### Agent (LangGraph)

The primary agent, built on LangGraph with tool calling. Discovers all `@skill` methods from system modules and exposes them as LangChain StructuredTools.

- **Default model:** GPT-4o
- **Streams:** `agent` (messages out), `agent_idle` (bool), `human_input` (str in)
- **Config:** `system_prompt`, `model`, `model_fixture` (for testing)
- Maintains conversation history, queues messages, streams outputs

### MCP Client Agent

HTTP-based agent that fetches tools from an McpServer instead of discovering them in-process.

- **Default model:** GPT-4o
- **MCP server URL:** `http://localhost:9990/mcp`
- Discovers tools via JSON-RPC, converts to LangChain StructuredTools

### VLM Agent

Vision Language Model agent for image-based queries.

- Streams: `color_image` (Image in), `query_stream` (in), `answer_stream` (out)
- Supports Ollama models
- RPC methods: `query()`, `query_image()`

### Ollama Agent

Local LLM agent using Ollama for fully offline operation.

### Web Human Input

Browser-based human input on port 5555 with text and voice (Whisper STT) support.

## Skills System

Any method decorated with `@skill` on a Module is automatically exposed to agents and MCP.

### The `@skill` Decorator

```python
from dimos.agents.annotation import skill

class MyModule(Module):
    @skill
    def move_forward(self, distance: float) -> str:
        """Move the robot forward by the given distance in meters."""
        self._driver.move(distance, 0, 0)
        return f"Moved forward {distance}m"
```

**Rules:**
- Docstring is **mandatory** (startup fails without it)
- All parameters must have type annotations
- Must return `str` (None -> "It has started. You will be updated later.")
- Supported param types: `str`, `int`, `float`, `bool`, `list[str]`, `list[float]`
- `@skill` implies `@rpc` -- don't stack both decorators

### Built-in Skills

**Navigation:**
- `relative_move(forward, left, degrees)` -- Move relative to current position
- `navigate_with_text(query)` -- Natural language navigation with 3-tier fallback (tagged locations -> visual detection -> semantic map)
- `tag_location(location_name)` -- Tag current position in spatial memory
- `stop_navigation()` -- Immediately stop moving

**Communication:**
- `speak(text)` -- TTS via OpenAI (Onyx voice, 1.2x speed)

**Person Interaction:**
- `follow_person(query)` -- Follow a described person using VL model + EdgeTAM tracker
- `stop_following()` -- Stop following

**Utility:**
- `wait(seconds)` -- Pause execution
- `current_time()` -- Get current date/time

**Go2-specific:**
- `execute_sport_command(command_name)` -- 40+ motor routines (flips, dances, gaits, etc.)

**G1-specific:**
- `move(x, y, yaw, duration)` -- Velocity-based movement
- `execute_arm_command(command_name)` -- 14 arm gestures
- `execute_mode_command(command_name)` -- Walk/Run modes

**Other:**
- `google_maps_skill` -- Google Maps integration
- `gps_nav_skill` -- GPS-based outdoor navigation
- `osm` -- OpenStreetMap integration

## Default Agent Persona

The default agent is named **"Daneel"** with a system prompt that:
- Prioritizes human safety above all
- Communicates via speakers (1-2 sentences max)
- Uses `navigate_with_text` for indoor, GPS for outdoor navigation
- Supports location tagging and sport commands
- Has a recovery protocol for failed commands

## MCP (Model Context Protocol)

See [Claude Code Integration](claude-code.md) for details on exposing skills via MCP.

## Perception Pipeline

The agent benefits from a full perception stack:

- **Object Detection:** Ultralytics-based detectors, person tracking, 3D detection
- **Spatial Memory:** ChromaDB vector database with CLIP/ResNet embeddings, spatio-temporal RAG
  - `query_by_location(x, y, radius)` -- Find objects near a position
  - `query_by_image(image)` -- Visual similarity search
  - `query_by_text(text)` -- CLIP text-to-image matching
- **Object Tracking:** 2D and 3D trackers with persistence
- **Temporal Memory:** Experimental time-aware memory system

## Memory System

Spatial perception uses ChromaDB for persistent memory:

- Automatic frame processing with distance (0.01m) and time (1.0s) thresholds
- Location tagging: `tag_location()`, `find_robot_location()`, `add_named_location()`
- Vector search over CLIP embeddings for text-to-scene queries
- Controllable via `--new-memory` flag (fresh start vs. resume)
