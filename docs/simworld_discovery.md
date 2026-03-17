# SimWorld Gym API Discovery

**Date:** 2026-03-17
**Source:** SimWorld-Robotics GitHub (SCAI-JHU/SimWorld-Robotics)
**Method:** Source code reading + runtime discovery (if available)

## Environment IDs

Registered in `simworld_gym/__init__.py`:

| ID | Entry Point | Notes |
|---|---|---|
| `simworld_gym/SimpleWorld` | `SimpleEnv` | Single-agent, synchronous stepping |
| `simworld_gym/BufferWorld` | `BufferEnv` | Multi-agent, async action buffer |
| `simworld_gym/TrafficWorld` | `TrafficEnv` | Traffic simulation variant |

**Important:** Uses legacy `gym` package, NOT `gymnasium`. Import as `import gym`.

## Observation Space

Controlled by `observation_type` constructor parameter:

| Type | Keys | Shapes | Dtypes |
|---|---|---|---|
| `ground_truth` | `relative_target_location`, `relative_target_orientation` | (3,), (1,) | float64 |
| `rgb` | `rgb` | (H, W, 3) | uint8 |
| `depth` | `depth` | (H, W, 1) | uint8 |
| `rgbd` | `rgb`, `depth` | (H, W, 3), (H, W, 1) | uint8 |
| `all` | `rgb`, `depth`, `object_mask` | (H, W, 3), (H, W, 1), (H, W, 3) | uint8 |

Default resolution: W=320, H=240.

### Depth Format Warning

The depth image is **NOT raw metric depth**. The `_decode_npy()` method in
`unrealcv_basic.py` applies:
1. Log normalization: `depth_log = np.log(raw_depth + eps)`
2. Min-max scaling to [0, 1]
3. Gamma correction (gamma=0.5)
4. Scale to uint8 [0, 255]
5. OpenCV JET colormap -> (H, W, 3) uint8

**For SLAM, we need raw metric depth.** The bridge must intercept the npy
response BEFORE `_decode_npy()` is called, or patch the method to return
raw float32 values. The raw npy from UnrealCV contains float32 depth in
Unreal units (likely centimeters, needs verification at runtime).

## Action Space

Type: `Discrete(6)` (from `action_config.json`)

| Index | Meaning | Type | Parameters |
|---|---|---|---|
| 0 | MOVE_FORWARD | Move_Speed | speed=5000, duration=0.1s, dir=0 |
| 1 | MOVE_BACKWARD | Move_Speed | speed=5000, duration=0.1s, dir=1 |
| 2 | MOVE_LEFT | Move_Speed | speed=5000, duration=0.1s, dir=2 |
| 3 | MOVE_RIGHT | Move_Speed | speed=5000, duration=0.1s, dir=3 |
| 4 | TURN_RIGHT | Rotate_Angle | duration=0.1s, angle=90 deg |
| 5 | TURN_LEFT | Rotate_Angle | duration=0.1s, angle=-90 deg |
| 100 | TERMINATE | Special | Ends episode |

**Note:** Action -1 triggers subtask evaluation (internal to SimpleEnv).
For our bridge, use actions 0-5 only.

## Ground-Truth Pose

Available in the `info` dict returned by `step()` and `reset()`:

```python
info["agent"]["agent_location"]  # np.array([x, y, z]) in Unreal units (cm)
info["agent"]["agent_rotation"]  # cardinal direction string: "North", "South", etc.
```

Raw rotation `[roll, pitch, yaw]` in degrees is stored internally on
`agent_controller._agent_rotation` but is NOT directly exposed in info.
The info dict only has the discretized cardinal direction.

**For full 6-DOF ground-truth pose**, the bridge needs to either:
1. Subclass SimpleEnv to expose raw rotation in info, OR
2. Access `env.agent_controller._agent_rotation` directly (fragile).

Position is straightforward: `info['agent']['agent_location']` gives (x, y, z).

## Camera Intrinsics

Not directly exposed in observations or info dict.

From source code (`agent_controller._generate_agent`):
- **FOV:** 120 degrees (hardcoded)
- **Resolution:** 320x240 (default, configurable)

Computed intrinsics (assuming symmetric horizontal FOV):
- **fx = fy:** 92.38 pixels
- **cx:** 160.0, **cy:** 120.0

These must be verified at runtime by checking depth-to-3D reprojection quality.

## Step Rate

**Estimated from source code (no runtime available):**

Each discrete movement action takes:
- `performing_time` = duration from config = 0.1s
- `time.sleep(performing_time + 0.05)` = 0.15s minimum
- Availability polling loop with 0.05s sleep intervals
- Image capture overhead (UnrealCV PNG/npy request)

**Estimated range: 3-6 Hz** depending on UE5 rendering load.
The 0.15s mandatory sleep alone limits to ~6.7 Hz theoretical max.

## Go/No-Go Determination

Criterion: step rate >= 5.0 Hz for real-time SLAM.

**CONDITIONAL GO** -- source code analysis suggests 3-6 Hz is likely.
This is borderline for the 5 Hz threshold. Recommendations:
1. Measure at runtime before committing to real-time SLAM
2. If below 5 Hz, reduce resolution from 320x240 to 160x120
3. If still below 5 Hz, switch to batch/offline processing per CONTEXT.md
4. The mandatory `time.sleep(0.15)` per step is the main bottleneck --
   consider patching SimpleEnv.step() to reduce or remove the sleep

## Surprises and Deviations from Research Assumptions

1. **Legacy gym, not gymnasium:** SimWorld uses `import gym` (OpenAI gym),
   not `import gymnasium`. Our bridge must handle this compatibility.
   The `step()` return signature matches gymnasium (5 values), but
   registration and spaces use old gym API.

2. **Depth is NOT metric:** The default pipeline returns colorized uint8,
   not raw float32 meters. This is a critical blocker for depth-based SLAM.
   Raw npy is available from UnrealCV but the gym wrapper destroys it.

3. **Ground-truth rotation is discretized:** Info dict only has cardinal
   direction strings, not continuous rotation. Raw rotation must be extracted
   from internal state or the env must be subclassed.

4. **Discrete action space only:** Continuous velocity control is not
   implemented (raises NotImplementedError). The robot moves in fixed
   increments with 90-degree turns.

5. **Reset requires task_path and config JSONs:** SimpleEnv.reset()
   expects `options={'task_path': ..., 'world_json': ..., 'agent_json': ...}`.
   Cannot simply call `env.reset()` without configuration files.

6. **Camera FOV is very wide (120 deg):** This causes significant barrel
   distortion in depth-to-3D conversion. Intrinsics computation must account
   for this wide angle.

