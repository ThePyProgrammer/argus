"""Path smoothing and resampling (adapted from DimOS).

Takes a jagged A* grid path and produces a smooth, evenly-spaced path
suitable for pure pursuit following.
"""


import numpy as np
from scipy.ndimage import uniform_filter1d


def smooth_path(
    waypoints: list[np.ndarray],
    resample_spacing: float = 0.1,
    smoothing_window: int = 50,
    upsample_factor: int = 10,
) -> list[np.ndarray]:
    """Smooth and resample an A* path.

    Steps:
    1. Upsample: linearly interpolate between waypoints (10x by default)
    2. Smooth: moving average filter removes grid artifacts
    3. Resample: uniform spacing for consistent pure pursuit behavior

    Args:
        waypoints: List of (3,) float64 waypoints from A*.
        resample_spacing: Desired spacing between output waypoints in meters.
        smoothing_window: Moving average window size (in upsampled points).
        upsample_factor: How many points to interpolate between each pair.

    Returns:
        Smoothed and resampled list of (3,) float64 waypoints.
    """
    if len(waypoints) < 3:
        return waypoints

    pts = np.array(waypoints)  # (N, 3)

    # Step 1: Upsample
    upsampled = []
    for i in range(len(pts) - 1):
        for t in np.linspace(0, 1, upsample_factor, endpoint=False):
            upsampled.append(pts[i] + t * (pts[i + 1] - pts[i]))
    upsampled.append(pts[-1])
    upsampled = np.array(upsampled)

    # Step 2: Smooth with moving average
    window = min(smoothing_window, len(upsampled) // 2)
    if window >= 3:
        smoothed = np.copy(upsampled)
        smoothed[:, 0] = uniform_filter1d(upsampled[:, 0], size=window, mode='nearest')
        smoothed[:, 1] = uniform_filter1d(upsampled[:, 1], size=window, mode='nearest')
        # Don't smooth Z (keep ground level)
    else:
        smoothed = upsampled

    # Step 3: Resample at uniform spacing
    # Compute cumulative arc length
    diffs = np.diff(smoothed[:, :2], axis=0)
    segment_lengths = np.sqrt((diffs ** 2).sum(axis=1))
    cumulative = np.concatenate([[0], np.cumsum(segment_lengths)])
    total_length = cumulative[-1]

    if total_length < resample_spacing:
        return waypoints  # path too short to resample

    # Interpolate at uniform intervals
    n_points = max(2, int(total_length / resample_spacing))
    target_distances = np.linspace(0, total_length, n_points)

    resampled = []
    for d in target_distances:
        idx = np.searchsorted(cumulative, d, side='right') - 1
        idx = min(idx, len(smoothed) - 2)
        if segment_lengths[idx] > 1e-6:
            t = (d - cumulative[idx]) / segment_lengths[idx]
            t = np.clip(t, 0, 1)
            pt = smoothed[idx] + t * (smoothed[idx + 1] - smoothed[idx])
        else:
            pt = smoothed[idx].copy()
        resampled.append(pt)

    return resampled
