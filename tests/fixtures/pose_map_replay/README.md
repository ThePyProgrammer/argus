# Frozen pose/map comparisons

These small, synthetic NPZ fixtures were frozen on November 18, 2026. They
contain accepted world points, estimated and known camera poses, baseline floor
masks, frame times, and ragged-array offsets. They are analytical unit fixtures,
not live SLAM captures. No random sampling or simulator state is required.

- `translation_drift`: a 24-by-24 floor patch spanning [-1, 1] in X/Y and a
  wall at X=2.06 m, with 10 Y values in [-0.5, 0.5] and 12 heights from 0.06
  to 0.8 m. The second estimated pose/scan has an 0.08 m X error. Floor labels
  stay correct, while wall placement changes.
- `historical_placement`: the same observations, but the first pose/scan has
  the 0.08 m error and the second is exact. Correct current pose and floor
  labels must not erase the earlier wall-placement error.
- `narrow_floor`: first, 50 collinear floor points from X=0.2 to 1 m, with
  matching points raised 0.06 m; then a broad floor patch; then the narrow
  view with additional 6 mm features at Y=1.2 m. This distinguishes lack of
  initial plane support, successful historical cleanup, preserved 6 cm
  obstacles, and 6 mm features inside the existing 15 mm classification band.

All true cameras have identity rotation and origin [0, 0, 0.32] m. Frames are
0.01 seconds apart. Baseline masks use the unchanged default `FloorTracker`.
Tests assert independent geometric errors/labels as well as mask repeatability;
they do not treat those saved masks as ground truth. Diagnostic floor labels
use |Z| <= 2 mm, with 2–4 mm left ambiguous. Fixed-world voxel comparisons use
0.10 m cells and do not reuse the runtime map's cloud-dependent voxel origin.
