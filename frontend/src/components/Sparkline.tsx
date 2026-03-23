interface SparklineProps {
  data: number[];
  width?: number;
  height?: number;
  color?: string;
  baselineValue?: number;
  baselineColor?: string;
}

export default function Sparkline({
  data,
  width = 120,
  height = 30,
  color = '#2ecc71',
  baselineValue,
  baselineColor = '#555',
}: SparklineProps) {
  if (data.length < 2) return null;

  const min = Math.min(...data);
  const max = Math.max(...data);
  const range = max - min || 1;

  const points = data
    .map((v, i) => {
      const x = i * (width / (data.length - 1));
      const y = height - ((v - min) / range) * height;
      return `${x},${y}`;
    })
    .join(' ');

  const showBaseline =
    baselineValue !== undefined && baselineValue >= min && baselineValue <= max;
  const baseY = showBaseline
    ? height - ((baselineValue! - min) / range) * height
    : 0;

  return (
    <svg width={width} height={height} style={{ display: 'block' }}>
      {showBaseline && (
        <line
          x1={0}
          y1={baseY}
          x2={width}
          y2={baseY}
          stroke={baselineColor}
          strokeWidth={1}
          strokeDasharray="3,2"
        />
      )}
      <polyline fill="none" stroke={color} strokeWidth={1.5} points={points} />
    </svg>
  );
}
