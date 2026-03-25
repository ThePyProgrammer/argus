import { useRef, useEffect, useCallback } from 'react';
import { useRobotStore } from '../stores/robotStore';
import { OKABE_ITO } from '../utils/palette';

const MAP_WIDTH = 220;
const MAP_HEIGHT = 180;
const PADDING = 12;

// World bounds — auto-fit to robot positions + margin
function computeViewBounds(
  robots: Map<string, { position: [number, number, number]; trajectory: number[][] }>,
) {
  let minX = -2, maxX = 12, minY = -6, maxY = 6; // default bounds

  robots.forEach((robot) => {
    const [x, , z] = robot.position; // MuJoCo: x is forward, y is left, z is up → top-down uses x, y
    minX = Math.min(minX, x - 2);
    maxX = Math.max(maxX, x + 2);
    minY = Math.min(minY, z - 2); // use y-axis for lateral
    maxY = Math.max(maxY, z + 2);

    // Expand to include trajectory
    for (const pt of robot.trajectory) {
      minX = Math.min(minX, pt[0] - 1);
      maxX = Math.max(maxX, pt[0] + 1);
      minY = Math.min(minY, pt[1] - 1);
      maxY = Math.max(maxY, pt[1] + 1);
    }
  });

  // Add padding and ensure aspect ratio
  const rangeX = maxX - minX || 1;
  const rangeY = maxY - minY || 1;
  const aspect = (MAP_WIDTH - PADDING * 2) / (MAP_HEIGHT - PADDING * 2);
  if (rangeX / rangeY > aspect) {
    const mid = (minY + maxY) / 2;
    const half = (rangeX / aspect) / 2;
    minY = mid - half;
    maxY = mid + half;
  } else {
    const mid = (minX + maxX) / 2;
    const half = (rangeY * aspect) / 2;
    minX = mid - half;
    maxX = mid + half;
  }

  return { minX, maxX, minY, maxY };
}

