# Phase 12: OpenVINS + SVO Pro Backends - Research

**Researched:** 2026-03-23
**Domain:** C++ SLAM backend subprocess integration, IMU sensor extraction, crash recovery
**Confidence:** MEDIUM-HIGH

## Summary

Phase 12 adds two C++ SLAM backends (OpenVINS visual-inertial, SVO Pro / DSO semi-direct) via subprocess isolation using ZMQ IPC. The critical technical challenges are: (1) adding IMU sensors to the Go2 MuJoCo XML and extracting 200Hz readings via physics sub-stepping, (2) building OpenVINS ROS-free and wrapping it as a ZMQ-speaking subprocess, (3) evaluating whether SVO Pro can be de-catkinized or whether DSO is the practical fallback, and (4) implementing a generic SubprocessSLAMBridge that handles spawn/IPC/crash detection/ICP fallback.

Key findings: The Go2 XML has an IMU `site` defined but NO sensor elements -- the `go2_mjx.xml` variant shows exactly what XML to add. OpenVINS has a well-documented ROS-free build producing `libov_msckf_lib.so` and headers. SVO Pro's de-catkinization is poorly documented and high-risk; DSO has clean standalone CMake and is the recommended fallback. ZMQ PAIR sockets over IPC transport are optimal for the 1:1 subprocess pattern. OpenVINS outputs poses in FLU (x-forward, y-left, z-up) convention which needs a simple rotation to MuJoCo's frame.

**Primary recommendation:** Build the generic SubprocessSLAMBridge first with OpenVINS as the reference backend, then attempt SVO Pro with a hard 1-day timebox before pivoting to DSO.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- ZMQ + msgpack for transport: ZeroMQ IPC sockets with msgpack serialization. ~0.5ms per frame transfer.
- Raw numpy bytes + msgpack header: Send shape/dtype as msgpack header, then raw `.tobytes()` for frame data.
- Generic SubprocessSLAMBridge: One shared bridge class reusable for any C++ SLAM backend. Handles spawn, IPC, crash detection, restart. Each backend just provides binary path + config.
- Sub-step MuJoCo for IMU: Run MuJoCo physics sub-steps between camera frames to collect IMU at ~200Hz. Camera captures at normal rate (~30Hz). Batch IMU readings between frames.
- Add to SensorFrame: Add optional `imu_readings: list[IMUReading]` field to SensorFrame. Each IMUReading has `accel` (3,), `gyro` (3,), `timestamp`. Backends that don't need IMU ignore it.
- Attempt SVO Pro with DSO as fallback: Try de-catkinizing SVO Pro build. If it takes more than ~1 day of build issues, pivot to DSO.
- Fall back to ICP immediately on subprocess crash (no retry). Switch to ICP and notify user.
- Toast notification + status change in frontend.
- 5-second hang timeout: If subprocess doesn't respond within 5 seconds, treat as crash.

### Claude's Discretion
- ZMQ socket type (PAIR vs REQ/REP vs PUSH/PULL) for the subprocess bridge
- Exact IMU noise model parameters for MuJoCo sensors (or no noise for simulation)
- DSO vs SVO Pro build investigation strategy and time-boxing
- Toast notification styling and auto-dismiss behavior
- Exact SubprocessSLAMBridge process management (signal handling, cleanup)

