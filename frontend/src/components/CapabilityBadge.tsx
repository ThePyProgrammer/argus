interface CapabilityBadgeProps {
  label: string;
  value: string | number | boolean;
}

export function CapabilityBadge({ label, value }: CapabilityBadgeProps) {
  // D-04 rule: skip negative/empty values — truth-in-advertising.
  if (value === false || value === null || value === undefined) return null;

  // Rendering rules (D-04):
  //   boolean true   → label-only pill (preserves SLAM styling)
  //   number + 'latency' in label → "~{value}ms"
  //   other → "{label}: {value}"
  let text: string;
  if (value === true) {
    text = label
      .replace('supports_', '')
      .replace('outputs_', '')
      .replace(/_/g, ' ');
  } else if (typeof value === 'number' && label.includes('latency')) {
    text = `~${value}ms`;
  } else {
    text = `${label.replace(/_/g, ' ')}: ${value}`;
  }

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

  return <span style={style}>{text}</span>;
}
