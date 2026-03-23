import { useEffect, useRef } from 'react';
import { createPortal } from 'react-dom';
import { useSlamStore } from '../stores/slamStore';

/**
 * Dismissible toast notification that shows when a subprocess SLAM
 * backend crashes and falls back to ICP. Uses portal pattern (same
 * as ConfirmModal) for z-index stacking.
 *
 * Auto-dismisses after 8 seconds. Reads crashMessage from slamStore;
 * renders nothing when crashMessage is null.
 */
export function CrashToast() {
  const crashMessage = useSlamStore((s) => s.crashMessage);
  const clearCrashMessage = useSlamStore((s) => s.clearCrashMessage);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (crashMessage) {
      timerRef.current = setTimeout(() => {
        clearCrashMessage();
      }, 8000);
    }
    return () => {
      if (timerRef.current) {
        clearTimeout(timerRef.current);
      }
    };
  }, [crashMessage, clearCrashMessage]);

  if (!crashMessage) return null;

  const toastStyle: React.CSSProperties = {
    position: 'fixed',
    bottom: '24px',
    right: '24px',
    background: 'rgba(180, 40, 20, 0.95)',
    color: '#fff',
    padding: '14px 20px',
    borderRadius: '8px',
    fontSize: '14px',
    fontWeight: 600,
    border: '1px solid #e65100',
    boxShadow: '0 4px 16px rgba(0, 0, 0, 0.4)',
    zIndex: 50,
    display: 'flex',
    alignItems: 'center',
    gap: '12px',
    maxWidth: '400px',
  };

  const closeButtonStyle: React.CSSProperties = {
    background: 'transparent',
    border: 'none',
    color: '#fff',
    fontSize: '18px',
    cursor: 'pointer',
    padding: '0 4px',
    lineHeight: 1,
    opacity: 0.8,
  };

  return createPortal(
    <div style={toastStyle} role="alert">
      <span style={{ flex: 1 }}>{crashMessage}</span>
      <button
        style={closeButtonStyle}
        onClick={clearCrashMessage}
        aria-label="Dismiss notification"
      >
        x
      </button>
    </div>,
    document.body,
  );
}