### Deferred Ideas (OUT OF SCOPE)
None
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| BACK-03 | OpenVINS backend integrates via subprocess bridge, accepting RGB + IMU data | OpenVINS ROS-free build, ZMQ IPC protocol, IMU extraction from MuJoCo, coordinate frame transform |
| BACK-04 | System extracts accelerometer and gyroscope data from MuJoCo simulation to feed VIO backends | Go2 XML sensor additions, MuJoCo sub-stepping for 200Hz IMU, IMUReading dataclass design |
| BACK-05 | SVO Pro backend integrates via subprocess bridge with de-catkinized build | SVO Pro build assessment, DSO fallback research, shared SubprocessSLAMBridge pattern |
| BACK-06 | Each C++ backend runs in subprocess isolation so crashes do not take down the main process | SubprocessSLAMBridge design, ZMQ PAIR sockets, crash detection, ICP fallback, toast notification |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| pyzmq | 26.x (latest) | ZeroMQ Python bindings for IPC | Pip-installable, Python 3.14 wheels available, ~15us per message latency on IPC |
| msgpack | 1.1+ | Binary serialization for IPC headers | Faster than JSON, compact, cross-language (Python + C++) |
| open_vins | v2.7.1+ (source) | Visual-Inertial SLAM | ROS-free build officially supported, well-documented C++ API |
| DSO | master (source) | Direct Sparse Odometry (SVO Pro fallback) | Clean standalone CMake, no ROS dependency, monocular direct method |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| cppzmq | 4.10+ | ZeroMQ C++ header-only bindings | In the C++ subprocess harness that wraps OpenVINS/DSO |
| msgpack-c | 6.x | msgpack C++ implementation | In the C++ subprocess for serializing poses back |
| Eigen3 | 3.4+ | Linear algebra (OpenVINS dep) | Required build dependency |
| Ceres Solver | 2.2+ | Nonlinear optimization (OpenVINS dep) | Required build dependency |
| Boost | 1.71+ | C++ utilities (OpenVINS dep) | Required build dependency |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| ZMQ PAIR | ZMQ REQ/REP | REQ/REP enforces strict request-response alternation (blocks on double-send); PAIR is more flexible for 1:1 subprocess |
| msgpack | protobuf | Protobuf needs schema compilation; msgpack is schemaless and sufficient for simple header + raw bytes |
| DSO (fallback) | Basalt VIO | Basalt is VIO (needs IMU like OpenVINS) and has heavier deps; DSO is visual-only, simpler, validates a different SLAM paradigm |
| SVO Pro | SVO v1 (older) | SVO v1 has documented no-ROS build but lacks loop closure and VIO; Pro has them but catkin-entangled |

**Installation:**
```bash
# Python dependencies
pip install pyzmq msgpack

# C++ build dependencies (Ubuntu/Debian)
sudo apt install libeigen3-dev libboost-all-dev libceres-dev libzmq3-dev

# OpenVINS (build from source, ROS-free)
git clone https://github.com/rpng/open_vins.git
cd open_vins/ov_msckf && mkdir build && cd build
cmake -DENABLE_ROS=OFF -DCMAKE_BUILD_TYPE=Release ..
make -j$(nproc)
sudo make install
# Produces: /usr/local/lib/libov_msckf_lib.so
# Headers: /usr/local/include/open_vins/

# DSO (fallback for SVO Pro)
git clone --recursive https://github.com/JakobEngel/dso.git
cd dso && mkdir build && cd build
cmake .. -DCMAKE_BUILD_TYPE=Release
make -j$(nproc)
```

## Architecture Patterns

### Recommended Project Structure
```
src/slam/backends/
    subprocess_bridge.py      # Generic SubprocessSLAMBridge base class
    openvins_backend.py       # OpenVINS backend (uses SubprocessSLAMBridge)
    svopro_backend.py         # SVO Pro or DSO backend (uses SubprocessSLAMBridge)

src/bridge/
    sensor_types.py           # Add IMUReading dataclass, update SensorFrame
    sim_bridge.py             # Add IMU sub-stepping in step()

models/unitree_go2/
    go2.xml                   # Add <sensor> block with accelerometer + gyroscope

extern/
    openvins_harness/         # C++ subprocess: reads ZMQ, feeds OpenVINS, returns poses
        CMakeLists.txt
        main.cpp
    dso_harness/              # C++ subprocess for DSO (fallback)
        CMakeLists.txt
        main.cpp

frontend/src/components/
    Toast.tsx                 # New: dismissible toast notification component
```

