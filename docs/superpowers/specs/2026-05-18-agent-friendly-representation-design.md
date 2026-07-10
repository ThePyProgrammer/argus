# Agent-Friendly Swarm Representation Design

## Purpose

Design a general-purpose indoor/outdoor representation layer that lets agentic AI systems reason over a robot swarm's world state without consuming raw point clouds or Gaussian splats directly.

The representation should support four first-class capabilities:

1. **Explore/search:** find objects, people, hazards, and unexplored areas.
2. **Navigate/coordinate:** route robots, assign frontiers, avoid conflicts, and respect robot-specific traversability.
3. **Inspect/understand:** summarize what the swarm sees and answer grounded questions about the environment.
4. **Manipulate/interact:** reason about objects, affordances, preconditions, and robot capabilities before action.

## Chosen Approach

Use a **Layered Belief Graph + Query Services** architecture.

This combines:

- A persistent semantic/topological world model.
- Agent-facing query tools over that model.
- Swarm-specific belief, provenance, uncertainty, conflict, and commitment tracking.

The design intentionally starts with query services that are useful immediately, but all query results use schemas that can grow into a persistent layered belief graph.

## Architecture

```text
Robot-local 3D substrate
  point clouds, Gaussian splats, poses, sensor frames
        ↓
Metric layer
  occupancy, ESDF, terrain, traversability, collision geometry
        ↓
Region + topology layer
  frontiers, zones, paths, rooms, corridors, outdoor terrain patches
        ↓
Semantic + affordance layer
  objects, hazards, landmarks, humans, manipulable things, affordances
        ↓
Belief + provenance layer
  confidence, source robot, timestamp, frame, conflicts, stale state
        ↓
Commitment layer
  task assignments, route/resource reservations, intentions, locks
        ↓
Agent-facing query API
  find, summarize, plan, check, allocate, explain
```

The raw 3D substrate remains grounded below the reasoning layer. Agents interact with bounded tools over the representation, not with the full dense map.

## Core Data Model

The key primitive is a **claim with evidence**.

Instead of storing a fact as global truth:

```text
PathSegment_4 is blocked.
```

store it as a claim:

```yaml
id: claim_123
subject: path_segment_4
predicate: blocked_by
object: hazard_12
confidence: 0.74
source:
  type: robot
  id: rover_3
observed_at: 2026-05-18T10:41:00Z
frame_id: map
valid_until: 2026-05-18T10:46:00Z
evidence:
  type: point_cloud_slice
  uri: local_submap://rover_3/session_22/slice_91
conflicts_with:
  - claim_098
status: active
```

### Entity Types

The first implementation should support these entity categories:

- `robot`
- `region`
- `frontier`
- `path_segment`
- `terrain_patch`
- `object`
- `hazard`
- `human`
- `landmark`
- `affordance`
- `task`
- `resource`
- `commitment`

### Relation Types

The first implementation should support these relation categories:

- `contains`
- `connects`
- `near`
- `blocks`
- `observed_by`
- `reachable_by`
- `assigned_to`
- `reserved_by`
- `requires_capability`
- `has_affordance`
- `conflicts_with`

### Required Belief Metadata

Every claim returned to an agent should include:

- `id`
- `subject`
- `predicate`
- `object` or scalar value
- `confidence`
- `source`
- `observed_at`
- `frame_id`
- `evidence`
- `status`

`source` may be a robot, detector, planner, human operator, simulator, or imported map.

When available, claims should also include:

- `valid_until` or `stale_after`
- `conflicts_with`
- `uncertainty_region`
- `robot_type_applicability`
- `last_confirmed_by`

## Agent Query API

Agents should access the representation through four tool families.

### 1. Perception Queries

Purpose: discover and summarize semantic state.

Initial tools:

```text
find_objects(query, region=None, min_confidence=None)
find_hazards(region=None, hazard_type=None)
summarize_region(region_id, include_uncertainty=True)
retrieve_evidence(claim_id)
```

Example output:

```yaml
objects:
  - id: object_42
    label: red_vehicle
    region: region_8
    confidence: 0.81
    source: drone_2
    observed_at: 2026-05-18T10:40:12Z
    evidence: image://drone_2/frame_5401
```

### 2. Navigation Queries

Purpose: reason about movement, exploration, and traversability.

Initial tools:

```text
get_frontiers(region=None, robot_type=None)
query_traversability(region_or_path, robot_type)
plan_route(robot_id, goal, constraints=None)
explain_blockage(route_or_region)
```

Example output:

```yaml
feasible: false
reason: path_segment_4 blocked_by hazard_12
confidence: 0.74
source: rover_3
alternatives:
  - send_robot: legged_1
  - request_confirmation: drone_2
  - route: path_segment_7
```

### 3. Coordination Queries

