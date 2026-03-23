import { useEffect } from 'react';
import { createPortal } from 'react-dom';

interface ConfirmModalProps {
  heading: string;
  body: string;
  confirmLabel: string;
  cancelLabel: string;
  onConfirm: () => void;
  onCancel: () => void;
  confirmDisabled?: boolean;
  confirmText?: string;
}

export function ConfirmModal(props: ConfirmModalProps) {
  const {
    heading,
    body,
    confirmLabel,
    cancelLabel,
    onConfirm,
    onCancel,
    confirmDisabled,
    confirmText,
  } = props;

  useEffect(() => {
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onCancel();
    };
    document.addEventListener('keydown', handleKey);
    return () => document.removeEventListener('keydown', handleKey);
  }, [onCancel]);

  const backdropStyle: React.CSSProperties = {
    position: 'fixed',
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    background: 'rgba(0, 0, 0, 0.6)',
    zIndex: 1000,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
  };

  const cardStyle: React.CSSProperties = {
    background: '#1a1a3e',
    border: '1px solid #2a2a4a',
    borderRadius: '8px',
    padding: '24px',
    maxWidth: '400px',
    width: '90%',
    boxShadow: '0 8px 32px rgba(0, 0, 0, 0.5)',
  };

  const headingStyle: React.CSSProperties = {
    fontSize: '16px',
    fontWeight: 600,
    color: '#e0e0e0',
    margin: 0,
  };

  const bodyStyle: React.CSSProperties = {
    fontSize: '13px',
    color: '#aaa',
    marginTop: '16px',
  };

  const buttonRowStyle: React.CSSProperties = {
    display: 'flex',
    gap: '8px',
    marginTop: '20px',
    justifyContent: 'flex-end',
  };

  const cancelButtonStyle: React.CSSProperties = {
    background: '#1565c0',
    color: '#fff',
    padding: '8px 16px',
    border: 'none',
    borderRadius: '4px',
    fontSize: '13px',
    fontWeight: 600,
    cursor: 'pointer',
  };

  const confirmButtonStyle: React.CSSProperties = {
    background: '#2ecc71',
    color: '#fff',
    padding: '8px 16px',
    border: 'none',
    borderRadius: '4px',
    fontSize: '13px',
    fontWeight: 600,
    cursor: 'pointer',
    ...(confirmDisabled ? { pointerEvents: 'none' as const, opacity: 0.6 } : {}),
  };

  return createPortal(
    <div style={backdropStyle} onClick={onCancel}>
      <div style={cardStyle} onClick={(e) => e.stopPropagation()}>
        <h3 style={headingStyle}>{heading}</h3>
        <p style={bodyStyle}>{body}</p>
        <div style={buttonRowStyle}>
          <button style={cancelButtonStyle} onClick={onCancel}>
            {cancelLabel}
          </button>
          <button style={confirmButtonStyle} onClick={onConfirm}>
            {confirmText ?? confirmLabel}
          </button>
        </div>
      </div>
    </div>,
    document.body,
  );
}
