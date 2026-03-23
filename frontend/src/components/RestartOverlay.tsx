export function RestartOverlay({ algorithmName }: { algorithmName: string }) {
  const overlayStyle: React.CSSProperties = {
    position: 'absolute',
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    justifyContent: 'center',
    background: 'rgba(13, 13, 26, 0.7)',
    zIndex: 10,
    pointerEvents: 'none',
  };

  const spinnerStyle: React.CSSProperties = {
    width: '40px',
    height: '40px',
    border: '3px solid #2a2a4a',
    borderTopColor: '#2ecc71',
    borderRadius: '50%',
    animation: 'spin 1s linear infinite',
  };

  const textStyle: React.CSSProperties = {
    marginTop: '16px',
    color: '#aaa',
    fontSize: '13px',
  };

  return (
    <div style={overlayStyle}>
      <div style={spinnerStyle} />
      <div style={textStyle}>Restarting with {algorithmName}...</div>
    </div>
  );
}
