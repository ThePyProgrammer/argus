# Robots & Hardware

DimOS supports quadrupeds, humanoids, manipulators, drones, and various sensors -- all without requiring ROS.

## Unitree Quadrupeds

### Go2

The most fully-supported platform with 12 blueprints covering every capability level.

| Blueprint | Description |
|---|---|
| `unitree-go2` | Full stack (perception, navigation, SLAM, spatial memory) |
| `unitree-go2-basic` | Minimal connection + video |
| `unitree-go2-detection` | + Object detection |
| `unitree-go2-spatial` | + Spatial memory (ChromaDB + CLIP) |
| `unitree-go2-ros` | ROS 2 bridge |
| `unitree-go2-vlm-stream-test` | Vision-language model testing |
| `unitree-go2-fleet` | Multi-robot fleet control |
| `unitree-go2-agentic` | + LLM agent (GPT-4o) + all skills |
| `unitree-go2-agentic-mcp` | + MCP server for Claude Code |
| `unitree-go2-agentic-ollama` | + Local LLM via Ollama |
| `unitree-go2-agentic-huggingface` | + HuggingFace models |
| `unitree-go2-temporal-memory` | + Temporal memory system |

**Go2 Skills (40+ sport commands):**
- Posture: BalanceStand, StandUp, StandDown, RecoveryStand, Sit, RiseSit
- Movement: ContinuousGait, EconomicGait, TrajectoryFollow, MoonWalk, CrossStep
- Dynamic: FrontFlip, BackFlip, LeftFlip, RightFlip, FrontJump, FrontPounce
- Expression: Hello, Stretch, Dance1, Dance2, FingerHeart, WiggleHips
- Parameters: BodyHeight, FootRaiseHeight, SpeedLevel

### B1

Larger quadruped platform. Located at `dimos/robot/unitree/b1/`.

## Unitree Humanoids

### G1

Full humanoid with arm gestures and MuJoCo simulation support. 11 blueprints.

| Blueprint | Description |
|---|---|
| `unitree-g1` | Full stack |
| `unitree-g1-basic` | Minimal connection |
| `unitree-g1-basic-sim` | Basic + MuJoCo simulation |
| `unitree-g1-joystick` | Joystick control |
| `unitree-g1-detection` | + Object detection |
| `unitree-g1-shm` | Shared memory transport |
| `unitree-g1-sim` | Simulation only |
| `unitree-g1-agentic` | + LLM agent |
| `unitree-g1-agentic-sim` | Agent + simulation |
| `unitree-g1-full` | Everything enabled |
| `unitree-g1-primitive-no-nav` | Basic motion without navigation |

**G1 Arm Gestures:** Handshake, HighFive, Hug, HighWave, Clap, FaceWave, LeftKiss, ArmHeart, RightHeart, HandsUp, XRay, RightHandUp, Reject, CancelAction

**G1 Movement Modes:** WalkMode, WalkControlWaist, RunMode

## Manipulators

### xArm (xArm6 / xArm7)

| Blueprint | Description |
|---|---|
| `xarm-perception` | Perception pipeline |
| `xarm-perception-agent` | + LLM agent |
| `xarm6-planner-only` | Motion planning (Drake) |
| `xarm7-planner-coordinator` | Coordinated motion planning |
| `xarm7-planner-coordinator-agent` | + Agent |
| `dual-xarm6-planner` | Dual-arm planning |
| `xarm7-trajectory-sim` | Trajectory simulation |

Supports: trajectory planning, keyboard teleop, VR teleop (Quest), velocity control, cartesian IK.

### AgileX Piper

Supports: keyboard teleop, cartesian IK, VR teleop.

## Drones

| Blueprint | Description |
|---|---|
| `drone-basic` | MAVLink connection + video |
| `drone-agentic` | + LLM agent control |

Supports MAVLink drones (via RosettaDrone bridge) and DJI Mavic video streaming. Includes visual servoing and autonomous tracking.

## Sensors

| Sensor | Blueprints |
|---|---|
| Livox Mid-360 LiDAR | `mid360`, `mid360-fastlio`, `mid360-fastlio-voxels`, `mid360-fastlio-voxels-native` |
| Intel RealSense | Integrated as camera module |
| ZED Stereo Camera | Integrated as camera module |
| Force/Torque Sensors | Hardware module |
| USB Cameras | Generic camera module |

## Teleop

| Blueprint | Description |
|---|---|
| `arm-teleop` | Quest VR arm teleop |
| `arm-teleop-dual` | Dual arm VR teleop |
| `arm-teleop-piper` | Piper arm teleop |
| `arm-teleop-xarm7` | xArm7 teleop |
| `phone-go2-teleop` | Phone-based Go2 control |
| `phone-go2-fleet-teleop` | Phone fleet control |
| `simple-phone-teleop` | Simplified phone interface |
| `keyboard-teleop-*` | Keyboard control (piper, xarm6, xarm7) |