### Pattern 1: SubprocessSLAMBridge (Generic)
**What:** A reusable Python class that spawns a C++ backend process, communicates via ZMQ IPC, handles crash detection/timeout, and falls back to ICP.
**When to use:** Any C++ SLAM backend that cannot or should not run in-process.
**Example:**
```python
# Source: Project-specific design based on ZMQ patterns
import subprocess
import signal
import time
import zmq
import msgpack
import numpy as np
from src.slam.protocol import SLAMResult, TrackingStatus

class SubprocessSLAMBridge:
    """Generic subprocess wrapper for C++ SLAM backends.

    Implements SLAMProtocol by delegating to a C++ process over ZMQ IPC.
    Handles spawn, communication, crash detection, and ICP fallback.
    """

    HANG_TIMEOUT_MS = 5000  # 5 seconds default

    def __init__(self, binary_path: str, config_path: str,
                 ipc_endpoint: str = "ipc:///tmp/slam_backend"):
        self._binary = binary_path
        self._config = config_path
        self._endpoint = ipc_endpoint
        self._process: subprocess.Popen | None = None
        self._ctx: zmq.Context | None = None
        self._socket: zmq.Socket | None = None
        self._alive = False

    def _start_process(self) -> None:
        self._ctx = zmq.Context()
        self._socket = self._ctx.socket(zmq.PAIR)
        self._socket.bind(self._endpoint)
        self._socket.setsockopt(zmq.RCVTIMEO, self.HANG_TIMEOUT_MS)
        self._socket.setsockopt(zmq.LINGER, 0)

        self._process = subprocess.Popen(
            [self._binary, "--config", self._config,
             "--zmq", self._endpoint],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        self._alive = True

    def send_frame(self, rgb: np.ndarray, depth: np.ndarray,
                   timestamp: float,
                   imu_readings: list | None = None) -> SLAMResult | None:
        """Send frame to subprocess, receive pose back.

        Returns None on crash/timeout (caller should fall back to ICP).
        """
        if not self._alive:
            return None
        try:
            # Header: metadata as msgpack
            header = msgpack.packb({
                "ts": timestamp,
                "rgb_shape": list(rgb.shape),
                "rgb_dtype": str(rgb.dtype),
                "depth_shape": list(depth.shape),
                "depth_dtype": str(depth.dtype),
                "n_imu": len(imu_readings) if imu_readings else 0,
            })
            # Multi-part message: header, rgb bytes, depth bytes, [imu bytes]
            parts = [header, rgb.tobytes(), depth.tobytes()]
            if imu_readings:
                imu_array = np.array(
                    [(r.timestamp, *r.accel, *r.gyro) for r in imu_readings],
                    dtype=np.float64
                )
                parts.append(imu_array.tobytes())
            self._socket.send_multipart(parts)

            # Receive response
            reply = self._socket.recv()
            result_data = msgpack.unpackb(reply)
            pose = np.frombuffer(result_data[b"pose"], dtype=np.float64).reshape(4, 4)
            status = TrackingStatus(result_data[b"status"].decode())
            return SLAMResult(
                pose=pose,
                points=np.empty((0, 3)),  # dense cloud from depth, not subprocess
                colors=np.empty((0, 3)),
                metrics={"processing_time_ms": result_data.get(b"time_ms", 0)},
                tracking_status=status,
            )
        except zmq.Again:
            # Timeout -- subprocess hung
            self._kill_process()
            return None
        except zmq.ZMQError:
            self._kill_process()
            return None

    def _kill_process(self) -> None:
        self._alive = False
        if self._process:
            self._process.kill()
            self._process.wait(timeout=2)
            self._process = None
```

