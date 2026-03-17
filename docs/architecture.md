# Architecture

DimOS is built on three core abstractions: **Modules**, **Streams**, and **Blueprints**.

## Modules

Modules are autonomous subsystems that run in forkserver worker processes. Each module encapsulates a single responsibility (camera driver, detector, planner, agent, etc.) and communicates only through typed streams.

```python
from dimos.core import Module, In, Out
from dimos.types import Image

class Grayscale(Module):
    color_image: In[Image]
    gray_image: Out[Image]

    @rpc
    def start(self) -> None:
        super().start()
        self.color_image.subscribe(self._on_frame)

    def _on_frame(self, img: Image) -> None:
        self.gray_image.publish(to_gray(img))
```

There are 62+ registered modules covering agents, robot connections, perception, navigation, manipulation, mapping, teleop, visualization, and web interfaces.

## Streams

Streams are typed pub/sub channels between modules:

| Type | Direction | Description |
|---|---|---|
| `Out[T]` | Publish | Sends messages to subscribers |
| `In[T]` | Subscribe | Receives from an upstream `Out` |
| `RemoteOut[T]` | Publish (cross-process) | Serialized proxy for `Out` |
| `RemoteIn[T]` | Subscribe (cross-process) | Serialized proxy for `In` |

Streams go through states: UNBOUND -> READY -> CONNECTED.

## Blueprints

Blueprints compose modules into deployable systems. The `autoconnect()` function merges blueprints and wires streams automatically by matching `(name, type)` pairs.

```python
from dimos.core.blueprints import autoconnect

blueprint = autoconnect(
    go2_connection(),        # robot driver
    spatial_perception(),    # SLAM + spatial memory
    agent(),                 # LLM agent with skills
    rerun_bridge(),          # visualization
)

blueprint.build().loop()     # deploy all modules, block until stopped
```

Blueprint fluent API:
- `.disabled_modules()` -- skip specific modules
- `.transports()` -- override default transport for streams
- `.global_config()` -- inject configuration
- `.remappings()` -- remap stream names
- `.requirements()` -- declare Spec dependencies

## Transports

Transports control how stream data moves between processes:

| Transport | Use Case |
|---|---|
| `LCMTransport` | Default. Multicast UDP, typed LCM messages |
| `pLCMTransport` | Pickled LCM -- complex Python objects |
| `JpegLcmTransport` | JPEG-compressed images over LCM |
| `SHMTransport` | Shared memory -- raw bytes, lowest latency |
| `pSHMTransport` | Shared memory with pickle serialization |
| `JpegShmTransport` | JPEG images via shared memory (configurable quality) |
| `ROSTransport` | ROS topic bridge -- interop with ROS 2 nodes |
| `DDSTransport` | DDS pub/sub (requires `--extra dds`) |

LCM is the default. For high-bandwidth streams (video, point clouds), SHM transports avoid network overhead.

**Linux network tuning for LCM:**
```bash
sudo sysctl -w net.core.rmem_max=67108864
```

## Spec Pattern (Dependency Injection)

Modules declare dependencies via Protocol-based Specs:

```python
class NavigatorSpec(Spec, Protocol):
    def set_goal(self, goal: PoseStamped) -> bool: ...

class MySkillContainer(Module):
    _navigator: NavigatorSpec  # injected at build time
```

The blueprint resolves Specs to concrete modules at build time with type checking and ambiguity detection.

## RPC

Methods decorated with `@rpc` are callable across process boundaries. The `@skill` decorator implies `@rpc` and additionally exposes the method to LLM agents and MCP.
