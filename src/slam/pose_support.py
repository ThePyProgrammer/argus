"""Numerical pose-chain support, separate from registration acceptance.

This is a necessary-condition gate for ICP navigation, not an accuracy bound
or calibrated covariance. A discarded motion direction cannot be recovered by
chaining a later full-rank *relative* alignment to the already affected pose.
"""
from dataclasses import dataclass
import math


SUPPORT_VERSION = 'icp_observability_chain_v1'


@dataclass
class PoseChainSupport:
    state: str = 'unavailable'
    observed_at_s: float | None = None
    first_loss_s: float | None = None
    observable_rank: int | None = None
    _history_lost: bool = False

    def update(self, now, *, accepted, rank, seeded=False):
        self.observable_rank = rank if type(rank) is int and 0 <= rank <= 6 else None
        initial_seed = seeded and self.observed_at_s is None and self.observable_rank == 0
        lost_now = accepted and not initial_seed and self.observable_rank != 6
        valid_time = type(now) in (int, float) and math.isfinite(now)
        if lost_now and not self._history_lost:
            self._history_lost = True
            self.first_loss_s = float(now) if valid_time else None
        if self._history_lost:
            # Even malformed timestamps must not hide an accepted, unsupported
            # increment. A later relative match cannot repair that history.
            self.state = 'unobservable_motion' if lost_now else 'unobservable_history'
            if valid_time:
                self.observed_at_s = float(now)
            return
        if not valid_time:
            self.state = 'invalid'
            return
        if self.observed_at_s is not None and now <= self.observed_at_s:
            self.state = 'invalid'
            return
        self.observed_at_s = float(now)
        if not accepted:
            # Rejected frames do not advance the ICP reference. A later full-
            # rank match to that reference can still recover the relative motion.
            self.state = 'unavailable'
        elif initial_seed:
            self.state = 'seeded'
        elif self.observable_rank == 6:
            self.state = 'observable'

    @property
    def supported(self):
        return self.state in {'seeded', 'observable'}

    def snapshot(self):
        return dict(version=SUPPORT_VERSION, state=self.state,
                    observed_at_s=self.observed_at_s, first_loss_s=self.first_loss_s,
                    observable_rank=self.observable_rank,
                    map_insertion_allowed=self.supported,
                    translation_bound_m=None, attitude_bound_rad=None,
                    historical_map_bound_m=None,
                    scope='numerical_support_only_not_an_accuracy_bound')


def navigation_support_error(value, now, max_age):
    """Validate required backend evidence at its navigation/map consumer."""
    if not isinstance(value, dict) or value.get('version') != SUPPORT_VERSION:
        return 'pose_support_unavailable'
    state = value.get('state')
    if state in {'unobservable_motion', 'unobservable_history'}:
        return 'pose_history_unobservable'
    timestamp = value.get('observed_at_s')
    if (isinstance(timestamp, bool) or not isinstance(timestamp, (int, float))
            or not math.isfinite(timestamp) or type(now) not in (int, float)
            or not math.isfinite(now) or type(max_age) not in (int, float)
            or not math.isfinite(max_age) or max_age < 0):
        return 'pose_support_invalid'
    if not 0 <= now - timestamp <= max_age:
        return 'pose_support_stale'
    if state == 'unavailable':
        return 'pose_support_unavailable'
    rank = value.get('observable_rank')
    if (state not in {'seeded', 'observable'} or type(rank) is not int
            or rank != (0 if state == 'seeded' else 6)
            or value.get('first_loss_s') is not None
            or value.get('map_insertion_allowed') is not True):
        return 'pose_support_invalid'
    return None
