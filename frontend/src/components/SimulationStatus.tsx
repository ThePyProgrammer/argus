import { useEffect, useState } from 'react';
import { useSimulationStore } from '../stores/simulationStore';

export default function SimulationStatus() {
  const status = useSimulationStore((s) => s.status);
  const [unavailable, setUnavailable] = useState(false);
  useEffect(() => {
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout>;
    const controller = new AbortController();
    const poll = async () => {
      try {
        const response = await fetch('/api/spawn/status', { signal: controller.signal });
        if (!response.ok) throw new Error('Status unavailable');
        const data = await response.json();
        if (!cancelled) { useSimulationStore.getState().apply(data); setUnavailable(false); }
      } catch { if (!cancelled) setUnavailable(true); }
      finally { if (!cancelled) timer = setTimeout(poll, 1000); }
    };
    void poll();
    return () => { cancelled = true; controller.abort(); clearTimeout(timer); };
  }, []);
  if (!unavailable && !['loading', 'error', 'stopped'].includes(status.phase)) return null;
  const loading = status.phase === 'loading' && !unavailable;
  return <div className="simulation-status" role={loading ? 'status' : 'alert'} aria-live="polite">
    <span className={loading ? 'simulation-spinner' : 'simulation-warning'} aria-hidden="true">{loading ? '' : '!'}</span>
    <div><strong>{unavailable ? 'Simulation connection unavailable' : loading ? 'Starting simulation' : status.phase === 'error' ? 'Simulation could not start' : 'Simulation stopped'}</strong>
      <p>{unavailable ? 'Waiting for the server to reconnect.' : status.message}</p>
      {loading && <p>Robots show their starting poses. Motion begins when MuJoCo is ready.</p>}
    </div>
  </div>;
}
