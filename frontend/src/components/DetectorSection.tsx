import { useState, useEffect, useCallback } from 'react';
import { DetectorDropdown } from './DetectorDropdown';
import { LifterDropdown } from './LifterDropdown';
import { DetectorParameterPanel } from './DetectorParameterPanel';
import { CapabilityBadge } from './CapabilityBadge';
import { ConfirmModal } from './ConfirmModal';
import { useDetectorStore, fetchDetectorState } from '../stores/detectorStore';

// D-05: active-backend capability badges in DetectorSection — same 3 keys as
// dropdown option rows (D-06) for single source of truth.
const ACTIVE_BADGE_KEYS = ['framework', 'license', 'cpu_latency_hint_ms'] as const;

// ---------------------------------------------------------------------------
// Polling fallbacks (mirror pollForRestart in AlgorithmSection.tsx:9-29).
// Fires when the WS path drops detector_restart_complete / lifter_restart_complete
// or the connection flaps. 500ms × 20 attempts = 10s bound (D-15 precedent).
// ---------------------------------------------------------------------------

async function pollForDetectorRestart(expectedBackend: string) {
  const maxAttempts = 20;
  for (let i = 0; i < maxAttempts; i++) {
    await new Promise((r) => setTimeout(r, 500));
    try {
      const res = await fetch('/api/detectors/active');
      if (res.ok) {
        const data = await res.json();
        if (data.backend === expectedBackend) {
          await fetchDetectorState();
          useDetectorStore.getState().setRestarting(false);
          useDetectorStore.getState().setRestartSubsystem(null);
          return;
        }
      }
    } catch {
      /* continue polling */
    }
  }
  useDetectorStore.getState().setError(
    'Detector restart timed out. Try again or refresh the page.',
  );
  useDetectorStore.getState().setRestarting(false);
  useDetectorStore.getState().setRestartSubsystem(null);
}

async function pollForLifterRestart(expectedLifter: string) {
  const maxAttempts = 20;
  for (let i = 0; i < maxAttempts; i++) {
    await new Promise((r) => setTimeout(r, 500));
    try {
      const res = await fetch('/api/detectors/active-lifter');
      if (res.ok) {
        const data = await res.json();
        if (data.lifter === expectedLifter) {
          await fetchDetectorState();
          useDetectorStore.getState().setRestarting(false);
          useDetectorStore.getState().setRestartSubsystem(null);
          return;
        }
      }
    } catch {
      /* continue polling */
    }
  }
  useDetectorStore.getState().setError(
    'Lifter restart timed out. Try again or refresh the page.',
  );
  useDetectorStore.getState().setRestarting(false);
  useDetectorStore.getState().setRestartSubsystem(null);
}

// ---------------------------------------------------------------------------
// DetectorSection — parent component owning the whole detector control surface.
// Mirrors AlgorithmSection.tsx structure (231 lines) with BOTH detector and
// lifter switch flows. Mounts:
//   - DetectorDropdown
//   - Capability badge row (framework, license, cpu_latency_hint_ms) [D-05]
//   - LifterDropdown (gated on outputs_3d_natively === false) [D-07, D-08]
//   - Error banner
//   - DetectorParameterPanel
//   - ConfirmModal (for detector switch) [D-14]
//   - ConfirmModal (for lifter switch) [D-14]
// ---------------------------------------------------------------------------

