import { act, cleanup, render, screen, waitFor } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import SimulationStatus from '../SimulationStatus';
import { useSimulationStore } from '../../stores/simulationStore';
import { useRobotStore } from '../../stores/robotStore';
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
const loading = { phase: 'loading', message: 'Starting MuJoCo', positions: { robot_a: [1, 2, .3] as [number, number, number], robot_b: [3, 4, .3] as [number, number, number] }, headings: { robot_a: 0, robot_b: Math.PI } };
it('previews confirmed poses and clears the warning only on server readiness', async () => {
  useSimulationStore.setState({ status: { phase: 'idle', message: '' } });
  vi.stubGlobal('fetch', vi.fn(async () => ({ ok: true, json: async () => loading })));
  render(<SimulationStatus />);
  await screen.findByText('Starting MuJoCo');
  expect(useRobotStore.getState().robots.get('robot_b')?.position).toEqual([3, 4, .3]);
  expect(useRobotStore.getState().robots.get('robot_b')?.bodyYaw).toBe(Math.PI);
  act(() => useSimulationStore.getState().apply({ ...loading, phase: 'ready' }));
  await waitFor(() => expect(screen.queryByRole('status')).toBeNull());
});
it('shows initialization failures instead of an endless loading spinner', async () => {
  vi.stubGlobal('fetch', vi.fn(async () => ({ ok: true, json: async () => ({ phase: 'error', message: 'Camera initialization failed' }) })));
  render(<SimulationStatus />);
  expect(await screen.findByRole('alert')).toBeTruthy();
  await screen.findByText('Camera initialization failed');
});