export function Minimap2D() {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const animFrameRef = useRef<number>(0);

  const draw = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const robots = useRobotStore.getState().robots;
    const bounds = computeViewBounds(robots);

    const drawX = MAP_WIDTH - PADDING * 2;
    const drawY = MAP_HEIGHT - PADDING * 2;

    function worldToScreen(wx: number, wy: number): [number, number] {
      const sx = PADDING + ((wx - bounds.minX) / (bounds.maxX - bounds.minX)) * drawX;
      const sy = PADDING + ((1 - (wy - bounds.minY) / (bounds.maxY - bounds.minY))) * drawY;
      return [sx, sy];
    }

    // Clear
    ctx.clearRect(0, 0, MAP_WIDTH, MAP_HEIGHT);

    // Background
    ctx.fillStyle = '#12122a';
    ctx.beginPath();
    ctx.roundRect(0, 0, MAP_WIDTH, MAP_HEIGHT, 8);
    ctx.fill();

    // Grid lines
    ctx.strokeStyle = 'rgba(255, 255, 255, 0.05)';
    ctx.lineWidth = 0.5;
    const gridStep = 2; // 2m grid
    for (let x = Math.ceil(bounds.minX / gridStep) * gridStep; x <= bounds.maxX; x += gridStep) {
      const [sx] = worldToScreen(x, 0);
      ctx.beginPath();
      ctx.moveTo(sx, PADDING);
      ctx.lineTo(sx, MAP_HEIGHT - PADDING);
      ctx.stroke();
    }
    for (let y = Math.ceil(bounds.minY / gridStep) * gridStep; y <= bounds.maxY; y += gridStep) {
      const [, sy] = worldToScreen(0, y);
      ctx.beginPath();
      ctx.moveTo(PADDING, sy);
      ctx.lineTo(MAP_WIDTH - PADDING, sy);
      ctx.stroke();
    }

    // Origin crosshair
    const [ox, oy] = worldToScreen(0, 0);
    ctx.strokeStyle = 'rgba(255, 255, 255, 0.15)';
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(ox - 4, oy);
    ctx.lineTo(ox + 4, oy);
    ctx.moveTo(ox, oy - 4);
    ctx.lineTo(ox, oy + 4);
    ctx.stroke();

    // Draw each robot
    robots.forEach((robot) => {
      const color = OKABE_ITO[robot.colorIndex % 8];
      const [x, y] = robot.position; // MuJoCo world: x, y horizontal plane

      // Trajectory trail
      if (robot.trajectory.length > 1) {
        ctx.strokeStyle = color;
        ctx.globalAlpha = 0.3;
        ctx.lineWidth = 1.5;
        ctx.beginPath();
        const [tx0, ty0] = worldToScreen(robot.trajectory[0][0], robot.trajectory[0][1]);
        ctx.moveTo(tx0, ty0);
        for (let i = 1; i < robot.trajectory.length; i++) {
          const [tx, ty] = worldToScreen(robot.trajectory[i][0], robot.trajectory[i][1]);
          ctx.lineTo(tx, ty);
        }
        ctx.stroke();
        ctx.globalAlpha = 1;
      }

      // Robot dot
      const [sx, sy] = worldToScreen(x, y);
      ctx.fillStyle = color;
      ctx.beginPath();
      ctx.arc(sx, sy, 5, 0, Math.PI * 2);
      ctx.fill();

      // White outline
      ctx.strokeStyle = '#fff';
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.arc(sx, sy, 5, 0, Math.PI * 2);
      ctx.stroke();

      // Heading indicator (triangle pointing in bodyYaw direction)
      const yaw = robot.bodyYaw;
      const headLen = 10;
      const hx = sx + Math.cos(yaw) * headLen;
      const hy = sy - Math.sin(yaw) * headLen; // canvas y is inverted
      ctx.strokeStyle = color;
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.moveTo(sx, sy);
      ctx.lineTo(hx, hy);
      ctx.stroke();

      // Small arrowhead
      const arrowSize = 4;
      const angle = Math.atan2(-(hy - sy), hx - sx);
      ctx.fillStyle = color;
      ctx.beginPath();
      ctx.moveTo(hx, hy);
      ctx.lineTo(
        hx - arrowSize * Math.cos(angle - 0.5),
        hy + arrowSize * Math.sin(angle - 0.5),
      );
      ctx.lineTo(
        hx - arrowSize * Math.cos(angle + 0.5),
        hy + arrowSize * Math.sin(angle + 0.5),
      );
      ctx.closePath();
      ctx.fill();

      // Label
      ctx.fillStyle = '#ccc';
      ctx.font = '10px monospace';
      ctx.textAlign = 'center';
      ctx.fillText(robot.id.replace('robot_', 'R'), sx, sy - 9);
    });

    // Scale indicator
    const scaleMeters = 2;
    const [s0] = worldToScreen(0, 0);
    const [s1] = worldToScreen(scaleMeters, 0);
    const scaleLen = Math.abs(s1 - s0);
    const scaleY = MAP_HEIGHT - 6;
    ctx.strokeStyle = 'rgba(255, 255, 255, 0.4)';
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(PADDING, scaleY);
    ctx.lineTo(PADDING + scaleLen, scaleY);
    ctx.stroke();
    // End ticks
    ctx.beginPath();
    ctx.moveTo(PADDING, scaleY - 3);
    ctx.lineTo(PADDING, scaleY + 3);
    ctx.moveTo(PADDING + scaleLen, scaleY - 3);
    ctx.lineTo(PADDING + scaleLen, scaleY + 3);
    ctx.stroke();
    ctx.fillStyle = 'rgba(255, 255, 255, 0.4)';
    ctx.font = '9px monospace';
    ctx.textAlign = 'center';
    ctx.fillText(`${scaleMeters}m`, PADDING + scaleLen / 2, scaleY - 4);

    animFrameRef.current = requestAnimationFrame(draw);
  }, []);

  useEffect(() => {
    animFrameRef.current = requestAnimationFrame(draw);
    return () => cancelAnimationFrame(animFrameRef.current);
  }, [draw]);

  const containerStyle: React.CSSProperties = {
    position: 'absolute',
    bottom: 16,
    right: 16,
    width: MAP_WIDTH,
    height: MAP_HEIGHT,
    zIndex: 20,
    border: '1px solid rgba(255, 255, 255, 0.1)',
    borderRadius: 8,
    boxShadow: '0 4px 16px rgba(0, 0, 0, 0.5)',
    overflow: 'hidden',
    pointerEvents: 'none',
  };

  return (
    <div style={containerStyle}>
      <canvas
        ref={canvasRef}
        width={MAP_WIDTH}
        height={MAP_HEIGHT}
        style={{ width: MAP_WIDTH, height: MAP_HEIGHT }}
      />
    </div>
  );
}
