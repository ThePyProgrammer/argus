import { describe, it, expect } from 'vitest';
import { useMetricsStore } from '../metricsStore';
import type {
  SlamMetrics,
  MetricHistory,
  DetectionMetrics,
  DetectionMetricHistory,
  DetectionGtMetrics,
} from '../../utils/messageTypes';

// DET-METRICS-01 / SC#2 revision 2026-04-15 — metricsStore detection slice shape.
//
// This test replaces the Wave 0 skip-stub. It asserts the three detection
// slices (detectionPerRobot, detectionHistory, detectionGtPerRobot) exist,
// that `updateAllMetrics` accepts all 6 args in a SINGLE set() call
// (preserves the one-re-render-per-stats invariant from Phase v2.0 13-01),
// and that the SC#2 per-class GT payload round-trips through the store.

describe('metricsStore detection slice shape (DET-METRICS-01)', () => {
  it('initial state contains detectionPerRobot + detectionHistory + detectionGtPerRobot as empty records', () => {
    const s = useMetricsStore.getState();
    expect(s.detectionPerRobot).toBeDefined();
    expect(s.detectionHistory).toBeDefined();
    expect(s.detectionGtPerRobot).toBeDefined();
    expect(typeof s.detectionPerRobot).toBe('object');
    expect(typeof s.detectionHistory).toBe('object');
    expect(typeof s.detectionGtPerRobot).toBe('object');
    // The three new slices must not leak forbidden vocabulary into their keys.
    const keys = Object.keys(s);
    const forbidden = ['mAP', 'map_50', 'map_75', 'mean_average_precision'];
    for (const f of forbidden) {
      expect(keys).not.toContain(f);
    }
  });

  it('updateAllMetrics accepts 6 args and writes all in one set() call', () => {
    const slam: Record<string, SlamMetrics> = {
      r0: {
        ate_rmse: 0.042,
        ate_mean: 0.03,
        rpe_rmse: 0.018,
        rpe_mean: 0.012,
        ms_per_frame: 12.5,
        tracking_status: 'ok',
      },
    };
    const history: Record<string, MetricHistory> = {
      r0: {
        ate_rmse: [0.04, 0.042],
        rpe_rmse: [0.017, 0.018],
        ms_per_frame: [12.0, 12.5],
        timestamps: [1.0, 2.0],
      },
    };
    const detection: Record<string, DetectionMetrics> = {
      r0: {
        inference_ms_p50: 12.0,
        inference_ms_p95: 40.0,
        detections_per_frame: 3,
        mean_confidence: 0.87,
        queue_depth: 1,
        freshness_s: 0.5,
        jitter_m: 0.001,
      },
    };
    const detHist: Record<string, DetectionMetricHistory> = {
      r0: {
        inference_ms: [12.0],
        det_per_frame: [3],
        confidence: [0.87],
        freshness: [0.5],
        jitter: [0.001],
      },
    };
    const detGt: Record<string, DetectionGtMetrics> = {
      r0: { chair: { center_error_m: 0.12, per_class_recall: 0.66 } },
    };

    let notifications = 0;
    const unsub = useMetricsStore.subscribe(() => {
      notifications += 1;
    });
    useMetricsStore.getState().updateAllMetrics(
      slam,
      null,
      history,
      detection,
      detHist,
      detGt,
    );
    unsub();

    // Single set() call emits exactly 1 subscription notification.
    expect(notifications).toBe(1);

    const s = useMetricsStore.getState();
    expect(s.perRobot.r0?.ate_rmse).toBe(0.042);
    expect(s.detectionPerRobot.r0?.inference_ms_p50).toBe(12.0);
    expect(s.detectionPerRobot.r0?.inference_ms_p95).toBe(40.0);
    expect(s.detectionPerRobot.r0?.mean_confidence).toBe(0.87);
    expect(s.detectionPerRobot.r0?.freshness_s).toBe(0.5);
    expect(s.detectionPerRobot.r0?.jitter_m).toBe(0.001);
    expect(s.detectionHistory.r0?.inference_ms).toEqual([12.0]);
    // SC#2 round-trip:
    expect(s.detectionGtPerRobot.r0?.chair?.center_error_m).toBe(0.12);
    expect(s.detectionGtPerRobot.r0?.chair?.per_class_recall).toBe(0.66);
  });

  it('does not leak forbidden mAP vocabulary through store state keys', () => {
    const s = useMetricsStore.getState();
    const keys = Object.keys(s);
    const forbidden = ['mAP', 'map_50', 'map_75', 'mean_average_precision'];
    for (const f of forbidden) {
      expect(keys).not.toContain(f);
    }
  });
});