Purpose: allocate work and avoid multi-robot conflicts.

Initial tools:

```text
allocate_task(task, candidate_robots=None)
reserve_resource(resource_id, robot_id, time_window)
list_commitments(region=None, robot_id=None)
detect_conflicts(plan_or_commitment)
```

Example output:

```yaml
selected_robot: legged_1
reason: highest feasibility under terrain and battery constraints
commitments_created:
  - commitment_22
conflicts:
  - resource corridor_4 reserved by rover_2 until 10:47
```

### 4. Belief Queries

Purpose: inspect confidence, staleness, contradictions, and missing evidence.

Initial tools:

```text
get_confidence(claim_or_entity_id)
check_staleness(claim_or_region_id)
compare_claims(claim_ids)
request_confirmation(target, preferred_robot_type=None)
```

Example output:

```yaml
claim: claim_123
status: stale
reason: valid_until elapsed
recommended_action:
  request_confirmation:
    target: path_segment_4
    preferred_robot_type: drone
```

## Observation-to-Belief Flow

```text
Robot observes scene
  image, LiDAR, point cloud, splat update, pose
        ↓
Local extractors
  occupancy, terrain, objects, hazards, frontiers
        ↓
Claim builder
  normalize entity IDs, confidence, timestamp, evidence pointer
        ↓
Fusion/conflict resolver
  merge, supersede, conflict, mark stale
        ↓
Belief graph update
```

The first implementation should treat local extractor outputs as claims, not truth. Fusion decides whether a claim updates an existing entity, creates a new entity, supersedes older claims, or remains as a conflict.

## Agent-Decision-to-Action Flow

```text
Agent asks tool
  search, route, inspect, allocate
        ↓
Planner/checker
  route feasibility, collision, capability, commitments
        ↓
Commitment writer
  assign task, reserve route/resource, set intent
        ↓
Robot executor
  behavior tree, action primitive, local controller
        ↓
Execution feedback
  complete, blocked, failed, new observation
```

Agents may propose and coordinate actions. Local robot controllers retain authority over low-latency safety, collision avoidance, and final execution feasibility.

## Error Handling and Conflict Semantics

The representation should avoid silently collapsing conflicting evidence into one false certainty.

Use these statuses for claims:

- `active`: currently accepted as best available belief.
- `superseded`: replaced by newer or better evidence.
- `conflicted`: contradicted by another live claim.
- `stale`: no longer fresh enough for confident action.
- `rejected`: failed validation or known false positive.

When a query depends on conflicted or stale data, the tool should return a degraded answer with a recommended next step, such as requesting confirmation or choosing a lower-risk robot.

## Testing Strategy

Test the representation independently from robot hardware first.

### Unit Tests

- Claim creation and required metadata validation.
- Entity/relation insertion.
- Claim status transitions: active, superseded, conflicted, stale, rejected.
- Query response schemas for all four tool families.
- Robot-type-specific traversability logic.

### Integration Tests

- Observation-to-belief update creates expected entities and claims.
- Conflicting robot reports remain visible instead of being silently overwritten.
- Route planning rejects paths blocked by active hazard claims.
- Stale hazard claims trigger confirmation recommendations.
- Task allocation respects robot capabilities and existing commitments.

### Scenario Tests

Use small synthetic indoor/outdoor scenarios:

1. Indoor blocked doorway: wheeled robot must reroute; drone can inspect.
2. Outdoor rough terrain: legged robot is preferred over wheeled robot.
3. Search frontier conflict: two robots report different traversability for the same path.
4. Manipulation precondition: object exists but no available robot has the required affordance.

## Non-Goals

- Do not make the LLM consume raw point clouds, splats, or full graph dumps.
- Do not require a complete ontology before the first useful query tools exist.
- Do not solve low-level SLAM, splat reconstruction, or object detection in this layer.
- Do not let the agent bypass local controller safety checks.
- Do not assume a single globally consistent map in communication-limited swarm settings.

## Open Design Constraints

These should be decided during implementation planning:

1. Storage backend for the belief graph.
2. Runtime API shape: Python service, ROS node, database-backed service, or local library.
3. Exact evidence URI format for point-cloud slices, splat regions, images, and detector outputs.
4. Fusion policy for entity identity across robots.
5. Whether commitments are stored in the same graph or a separate scheduler-owned store.

## Success Criteria

The representation is successful when an agent can ask bounded questions and receive grounded answers with evidence, confidence, and action implications.

Minimum successful demo:

1. Ingest synthetic observations from at least two robots.
2. Create entities, relations, and claims with provenance.
3. Detect a conflict between two robot observations.
4. Answer one query from each tool family.
5. Return route or task recommendations that include confidence and explanation.
6. Refuse or degrade recommendations when required data is stale or conflicted.
