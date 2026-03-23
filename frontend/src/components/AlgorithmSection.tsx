import { useState, useEffect, useCallback } from 'react';
import { AlgorithmDropdown } from './AlgorithmDropdown';
import { ParameterPanel } from './ParameterPanel';
import { CapabilityBadge } from './CapabilityBadge';
import { ConfirmModal } from './ConfirmModal';
import { useSlamStore, fetchSlamState } from '../stores/slamStore';
import { useRobotStore } from '../stores/robotStore';

async function pollForRestart(expectedBackend: string) {
  const maxAttempts = 20;
  for (let i = 0; i < maxAttempts; i++) {
    await new Promise((r) => setTimeout(r, 500));
    try {
      const res = await fetch('/api/slam/active');
      if (res.ok) {
        const data = await res.json();
        if (data.backend === expectedBackend) {
          await fetchSlamState();
          useSlamStore.getState().setRestarting(false);
          return;
        }
      }
    } catch {
      /* continue polling */
    }
  }
  useSlamStore.getState().setError('Restart timed out. Try again or refresh the page.');
  useSlamStore.getState().setRestarting(false);
}

export default function AlgorithmSection() {
  const [showSection, setShowSection] = useState(true);
  const [showModal, setShowModal] = useState(false);
  const [pendingBackend, setPendingBackend] = useState<string | null>(null);
  const [switching, setSwitching] = useState(false);

  const backends = useSlamStore((s) => s.backends);
  const activeBackend = useSlamStore((s) => s.activeBackend);
  const error = useSlamStore((s) => s.error);

  // Fetch backends and active state on mount
  useEffect(() => {
    fetchSlamState();
  }, []);

  const onSelect = useCallback((backendName: string) => {
    setPendingBackend(backendName);
    setShowModal(true);
  }, []);

  const onConfirmSwitch = useCallback(async () => {
    if (!pendingBackend) return;

    setSwitching(true);

    // Find display name for the pending backend
    const selectedBackend = useSlamStore.getState().backends.find(
      (b) => b.name === pendingBackend,
    );
    const pendingDisplayName = selectedBackend?.display ?? pendingBackend;

    // Set restarting state
    useSlamStore.getState().setRestarting(true);

    // Capture staged params BEFORE clearing
    const params = useSlamStore.getState().stagedParams;

    // Clear point cloud
    useRobotStore.getState().setCloudFull([], []);

    // Reset robot poses and trajectories
    const robotState = useRobotStore.getState();
    const robots = new Map(robotState.robots);
    for (const [id, robot] of robots) {
      robots.set(id, {
        ...robot,
        position: [0, 0, 0] as [number, number, number],
        rotation: [1, 0, 0, 0, 1, 0, 0, 0, 1],
        trajectory: [],
        trajectoryAlphas: [],
      });
    }
    useRobotStore.setState({ robots });

    // POST to /api/slam/select with staged params included in body
    const body: Record<string, unknown> = { backend: pendingBackend };
    if (Object.keys(params).length > 0) {
      body.params = params;
    }

    try {
      const res = await fetch('/api/slam/select', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });

      // Close modal
      setShowModal(false);
      setSwitching(false);

      if (!res.ok) {
        useSlamStore.getState().setError(
          `Failed to switch to ${pendingDisplayName}. The previous algorithm is still active.`,
        );
        useSlamStore.getState().setRestarting(false);
        return;
      }

      // Clear staged params AFTER successful POST
      useSlamStore.getState().clearStagedParams();

      // Start polling for restart completion
      pollForRestart(pendingBackend);
    } catch {
      setShowModal(false);
      setSwitching(false);
      useSlamStore.getState().setError(
        `Failed to switch to ${pendingDisplayName}. The previous algorithm is still active.`,
      );
      useSlamStore.getState().setRestarting(false);
    }

    setPendingBackend(null);
  }, [pendingBackend]);

  // Find active backend for capability badges
  const activeBackendInfo = backends.find((b) => b.name === activeBackend);
  const activeCapabilities = activeBackendInfo
    ? Object.entries(activeBackendInfo.capabilities)
        .filter(([, v]) => v === true)
        .map(([k]) => k)
    : [];

  // Derive pending display name for modal
  const pendingDisplayName = pendingBackend
    ? (backends.find((b) => b.name === pendingBackend)?.display ?? pendingBackend)
    : '';

  return (
    <div>
      {/* Section header */}
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
        <span style={{ fontSize: '12px', fontWeight: 600, color: '#888' }}>SLAM ALGORITHM</span>
        <span style={{ fontSize: '10px', color: '#888' }}>{showSection ? '\u25BC' : '\u25B6'}</span>
      </div>

      {/* Section body */}
      {showSection && (
        <div style={{ marginTop: '8px' }}>
          {/* Algorithm dropdown */}
          <AlgorithmDropdown onSelect={onSelect} />

          {/* Capability badges for active backend */}
          {activeCapabilities.length > 0 && (
            <div style={{ marginTop: '8px', display: 'flex', flexWrap: 'wrap' }}>
              {activeCapabilities.map((cap) => (
                <CapabilityBadge key={cap} name={cap} />
              ))}
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
                onClick={() => useSlamStore.getState().setError(null)}
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

          {/* Parameter panel */}
          <ParameterPanel />
        </div>
      )}

      {/* Confirmation modal */}
      {showModal && (
        <ConfirmModal
          heading="Switch Algorithm"
          body={`Switch to ${pendingDisplayName}? This will restart the current session.`}
          confirmLabel="Switch Algorithm"
          cancelLabel="Keep Current"
          confirmDisabled={switching}
          confirmText={switching ? 'Switching...' : undefined}
          onConfirm={onConfirmSwitch}
          onCancel={() => {
            setShowModal(false);
            setPendingBackend(null);
          }}
        />
      )}
    </div>
  );
}
