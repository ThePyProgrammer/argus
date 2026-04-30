"""Generate spawn positions for N robots.

Provides curated office positions and a greedy spread algorithm
to place N robots as far apart as possible.
"""


import random

# Known valid positions inside the DimOS office scene.
# Open floor areas away from walls and furniture.
OFFICE_SPAWNS = [
    (-1.0, 1.0),    # main room center
    (-2.5, 0.0),    # main room left
    (0.5, 1.5),     # main room right
    (-1.0, -1.0),   # main room back
    (1.0, 0.0),     # near doorway
    (-3.0, 1.5),    # far left corner
    (-0.5, 2.5),    # near window
    (1.5, 2.0),     # right side
    (-2.0, 2.0),    # left open area
    (0.0, 0.0),     # center
    (-1.5, -0.5),   # back left
    (0.5, -0.5),    # back right
]


def generate_robot_ids(n: int) -> tuple[str, ...]:
    """Generate N robot IDs: robot_a, robot_b, robot_c, ..."""
    return tuple(f"robot_{chr(ord('a') + i)}" for i in range(n))


def generate_spawn_positions(
    robot_ids: tuple[str, ...],
    scene: str = "office",
    spawn_height: float = 0.3,
) -> dict[str, tuple[float, float, float]]:
    """Generate spread-out spawn positions for N robots.

    For office scene, uses greedy farthest-point sampling from
    curated positions. For flat scene, places robots in a line.

    Args:
        robot_ids: Tuple of robot ID strings.
        scene: "office" or "flat".
        spawn_height: Z height for every generated spawn position.

    Returns:
        Dict mapping robot_id to (x, y, z) spawn position.
    """
    n = len(robot_ids)

    if scene == "flat":
        # Line formation, 5m apart
        positions = {}
        for i, rid in enumerate(robot_ids):
            positions[rid] = (i * 5.0, 0.0, float(spawn_height))
        return positions

    # Office: greedy farthest-point sampling from curated positions
    candidates = list(OFFICE_SPAWNS)
    random.shuffle(candidates)

    if n > len(candidates):
        # More robots than positions -- add random offsets to existing ones
        while len(candidates) < n:
            base = random.choice(OFFICE_SPAWNS)
            offset = (base[0] + random.uniform(-0.5, 0.5),
                      base[1] + random.uniform(-0.5, 0.5))
            candidates.append(offset)

    # Greedy: pick first randomly, then always pick the farthest from all selected
    selected = [candidates.pop(0)]
    for _ in range(n - 1):
        best_idx = 0
        best_min_dist = -1
        for i, c in enumerate(candidates):
            min_dist = min((c[0] - s[0])**2 + (c[1] - s[1])**2 for s in selected)
            if min_dist > best_min_dist:
                best_min_dist = min_dist
                best_idx = i
        selected.append(candidates.pop(best_idx))

    positions = {}
    for rid, pos in zip(robot_ids, selected):
        positions[rid] = (pos[0], pos[1], float(spawn_height))
    return positions
