import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import StartupSpawnPicker from '../StartupSpawnPicker';
import WorkspaceHeader from '../WorkspaceHeader';
import { useControlStore } from '../../stores/controlStore';

vi.mock('three', async (original) => ({
  ...await original<typeof import('three')>(),
  WebGLRenderer: class { constructor() { throw new Error('No WebGL in test'); } },
}));
const setup = { scene: 'office', robot_ids: ['robot_a'], defaults: { robot_a: [2, 3] } };
beforeEach(() => {
  useControlStore.setState({ restartPickerOpen: false, connected: true });
  vi.stubGlobal('fetch', vi.fn(async (url: string, init?: RequestInit) => ({
    ok: true, json: async () => init?.method === 'POST' ? {} : url.endsWith('/restart') ? setup : { awaiting_selection: false },
  })));
});
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

it('opens the map from the header and cancels without restarting', async () => {
  render(<><WorkspaceHeader /><StartupSpawnPicker /></>);
  fireEvent.click(screen.getByRole('button', { name: 'Restart' }));
  await screen.findByText('Choose restart positions');
  expect((screen.getByRole('button', { name: 'Restart simulation' }) as HTMLButtonElement).disabled).toBe(true);
  fireEvent.click(screen.getByRole('button', { name: 'Cancel' }));
  await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull());
  expect(vi.mocked(fetch).mock.calls.some(([, init]) => init?.method === 'POST')).toBe(false);
});

it('submits restart positions only after confirmation', async () => {
  useControlStore.setState({ restartPickerOpen: true });
  render(<StartupSpawnPicker />);
  fireEvent.click(await screen.findByRole('button', { name: 'Use default positions' }));
  await waitFor(() => expect(fetch).toHaveBeenCalledWith('/api/spawn/restart', expect.objectContaining({
    method: 'POST', body: JSON.stringify({ positions: setup.defaults, scene: setup.scene }),
  })));
  await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull());
});

it('changes the selected scene before submitting startup positions', async () => {
  const scenes = [{ id: 'flat', name: 'Open floor', description: 'Test floor', source: 'Argus' }, { id: 'gym', name: 'Gym', description: 'Exercise equipment', source: 'mujoco-scene-editor' }];
  vi.stubGlobal('fetch', vi.fn(async (url: string, init?: RequestInit) => ({ ok: true, json: async () => init?.method === 'POST' ? {} : { ...setup, awaiting_selection: true, scene: url.includes('scene=gym') ? 'gym' : 'flat', scenes } })));
  render(<StartupSpawnPicker />);
  fireEvent.click(await screen.findByRole('button', { name: /Gym/ }));
  await waitFor(() => expect(screen.getByRole('button', { name: /Gym/ }).getAttribute('aria-pressed')).toBe('true'));
  fireEvent.click(screen.getByRole('button', { name: 'Use default positions' }));
  await waitFor(() => expect(fetch).toHaveBeenCalledWith('/api/spawn', expect.objectContaining({ method: 'POST', body: JSON.stringify({ positions: setup.defaults, scene: 'gym' }) })));
});