export default function DetectorSection() {
  const [showSection, setShowSection] = useState(true);
  const [showDetectorModal, setShowDetectorModal] = useState(false);
  const [showLifterModal, setShowLifterModal] = useState(false);
  const [pendingBackend, setPendingBackend] = useState<string | null>(null);
  const [pendingLifter, setPendingLifter] = useState<string | null>(null);
  const [switching, setSwitching] = useState(false);

  const backends = useDetectorStore((s) => s.backends);
  const activeBackend = useDetectorStore((s) => s.activeBackend);
  const lifters = useDetectorStore((s) => s.lifters);
  const error = useDetectorStore((s) => s.error);

  // Fetch backends + active + lifters + active-lifter on mount
  useEffect(() => {
    fetchDetectorState();
  }, []);

  const activeBackendInfo = backends.find((b) => b.name === activeBackend);
  // D-08 strict `=== false` comparison: hidden during undefined state
  // (accepts first-render flicker per Research Pitfall #5). Hidden when the
  // active detector advertises native 3D output (future BoxeR).
  const showLifterDropdown =
    activeBackendInfo?.capabilities?.outputs_3d_natively === false;

  const onDetectorSelect = useCallback((name: string) => {
    setPendingBackend(name);
    setShowDetectorModal(true);
  }, []);

  const onLifterSelect = useCallback((name: string) => {
    setPendingLifter(name);
    setShowLifterModal(true);
  }, []);

  const onConfirmDetectorSwitch = useCallback(async () => {
    if (!pendingBackend) return;

    setSwitching(true);

    const picked = useDetectorStore.getState().backends.find(
      (b) => b.name === pendingBackend,
    );
    const pickedDisplay = picked?.display ?? pendingBackend;

    // Set restart state BEFORE the POST so the overlay mounts immediately
    useDetectorStore.getState().setRestarting(true);
    useDetectorStore.getState().setRestartSubsystem('detector');

    // Capture staged params before clearing
    const params = useDetectorStore.getState().stagedParams;
    const body: Record<string, unknown> = { backend: pendingBackend };
    if (Object.keys(params).length > 0) body.params = params;

    try {
      const res = await fetch('/api/detectors/select', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });

      setShowDetectorModal(false);
      setSwitching(false);

      if (!res.ok) {
        useDetectorStore.getState().setError(
          `Failed to switch to ${pickedDisplay}. The previous detector is still active.`,
        );
        useDetectorStore.getState().setRestarting(false);
        useDetectorStore.getState().setRestartSubsystem(null);
        return;
      }

      // Clear staged params AFTER successful POST
      useDetectorStore.getState().clearStagedParams();

      // Start polling fallback — WS handler is the primary dismissal path
      pollForDetectorRestart(pendingBackend);
    } catch {
      setShowDetectorModal(false);
      setSwitching(false);
      useDetectorStore.getState().setError(
        `Failed to switch to ${pickedDisplay}. The previous detector is still active.`,
      );
      useDetectorStore.getState().setRestarting(false);
      useDetectorStore.getState().setRestartSubsystem(null);
    }

    setPendingBackend(null);
  }, [pendingBackend]);

  const onConfirmLifterSwitch = useCallback(async () => {
    if (!pendingLifter) return;

    setSwitching(true);

    const picked = useDetectorStore.getState().lifters.find(
      (l) => l.name === pendingLifter,
    );
    const pickedDisplay = picked?.display ?? pendingLifter;

    useDetectorStore.getState().setRestarting(true);
    useDetectorStore.getState().setRestartSubsystem('lifter');

    const params = useDetectorStore.getState().stagedLifterParams;
    const body: Record<string, unknown> = { lifter: pendingLifter };
    if (Object.keys(params).length > 0) body.params = params;

    try {
      const res = await fetch('/api/detectors/lifter-select', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });

      setShowLifterModal(false);
      setSwitching(false);

      if (!res.ok) {
        useDetectorStore.getState().setError(
          `Failed to switch lifter to ${pickedDisplay}. The previous lifter is still active.`,
        );
        useDetectorStore.getState().setRestarting(false);
        useDetectorStore.getState().setRestartSubsystem(null);
        return;
      }

      useDetectorStore.getState().clearStagedLifterParams();
      pollForLifterRestart(pendingLifter);
    } catch {
      setShowLifterModal(false);
      setSwitching(false);
      useDetectorStore.getState().setError(
        `Failed to switch lifter to ${pickedDisplay}. The previous lifter is still active.`,
      );
      useDetectorStore.getState().setRestarting(false);
      useDetectorStore.getState().setRestartSubsystem(null);
    }

    setPendingLifter(null);
  }, [pendingLifter]);

  const pendingDetectorDisplay = pendingBackend
    ? (backends.find((b) => b.name === pendingBackend)?.display ?? pendingBackend)
    : '';
  const pendingLifterDisplay = pendingLifter
    ? (lifters.find((l) => l.name === pendingLifter)?.display ?? pendingLifter)
    : '';

  return (
    <div>
      {/* Section header — mirrors SLAM ALGORITHM styling (12px bold #888) */}
      <div
        onClick={() => setShowSection(!showSection)}
        style={{
          borderTop: '1px solid #2a2a4a',
          paddingTop: '16px',
          marginTop: '16px',
          cursor: 'pointer',
          userSelect: 'none',
          display: 'flex',
          justifyContent: 'space-between',
        }}
      >
        <span style={{ fontSize: '12px', fontWeight: 600, color: '#888' }}>
          OBJECT DETECTION
        </span>
        <span style={{ fontSize: '10px', color: '#888' }}>
          {showSection ? '\u25BC' : '\u25B6'}
        </span>
      </div>

      {/* Section body */}
      {showSection && (
        <div style={{ marginTop: '8px' }}>
          {/* Detector dropdown */}
          <DetectorDropdown onSelect={onDetectorSelect} />

          {/* D-05: active-backend capability badges */}
          {activeBackendInfo && (
            <div style={{ marginTop: '8px', display: 'flex', flexWrap: 'wrap' }}>
              {ACTIVE_BADGE_KEYS.map((key) => (
                <CapabilityBadge
                  key={key}
                  label={key}
                  value={activeBackendInfo.capabilities[key]}
                />
              ))}
            </div>
          )}

          {/* D-07 / D-08: Lifter dropdown inline; visibility gated on
              outputs_3d_natively === false (strict) */}
          {showLifterDropdown && (
            <div style={{ marginTop: '12px' }}>
              <LifterDropdown onSelect={onLifterSelect} />
            </div>
          )}

          {/* Error banner */}
          {error !== null && (
            <div
              style={{
                background: 'rgba(211, 47, 47, 0.15)',
                border: '1px solid rgba(211, 47, 47, 0.3)',
                borderRadius: '4px',
                padding: '8px',
                fontSize: '11px',
                color: '#ef5350',
                margin: '8px 0',
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
              }}
            >
              <span>{error}</span>
              <button
                onClick={() => useDetectorStore.getState().setError(null)}
                aria-label="Dismiss error"
                style={{
                  border: 'none',
                  background: 'none',
                  color: '#ef5350',
                  fontSize: '13px',
                  cursor: 'pointer',
                  padding: 0,
                }}
              >
                x
              </button>
            </div>
          )}

          {/* Parameter panel (detector params; lifter params are inside
              LifterDropdown's own live-tunable surface if any) */}
          <DetectorParameterPanel />
        </div>
      )}

      {/* D-14: Confirm modal — detector switch copy */}
      {showDetectorModal && (
        <ConfirmModal
          heading="Switch Detector"
          body={`Switch detector to ${pendingDetectorDisplay}? This will restart perception.`}
          confirmLabel="Switch Detector"
          cancelLabel="Keep Current"
          confirmDisabled={switching}
          confirmText={switching ? 'Switching...' : undefined}
          onConfirm={onConfirmDetectorSwitch}
          onCancel={() => {
            setShowDetectorModal(false);
            setPendingBackend(null);
          }}
        />
      )}

      {/* D-14: Confirm modal — lifter switch copy */}
      {showLifterModal && (
        <ConfirmModal
          heading="Switch Lifter"
          body={`Switch lifter to ${pendingLifterDisplay}? This will restart the current session.`}
          confirmLabel="Switch Lifter"
          cancelLabel="Keep Current"
          confirmDisabled={switching}
          confirmText={switching ? 'Switching...' : undefined}
          onConfirm={onConfirmLifterSwitch}
          onCancel={() => {
            setShowLifterModal(false);
            setPendingLifter(null);
          }}
        />
      )}
    </div>
  );
}
