import { describe, it, expect } from 'vitest';
import { useSlamStore } from '../slamStore';
import { useDetectorStore } from '../detectorStore';

// DET-UI-06 / D-03: detectorStore structural equivalence with slamStore.
//
// Three layers of checking:
//   (1) Superset: every slamStore key has a detectorStore counterpart.
//   (2) Exact extras: the extra keys beyond slamStore's set match the
//       documented 12-item additions set (10 lifter + 2 restart-subsystem
//       fields from Plan 10 Task 1).
//   (3) Setter-arity parity: every SLAM setter has an equivalent-arity
//       detector setter.
//
// This test is the contract — any future plan that adds a detectorStore
// field or setter MUST update EXPECTED_EXTRAS in the same commit. The
// `new Set(extras).toEqual(EXPECTED_EXTRAS)` assertion is symmetric: both
// MISSING and EXTRA keys fail it (two-way drift gate, T-03-29 mitigation).

const EXPECTED_EXTRAS = new Set<string>([
  // Lifter state (Plan 04 / D-02)
  'lifters',
  'activeLifter',
  'activeLifterDisplay',
  'activeLifterParameters',
  'stagedLifterParams',
  // Lifter setters (Plan 04 / D-02)
  'setLifters',
  'setActiveLifter',
  'stageLifterParam',
  'clearStagedLifterParams',
  'updateActiveLifterParam',
  // Restart-subsystem tracking (Plan 10 Task 1 / D-12)
  'restartSubsystem',
  'setRestartSubsystem',
]);

describe('detectorStore structural equivalence with slamStore (D-03)', () => {
  const slamState = useSlamStore.getState() as Record<string, unknown>;
  const detState = useDetectorStore.getState() as Record<string, unknown>;
  const slamKeys = new Set(Object.keys(slamState));
  const detKeys = new Set(Object.keys(detState));

  it('detectorStore has every slamStore key (superset)', () => {
    const missing = [...slamKeys].filter((k) => !detKeys.has(k));
    expect(missing).toEqual([]);
  });

  it('detectorStore extras match the documented additions set', () => {
    const extras = [...detKeys].filter((k) => !slamKeys.has(k));
    expect(new Set(extras)).toEqual(EXPECTED_EXTRAS);
  });

  it('every slamStore setter has an equivalent-arity detectorStore setter', () => {
    const slamSetters = [...slamKeys].filter(
      (k) => typeof slamState[k] === 'function',
    );
    for (const setter of slamSetters) {
      const detFn = detState[setter];
      expect(typeof detFn).toBe('function');
      // Function.length = parameter count (excluding rest params).
      // Mismatch signals a signature drift like
      //   setActive(name, display, parameters) vs setActive(name).
      expect((detFn as Function).length).toBe(
        (slamState[setter] as Function).length,
      );
    }
  });
});