### Pattern 2: C++ ZMQ Harness (subprocess side)
**What:** A minimal C++ main() that connects to ZMQ, receives frames, feeds them to the SLAM library, and returns poses.
**When to use:** For each C++ SLAM backend subprocess.
**Example:**
```cpp
// Source: Project-specific design
#include <zmq.hpp>
#include <msgpack.hpp>
#include "ov_msckf/VioManager.h"
#include "ov_msckf/VioManagerOptions.h"

int main(int argc, char** argv) {
    // Parse args: --config path --zmq ipc://endpoint
    std::string config_path = argv[2];
    std::string zmq_endpoint = argv[4];

    // Setup ZMQ PAIR socket
    zmq::context_t ctx(1);
    zmq::socket_t sock(ctx, zmq::socket_type::pair);
    sock.connect(zmq_endpoint);

    // Initialize OpenVINS
    auto params = ov_msckf::VioManagerOptions();
    // ... load params from config_path ...
    auto vio = std::make_shared<ov_msckf::VioManager>(params);

    while (true) {
        // Receive multipart: [header, rgb, depth, imu?]
        std::vector<zmq::message_t> parts;
        zmq::recv_multipart(sock, std::back_inserter(parts));

        // Unpack header, extract frame data
        // Feed IMU readings to vio->feed_measurement_imu(...)
        // Feed image to vio->feed_measurement_monocular(...)

        // Get pose: vio->get_state()->_imu->pos(), quat()
        // Pack as msgpack, send back
        zmq::message_t reply(packed_result.data(), packed_result.size());
        sock.send(reply, zmq::send_flags::none);
    }
}
```

### Pattern 3: IMU Sub-stepping in MuJoCo Bridge
**What:** Run multiple physics sub-steps between camera frames to collect high-frequency IMU data.
**When to use:** When the bridge needs to provide 200Hz IMU data alongside 30Hz camera frames.
**Example:**
```python
# Source: Based on existing sim_bridge.py step() method and MuJoCo sensor API
def step(self, action=None) -> SensorFrame:
    import mujoco

    imu_readings = []
    sim_time_base = self._step_count * self._dt

    # Run sub-steps, collecting IMU at each physics step
    for i in range(self._config.sim_steps_per_frame):
        if action is not None:
            self._data.ctrl[:] = action
        else:
            self._data.ctrl[:] = self._velocity_to_ctrl()
        mujoco.mj_step(self._model, self._data)

        # Read IMU sensors from sensordata
        accel = self._data.sensordata[self._accel_adr:self._accel_adr + 3].copy()
        gyro = self._data.sensordata[self._gyro_adr:self._gyro_adr + 3].copy()
        t = sim_time_base + (i + 1) * self._model.opt.timestep
        imu_readings.append(IMUReading(accel=accel, gyro=gyro, timestamp=t))

    self._step_count += 1
    frame = self._capture_frame()
    frame.imu_readings = imu_readings
    return frame
```

### Anti-Patterns to Avoid
- **REQ/REP for subprocess IPC:** REQ/REP enforces strict alternation and will deadlock if either side sends twice. Use PAIR for 1:1 subprocess communication.
- **Adding IMU noise via MuJoCo's noise attribute:** As of MuJoCo 3.1.4, the `noise` attribute on sensors is metadata-only and does NOT automatically add noise. Must add noise manually in Python if desired.
- **Blocking the main loop waiting for subprocess:** Use RCVTIMEO on the ZMQ socket, not Python-level timeouts.
- **Trying to share memory across Python/C++ for frames:** ZMQ IPC with raw bytes is fast enough (~0.5ms for 1.5MB frame) and much simpler than shared memory. Only optimize to shm if profiling shows IPC is the bottleneck.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| IPC transport | Custom socket/pipe protocol | ZMQ PAIR + msgpack | Handles buffering, reconnection, multipart messages. Battle-tested across languages. |
| Process crash detection | Polling process.poll() in a thread | ZMQ RCVTIMEO + process.returncode | ZMQ timeout is the authoritative signal; process.poll() is supplementary |
| IMU sensor simulation | Manual acceleration computation from poses | MuJoCo accelerometer/gyroscope sensors | MuJoCo sensors include proper rigid body dynamics effects (centripetal, Coriolis) |
| Coordinate transforms | Ad-hoc rotation matrices | Static 4x4 transform constant per backend | Established pattern from ORB-SLAM3 backend (T_MUJOCO_FROM_OPTICAL) |
| Toast notifications | Custom notification system | Simple React component with setTimeout auto-dismiss | No npm dependency needed; portal pattern already used by ConfirmModal |

