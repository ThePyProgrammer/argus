import { useEffect, useState } from 'react';
import { usePipelineStore } from '../../stores/pipelineStore';

import { ConfirmModal } from '../ConfirmModal';
import { RestartOverlay } from '../RestartOverlay';
import { PresetSelector } from './PresetSelector';

interface HotApplyToastState {
  visible: boolean;
  changed: string[];
}

export function ApplyBar() {
  const isDirty = usePipelineStore((s) => s.isDirty);
  const isValid = usePipelineStore((s) => s.isValid);
  const validationErrors = usePipelineStore((s) => s.validationErrors);
  const isApplying = usePipelineStore((s) => s.isApplying);

  const [showConfirm, setShowConfirm] = useState(false);
  const [showErrors, setShowErrors] = useState(false);
  const [applyError, setApplyError] = useState<string | null>(null);
  const [hotToast, setHotToast] = useState<HotApplyToastState>({ visible: false, changed: [] });

  // Auto-dismiss toast after 3000ms (UI-SPEC Lifetime 3000ms + 200ms fade).
  useEffect(() => {
    if (!hotToast.visible) return;
    const timeoutId = window.setTimeout(() => {
      setHotToast((prev) => ({ ...prev, visible: false }));
    }, 3000);
    return () => window.clearTimeout(timeoutId);
  }, [hotToast.visible]);

  function handleApplyClick() {
    usePipelineStore.getState().validate();
    const store = usePipelineStore.getState();
    if (!store.isValid) {
      setShowErrors(true);
      return;
    }
    setShowConfirm(true);
  }

  function handleConfirmApply() {
    setShowConfirm(false);
    setApplyError(null);
    const store = usePipelineStore.getState();
    store.setIsApplying(true);
    const config = store.serializeForApply();

    fetch('/api/pipeline/apply', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ nodes: config.nodes, edges: config.edges }),
    })
      .then((res) => {
        if (!res.ok) throw new Error(`Apply failed: ${res.status}`);
        return res.json();
      })
      .then((body) => {
        usePipelineStore.getState().markApplied();
        if (body && body.status === 'hot-applied') {
          // Phase 7 DET-PIPELINE-05 — no restart happened; clear isApplying now
          // (Pitfall 5: no slam_restart_complete WS will fire).
          usePipelineStore.getState().setIsApplying(false);
          const changed = Array.isArray(body.changed) ? (body.changed as string[]) : [];
          setHotToast({ visible: true, changed });
        }
        // status === 'restarting': isApplying cleared by slam_restart_complete WS handler
        // in useWebSocket.ts (existing behavior preserved).
      })
      .catch((err) => {
        setApplyError(err.message ?? 'Pipeline apply failed');
        usePipelineStore.getState().setIsApplying(false);
      });
  }

  const containerStyle: React.CSSProperties = {
    height: 48,
    background: '#1a1a2e',
    borderTop: '1px solid #2a2a4a',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: '0 16px',
    position: 'relative',
  };

  const applyButtonStyle: React.CSSProperties = {
    background: '#4fc3f7',
    color: '#0a0a14',
    fontWeight: 600,
    fontSize: 13,
    padding: '6px 20px',
    borderRadius: 4,
    border: 'none',
    cursor: isApplying || !isDirty ? 'not-allowed' : 'pointer',
    opacity: isApplying || !isDirty ? 0.5 : 1,
  };

  const errorListStyle: React.CSSProperties = {
    position: 'absolute',
    bottom: '100%',
    right: 16,
    background: '#1e1e32',
    border: '1px solid #d32f2f',
    padding: 8,
    borderRadius: 4,
    marginBottom: 4,
    maxWidth: 400,
    maxHeight: 200,
    overflowY: 'auto',
    zIndex: 50,
  };

  // Hot-apply toast — UI-SPEC Hot-Apply Toast Pixel Spec.
  const hotToastStyle: React.CSSProperties = {
    position: 'absolute',
    bottom: '100%',
    left: 16,
    background: '#1e3a2a',
    border: '1px solid #4caf50',
    borderRadius: 4,
    padding: '8px 12px',
    marginBottom: 4,
    minWidth: 240,
    maxWidth: 480,
    zIndex: 50,
    display: 'flex',
    flexDirection: 'column',
    gap: 2,
    cursor: 'pointer',
  };

  return (
    <div style={containerStyle}>
      {/* Left side: preset + modified indicator */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
        <PresetSelector />
        {isDirty && (
          <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
            <div
              style={{
                width: 8,
                height: 8,
                borderRadius: '50%',
                background: '#ff9800',
              }}
            />
            <span style={{ fontSize: 11, color: '#ff9800' }}>Modified</span>
          </div>
        )}
      </div>

      {/* Right side: validation + apply */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
        {/* Validation status */}
        {isValid ? (
          <span style={{ fontSize: 11, color: '#2ecc71' }}>Pipeline valid</span>
        ) : (
          <span
            style={{ fontSize: 11, color: '#d32f2f', cursor: 'pointer' }}
            onClick={() => setShowErrors(!showErrors)}
          >
            {validationErrors.length} validation error{validationErrors.length !== 1 ? 's' : ''}
          </span>
        )}

        {/* Apply error inline */}
        {applyError && (
          <span style={{ fontSize: 11, color: '#d32f2f' }}>{applyError}</span>
        )}

        {/* Apply button */}
        <button
          style={applyButtonStyle}
          onClick={handleApplyClick}
          disabled={isApplying || !isDirty}
        >
          Apply Pipeline
        </button>
      </div>

      {/* Error list popup */}
      {showErrors && validationErrors.length > 0 && (
        <div style={errorListStyle}>
          {validationErrors.map((err, i) => (
            <div key={i} style={{ fontSize: 11, color: '#d32f2f', marginBottom: 4 }}>
              {err.nodeId && (
                <span style={{ color: '#888', marginRight: 4 }}>[{err.nodeId}]</span>
              )}
              {err.message}
            </div>
          ))}
        </div>
      )}

      {/* Hot-apply success toast — Phase 7 DET-PIPELINE-05 */}
      {hotToast.visible && (
        <div
          style={hotToastStyle}
          role="status"
          aria-live="polite"
          onClick={() => setHotToast((p) => ({ ...p, visible: false }))}
        >
          <div style={{
            fontSize: 11,
            fontWeight: 600,
            color: '#a5d6a7',
            lineHeight: 1.4,
            display: 'flex',
            alignItems: 'center',
          }}>
            <span style={{ color: '#4caf50', marginRight: 6, fontSize: 12 }}>{'\u2713'}</span>
            Pipeline updated in place
          </div>
          {hotToast.changed.length > 0 && (
            <div style={{
              fontSize: 10,
              fontWeight: 400,
              color: '#888',
              lineHeight: 1.4,
              marginTop: 2,
            }}>
              {hotToast.changed.join(' \u00b7 ')}
            </div>
          )}
        </div>
      )}

      {/* Confirm modal */}
      {showConfirm && (
        <ConfirmModal
          heading="Apply Pipeline"
          body="Apply pipeline configuration? This will restart the simulation."
          confirmLabel="Apply"
          cancelLabel="Cancel"
          onConfirm={handleConfirmApply}
          onCancel={() => setShowConfirm(false)}
        />
      )}

      {/* Restart overlay */}
      {isApplying && <RestartOverlay subsystem="slam" name="pipeline configuration" />}
    </div>
  );
}
