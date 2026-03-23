export function CapabilityBadge({ name }: { name: string }) {
  const label = name
    .replace('supports_', '')
    .replace('outputs_', '')
    .replace(/_/g, ' ');

  const style: React.CSSProperties = {
    display: 'inline-block',
    padding: '1px 8px',
    borderRadius: '8px',
    fontSize: '10px',
    fontWeight: 400,
    background: 'rgba(46, 204, 113, 0.15)',
    color: '#2ecc71',
    border: '1px solid rgba(46, 204, 113, 0.3)',
    marginRight: '4px',
    marginBottom: '2px',
  };

  return <span style={style}>{label}</span>;
}