**Key insight:** The SubprocessSLAMBridge is the central abstraction. Once it works for OpenVINS, adding DSO/SVO Pro is just swapping the binary path and config. Do NOT create separate subprocess management per backend.

## Common Pitfalls

### Pitfall 1: Go2 XML Missing IMU Sensors
**What goes wrong:** The `go2.xml` model has a `<site name="imu">` but NO `<sensor>` block. Calling `mj_sensordata` returns nothing for IMU.
**Why it happens:** The MuJoCo Menagerie Go2 model is a locomotion model, not a VIO model. The `go2_mjx.xml` variant has sensors but is loaded by MJX (JAX backend), not standard MuJoCo.
**How to avoid:** Add a `<sensor>` block to `go2.xml` (or to `scene.xml` which includes it):
```xml
<sensor>
    <accelerometer site="imu" name="accelerometer"/>
    <gyro site="imu" name="gyro"/>
</sensor>
```
**Warning signs:** `mj_name2id(model, mjtObj.mjOBJ_SENSOR, "accelerometer")` returns -1.

### Pitfall 2: MuJoCo Sensor Noise Attribute Does Nothing
**What goes wrong:** Setting `noise="0.003"` on the accelerometer sensor element and expecting automatic noise injection.
**Why it happens:** MuJoCo 3.1.4 removed automatic sensor noise. The `noise` attribute is now metadata-only (stores std dev for user-side processing).
**How to avoid:** Either add noise manually in Python (`accel += np.random.normal(0, 0.003, 3)`) or use zero noise for simulation (OpenVINS will still work with clean data, just won't exercise noise-handling code paths).
**Warning signs:** IMU data is suspiciously clean (exactly matches rigid body dynamics with no stochastic component).

### Pitfall 3: OpenVINS Filter Divergence with Zero-Noise IMU
**What goes wrong:** OpenVINS's EKF assumes IMU noise parameters match reality. With perfect simulation IMU data (zero noise), the filter's uncertainty estimates collapse to zero, causing numerical instability.
**Why it happens:** The Kalman filter's measurement update divides by the predicted measurement covariance. If noise parameters say there should be noise but data has none, the innovation becomes unexpectedly small, collapsing state covariance.
**How to avoid:** Set OpenVINS's IMU noise parameters to very small values matching the actual simulation noise (or zero if no noise added). In the config YAML: `gyroscope_noise_density: 1e-6`, `accelerometer_noise_density: 1e-5`. Alternatively, add small Gaussian noise to IMU readings.
**Warning signs:** Pose jumps to infinity within first 5-10 frames, or NaN in pose output.

### Pitfall 4: ZMQ Socket Not Cleaned Up on Crash
**What goes wrong:** When the subprocess crashes, the ZMQ IPC socket file (`/tmp/slam_backend`) is left behind. Next launch fails with "address already in use."
**Why it happens:** ZMQ IPC transport creates a Unix domain socket file. If the binding process crashes without close(), the file persists.
**How to avoid:** (1) Use unique endpoint per backend instance: `ipc:///tmp/slam_{backend_name}_{pid}`. (2) Delete the socket file in `_kill_process()`. (3) Set `zmq.LINGER=0` so socket cleanup doesn't block.
**Warning signs:** `zmq.error.ZMQError: Address already in use` on second launch.

### Pitfall 5: Coordinate Frame Mismatch Between OpenVINS and MuJoCo
**What goes wrong:** OpenVINS outputs poses in FLU (x-forward, y-left, z-up) global frame. MuJoCo uses a z-up frame too, but the body's forward direction and the global frame alignment depend on initialization. Without proper alignment, the robot appears to drift sideways.
**Why it happens:** OpenVINS initializes its global frame from the first few seconds of IMU data (gravity alignment). The initial orientation of the IMU in MuJoCo determines how OpenVINS's FLU aligns with MuJoCo's world frame.
**How to avoid:** Apply the same GT offset seeding pattern from ORB-SLAM3 backend. OpenVINS's FLU frame should be close to MuJoCo's world frame if the robot starts level (gravity = -z in both). The main adjustment is:
```python
# OpenVINS FLU: x-forward, y-left, z-up
# MuJoCo:      x-forward, y-left, z-up (when robot faces +x)
# These are the SAME convention if robot starts facing +x.
# GT offset handles any starting orientation mismatch.
T_MUJOCO_FROM_FLU = np.eye(4)  # Identity if conventions match
```
**Warning signs:** Robot trajectory rotated 90 or 180 degrees from ground truth.

## Code Examples

### IMUReading Dataclass Addition to sensor_types.py
```python
# Source: Based on CONTEXT.md decision and existing SensorFrame pattern
from dataclasses import dataclass, field

@dataclass
class IMUReading:
    """A single IMU measurement from the simulation.

    Attributes:
        accel: Accelerometer reading (3,) in m/s^2, body frame.
        gyro: Gyroscope reading (3,) in rad/s, body frame.
        timestamp: Simulation timestamp in seconds.
    """
    accel: np.ndarray  # (3,) float64
    gyro: np.ndarray   # (3,) float64
    timestamp: float

# Updated SensorFrame:
@dataclass
class SensorFrame:
    rgb: np.ndarray
    depth: np.ndarray | None
    ground_truth_pose: np.ndarray
    sim_time: float
    imu_readings: list[IMUReading] = field(default_factory=list)
```

### MuJoCo Sensor Address Lookup
```python
# Source: MuJoCo Python API
import mujoco

# After loading model, find sensor addresses:
accel_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_SENSOR, "accelerometer")
gyro_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_SENSOR, "gyro")

# Sensor data addresses (where in sensordata array)
accel_adr = model.sensor_adr[accel_id]  # start index, 3 floats
gyro_adr = model.sensor_adr[gyro_id]    # start index, 3 floats

# After mj_step:
accel = data.sensordata[accel_adr:accel_adr + 3].copy()
gyro = data.sensordata[gyro_adr:gyro_adr + 3].copy()
```

### Go2 XML Sensor Block to Add
```xml
<!-- Add to go2.xml, after </actuator> and before <keyframe> -->
<sensor>
    <accelerometer site="imu" name="accelerometer"/>
    <gyro site="imu" name="gyro"/>
</sensor>
```

### OpenVINS Backend Registration
```python
# Source: Based on existing orbslam3_backend.py pattern
@slam_backend(name="openvins", display="OpenVINS (VIO)")
class OpenVINSBackend:
    CAPABILITIES: dict = {
        "supports_imu": True,
        "outputs_dense": True,  # via depth_to_pointcloud, not native
        "supports_loop_closure": False,
        "supports_stereo": False,
    }
    PARAMETER_SCHEMA: dict = {
        "type": "object",
        "properties": {
            "max_cameras": {
                "type": "integer", "default": 1, "minimum": 1, "maximum": 4,
                "description": "Number of cameras to use",
                "live_tunable": False,
            },
            "num_pts": {
                "type": "integer", "default": 200, "minimum": 50, "maximum": 500,
                "description": "Max number of tracked features",
                "live_tunable": False,
            },
        },
    }
```

### ZMQ Multi-Part Wire Protocol
```
Python (client) -> C++ (server) per frame:
  Part 0: msgpack header {ts, rgb_shape, rgb_dtype, depth_shape, depth_dtype, n_imu}
  Part 1: raw RGB bytes (H*W*3 uint8)
  Part 2: raw depth bytes (H*W float32)
  Part 3: raw IMU bytes (n_imu * 7 float64: [ts, ax, ay, az, gx, gy, gz] per reading)

C++ (server) -> Python (client) per frame:
  Part 0: msgpack {pose: bytes(4x4 float64), status: "ok"|"lost"|"initializing", time_ms: float}
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| MuJoCo sensor noise attribute | Manual noise in user code | MuJoCo 3.1.4 | Must add noise manually if needed |
| SVO Pro requires catkin | Still requires catkin (no change) | N/A (2021 last commit) | DSO is more practical fallback |
| OpenVINS ROS-only | ROS-free build (`-DENABLE_ROS=OFF`) | v2.0 | Can build standalone, produces shared lib |
| DSO unmaintained | Original repo still usable, plus forks (DSOPP, dso-python) | 2024+ | Clean CMake, monocular direct VO |

**Deprecated/outdated:**
- SVO Pro open-source: Last commit 2021, catkin-entangled, no maintained community. Research code only.
- MuJoCo automatic sensor noise: Removed in 3.1.4. The `noise` XML attribute is metadata-only.

## Open Questions

1. **OpenVINS initialization time with simulated data**
   - What we know: OpenVINS needs a few seconds of IMU data to estimate gravity direction and initial biases.
   - What's unclear: How long initialization takes with zero-noise MuJoCo IMU data. May be instant or may fail.
   - Recommendation: Feed 2 seconds of IMU data during bridge.start() settling phase before first frame. Return INITIALIZING status until OpenVINS reports tracking.

2. **DSO depth image support**
   - What we know: DSO is monocular (designed for mono cameras). Our setup provides RGB-D.
   - What's unclear: Whether DSO can use depth images for initialization or if it only works with monocular.
   - Recommendation: DSO ignores depth by design (it estimates its own depth). Use it as pure monocular VO. The dense cloud still comes from depth_to_pointcloud with DSO's estimated pose.

3. **Python 3.14 compatibility for pyzmq**
   - What we know: pyzmq 26.x has widespread wheel support. Python 3.14 is very new.
   - What's unclear: Whether pre-built wheels exist for Python 3.14 specifically.
   - Recommendation: Test `pip install pyzmq` early. If wheels unavailable, pyzmq builds from source with libzmq (requires `libzmq3-dev`).

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.x |
| Config file | pyproject.toml `[tool.pytest]` |
| Quick run command | `pytest tests/slam/ -x -q` |
| Full suite command | `pytest tests/ -x --timeout=60` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| BACK-03 | OpenVINS backend receives frames via ZMQ, returns poses | unit (mocked subprocess) | `pytest tests/slam/test_openvins_backend.py -x` | No -- Wave 0 |
| BACK-04 | MuJoCo bridge extracts IMU readings at sub-step rate | unit | `pytest tests/bridge/test_imu_extraction.py -x` | No -- Wave 0 |
| BACK-04 | IMUReading dataclass and SensorFrame.imu_readings field | unit | `pytest tests/bridge/test_sensor_types_imu.py -x` | No -- Wave 0 |
| BACK-05 | SVO Pro / DSO backend receives frames via ZMQ, returns poses | unit (mocked subprocess) | `pytest tests/slam/test_svopro_backend.py -x` | No -- Wave 0 |
| BACK-06 | SubprocessSLAMBridge handles crash with ICP fallback | unit | `pytest tests/slam/test_subprocess_bridge.py -x` | No -- Wave 0 |
| BACK-06 | SubprocessSLAMBridge handles 5s timeout as crash | unit | `pytest tests/slam/test_subprocess_bridge.py::test_timeout_fallback -x` | No -- Wave 0 |
| BACK-06 | Toast notification on crash (frontend) | manual-only | Visual inspection: crash backend, verify toast appears | N/A |

### Sampling Rate
- **Per task commit:** `pytest tests/slam/ tests/bridge/ -x -q`
- **Per wave merge:** `pytest tests/ -x --timeout=60`
- **Phase gate:** Full suite green before verify

### Wave 0 Gaps
- [ ] `tests/slam/test_subprocess_bridge.py` -- covers BACK-06 (SubprocessSLAMBridge crash detection, timeout, IPC protocol)
- [ ] `tests/slam/test_openvins_backend.py` -- covers BACK-03 (OpenVINS backend with mocked subprocess, same pattern as test_orbslam3_backend.py)
- [ ] `tests/slam/test_svopro_backend.py` -- covers BACK-05 (SVO Pro / DSO backend with mocked subprocess)
- [ ] `tests/bridge/test_imu_extraction.py` -- covers BACK-04 (IMU readings from MuJoCo sub-stepping)
- [ ] `tests/bridge/test_sensor_types_imu.py` -- covers BACK-04 (IMUReading dataclass, SensorFrame with imu_readings)

## Sources

### Primary (HIGH confidence)
- [OpenVINS ROS-Free Installation](https://docs.openvins.com/gs-installing-free.html) -- build instructions, dependencies, library output
- [OpenVINS Coordinate System](https://github.com/rpng/open_vins/issues/277) -- FLU convention, T_ItoG output
- [OpenVINS Coordinate Axes](https://github.com/rpng/open_vins/issues/61) -- x-forward, y-left, z-up confirmation
- [MuJoCo XML Reference](https://mujoco.readthedocs.io/en/stable/XMLreference.html) -- sensor element definitions, accelerometer/gyro
- [MuJoCo sensor noise deprecation](https://github.com/google-deepmind/mujoco/discussions/1602) -- noise attribute is metadata-only since 3.1.4
- Go2 model files: `go2.xml` has `<site name="imu">` at line 76; `go2_mjx.xml` has `<accelerometer>` and `<gyro>` sensors at lines 238-239 -- HIGH confidence (direct file inspection)
- Existing `orbslam3_backend.py` -- GT offset seeding, coordinate transform pattern, SLAMProtocol compliance

### Secondary (MEDIUM confidence)
- [ZMQ Guide Chapter 2: Sockets and Patterns](https://zguide.zeromq.org/docs/chapter2/) -- PAIR socket for 1:1 peer communication
- [DSO GitHub (JakobEngel/dso)](https://github.com/JakobEngel/dso) -- standalone CMake build, monocular direct VO
- [SVO Pro GitHub Issues #6, #21](https://github.com/uzh-rpg/rpg_svo_pro_open/issues/6) -- no official non-ROS build docs, one user claimed success without details
- [DSOPP reimplementation](https://github.com/RoadlyInc/DSOPP) -- modern CMake DSO variant

### Tertiary (LOW confidence)
- SVO Pro de-catkinization feasibility -- no documented success path, only anecdotal "I figured it out" claims
- DSO tracking quality vs SVO Pro -- no direct comparison in simulation environments
- pyzmq Python 3.14 wheel availability -- not verified against PyPI

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- pyzmq, msgpack well-established; OpenVINS ROS-free build officially documented
- Architecture: HIGH -- SubprocessSLAMBridge pattern follows established orbslam3_backend.py conventions; ZMQ IPC is battle-tested
- IMU extraction: HIGH -- MuJoCo sensor API straightforward; Go2 XML site already exists, just needs sensor elements
- SVO Pro viability: LOW -- no documented non-ROS build path; DSO fallback is more certain
- Pitfalls: MEDIUM-HIGH -- coordinate frames verified from official sources; sensor noise deprecation verified

**Research date:** 2026-03-23
**Valid until:** 2026-04-23 (30 days -- stable domain, libraries not fast-moving)
