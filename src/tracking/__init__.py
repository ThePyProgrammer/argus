"""Tracker package — TrackerProtocol + TrackerRegistry + built-in trackers.

Phase 7 ships NoneTracker passthrough (D-13). ByteTrack ships Phase 8
(DET-STRETCH-01). Mirror of src/perception/ package shape; per Pitfall P9,
module-scope imports are stdlib only — heavy deps (numpy, torch) reach via
lazy class-path loading inside ``TrackerRegistry.create()``.
"""
