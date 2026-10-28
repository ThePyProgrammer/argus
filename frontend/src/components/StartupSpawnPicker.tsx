import { useEffect, useRef, useState } from 'react';
import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { OKABE_ITO } from '../utils/palette';
import { useControlStore } from '../stores/controlStore';
import { useSimulationStore } from '../stores/simulationStore';
import { useRobotStore } from '../stores/robotStore';

type Point = [number, number];
interface SpawnSetup {
  awaiting_selection: boolean;
  scene: string;
  robot_ids: string[];
  defaults: Record<string, Point>;
}

export function SpawnMap({ sceneName, positions, robotIds, onPick }: {
  sceneName: string; positions: Record<string, Point>; robotIds: string[];
  onPick: (point: Point) => void;
}) {
  const container = useRef<HTMLDivElement>(null);
  const onPickRef = useRef(onPick);
  onPickRef.current = onPick;
  const markers = useRef<THREE.Group | null>(null);
  const redraw = useRef(() => {});
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!container.current) return;
    const host = container.current;
    let renderer: THREE.WebGLRenderer;
    try {
      renderer = new THREE.WebGLRenderer({ antialias: true });
    } catch {
      setError('Map rendering is unavailable. You can still use the default positions.');
      setLoading(false);
      return;
    }
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    host.appendChild(renderer.domElement);
    renderer.domElement.style.display = 'block';
    const scene = new THREE.Scene();
    scene.background = new THREE.Color('#101625');
    const camera = new THREE.OrthographicCamera(-10, 10, 10, -10, 0.1, 200);
    camera.up.set(0, 0, -1);
    camera.position.set(0, 40, 0);
    camera.lookAt(0, 0, 0);
    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableRotate = false;
    controls.enableDamping = false;
    controls.minZoom = 0.5;
    controls.maxZoom = 8;
    controls.mouseButtons.LEFT = null;
    const markerGroup = new THREE.Group();
    scene.add(markerGroup);
    markers.current = markerGroup;
    const selectable: THREE.Object3D[] = [];
    let cancelled = false;
    let span = 20;
    const render = () => renderer.render(scene, camera);
    redraw.current = render;
    const resize = () => {
      const width = host.clientWidth || 640;
      const height = host.clientHeight || 480;
      const aspect = width / height;
      camera.left = -span * aspect / 2;
      camera.right = span * aspect / 2;
      camera.top = span / 2;
      camera.bottom = -span / 2;
      camera.updateProjectionMatrix();
      renderer.setSize(width, height);
      render();
    };
    const fit = (object: THREE.Object3D) => {
      const bounds = new THREE.Box3().setFromObject(object);
      const center = bounds.getCenter(new THREE.Vector3());
      const size = bounds.getSize(new THREE.Vector3());
      const aspect = (host.clientWidth || 640) / (host.clientHeight || 480);
      span = Math.max(size.z, size.x / aspect, 5) * 1.15;
      camera.position.set(center.x, Math.max(bounds.max.y + 30, 40), center.z);
      controls.target.set(center.x, 0, center.z);
      controls.update();
      resize();
      setLoading(false);
    };
    if (sceneName === 'office') {
      new GLTFLoader().load('/scene.glb', (gltf) => {
        if (cancelled) return;
        gltf.scene.traverse((object) => {
          if (!(object instanceof THREE.Mesh)) return;
          if (/_convex_|ceiling/i.test(object.name)) {
            object.visible = false;
            return;
          }
          const floor = /Floor_002/i.test(object.name);
          object.userData.spawnFloor = floor;
          object.material = new THREE.MeshBasicMaterial({
            color: floor ? '#26354c' : /Walls/i.test(object.name) ? '#a2b2c9' : '#60738c',
            side: THREE.DoubleSide,
          });
          selectable.push(object);
        });
        scene.add(gltf.scene);
        fit(gltf.scene);
      }, undefined, () => {
        if (cancelled) return;
        setLoading(false);
        setError('Could not load the office map. Use default positions or reload to retry.');
      });
    } else {
      const floor = new THREE.Mesh(new THREE.PlaneGeometry(30, 30), new THREE.MeshBasicMaterial({ color: '#26354c', side: THREE.DoubleSide }));
      floor.rotation.x = -Math.PI / 2;
      floor.userData.spawnFloor = true;
      scene.add(floor);
      scene.add(new THREE.GridHelper(30, 30, '#60738c', '#36485e'));
      selectable.push(floor);
      fit(floor);
    }
    const click = (event: MouseEvent) => {
      const rect = renderer.domElement.getBoundingClientRect();
      const ray = new THREE.Raycaster();
      ray.setFromCamera(new THREE.Vector2(
        2 * (event.clientX - rect.left) / rect.width - 1,
        1 - 2 * (event.clientY - rect.top) / rect.height,
      ), camera);
      const hit = ray.intersectObjects(selectable, false)[0];
      if (!hit || !hit.object.userData.spawnFloor) {
        setError('Choose open floor, away from walls and furniture.');
        return;
      }
      setError('');
      // Viewer Y-up (x, z, -y) -> MuJoCo Z-up (x, y, z).
      onPickRef.current([Number(hit.point.x.toFixed(3)), Number((-hit.point.z).toFixed(3))]);
    };
    renderer.domElement.addEventListener('click', click);
    controls.addEventListener('change', render);
    const observer = new ResizeObserver(resize);
    observer.observe(host);
    resize();
    return () => {
      cancelled = true;
      observer.disconnect();
      controls.dispose();
      renderer.domElement.removeEventListener('click', click);
      scene.traverse((object) => {
        if (object instanceof THREE.Mesh || object instanceof THREE.LineSegments) {
          object.geometry.dispose();
          const materials = Array.isArray(object.material) ? object.material : [object.material];
          materials.forEach((material) => material.dispose());
        }
      });
      renderer.dispose();
      renderer.domElement.remove();
      markers.current = null;
      redraw.current = () => {};
    };
  }, [sceneName]);

  useEffect(() => {
    const group = markers.current;
    if (!group) return;
    for (const child of [...group.children]) {
      if (child instanceof THREE.Mesh) {
        child.geometry.dispose();
        (child.material as THREE.Material).dispose();
      }
      group.remove(child);
    }
    robotIds.forEach((id, index) => {
      const point = positions[id];
      if (!point) return;
      const marker = new THREE.Mesh(new THREE.CircleGeometry(0.3, 32), new THREE.MeshBasicMaterial({
        color: OKABE_ITO[index % 8], depthTest: false,
      }));
      marker.rotation.x = -Math.PI / 2;
      marker.position.set(point[0], 10, -point[1]);
      marker.renderOrder = 10;
      group.add(marker);
    });
    redraw.current();
  }, [positions, robotIds]);

  return <div style={{ position: 'relative', minHeight: 300, height: 'min(60vh, 620px)' }}>
    <div ref={container} style={{ position: 'absolute', inset: 0, cursor: 'crosshair' }} />
    {(loading || error) && <div className="spawn-map-status" role="status" style={{ position: 'absolute', bottom: 12, left: 12, right: 12, background: '#101625dd', padding: 10, pointerEvents: 'none' }}>{error || 'Loading overhead map…'}</div>}
  </div>;
}

export default function StartupSpawnPicker() {
  const restarting = useControlStore((s) => s.restartPickerOpen);
  const setRestartPickerOpen = useControlStore((s) => s.setRestartPickerOpen);
  const [setup, setSetup] = useState<SpawnSetup | null>(null);
  const [positions, setPositions] = useState<Record<string, Point>>({});
  const [active, setActive] = useState('');
  const [pending, setPending] = useState(false);
  const [error, setError] = useState('');
  useEffect(() => {
    const controller = new AbortController();
    setSetup(null);
    setPositions({});
    setError('');
    fetch(restarting ? '/api/spawn/restart' : '/api/spawn', { signal: controller.signal }).then(async (response) => {
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || 'Could not load spawn selection');
      return data;
    }).then((data) => {
      if (controller.signal.aborted) return;
      if (data?.awaiting_selection || restarting) {
        setSetup(data);
        setActive(data.robot_ids[0]);
      }
    }).catch((err) => {
      if (!controller.signal.aborted && restarting) setError(err instanceof Error ? err.message : 'Could not load spawn selection');
    });
    return () => controller.abort();
  }, [restarting]);
  if (!setup) return restarting ? <div className="spawn-picker" role="dialog" aria-modal="true" aria-label="Restart placement" style={{ position: 'fixed', inset: 0, zIndex: 1000, display: 'grid', placeItems: 'center' }}>
    <section style={{ padding: 20 }}><p role="status">{error || 'Loading spawn selection...'}</p><button onClick={() => setRestartPickerOpen(false)}>Cancel</button></section>
  </div> : null;
  const pick = (point: Point) => {
    if (pending) return;
    const next = { ...positions, [active]: point };
    setPositions(next);
    const remaining = setup.robot_ids.find((id) => !next[id]);
    if (remaining) setActive(remaining);
  };
  const confirm = async (chosen: Record<string, Point>) => {
    setPending(true);
    setError('');
    try {
      const response = await fetch(restarting ? '/api/spawn/restart' : '/api/spawn', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ positions: chosen }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'Could not confirm spawn positions');
      if (data.status) useSimulationStore.getState().apply(data.status);
      if (restarting) {
        useRobotStore.getState().setCloudFull([], []);
        useControlStore.getState().setRunning(true);
        useControlStore.getState().setPaused(false);
        setRestartPickerOpen(false);
      }
      setSetup(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not start simulation');
    } finally {
      setPending(false);
    }
  };
  return <div className="spawn-picker" role="dialog" aria-modal="true" aria-labelledby="spawn-title" style={{ position: 'fixed', inset: 0, zIndex: 1000, background: '#050914e8', display: 'grid', placeItems: 'center', padding: 20, color: 'var(--ink)' }}>
    <section style={{ width: 'min(1050px, 96vw)', background: 'var(--surface-raised)', border: '1px solid var(--line)', borderRadius: 12, overflow: 'hidden' }}>
      <header style={{ padding: '18px 22px' }}>
        <h2 id="spawn-title" style={{ margin: '0 0 8px' }}>{restarting ? 'Choose restart positions' : 'Choose starting positions'}</h2>
        <p style={{ margin: 0, color: 'var(--muted)' }}>Select a robot, then click open floor on the overhead map. Scroll to zoom; right-drag to pan. MuJoCo starts after you confirm.</p>
      </header>
      <div style={{ display: 'flex', gap: 8, padding: '0 22px 14px', flexWrap: 'wrap' }}>
        {setup.robot_ids.map((id, index) => <button key={id} disabled={pending} onClick={() => setActive(id)} aria-pressed={active === id} style={{ padding: '8px 12px', background: active === id ? 'var(--accent-wash)' : 'var(--surface-inset)', color: OKABE_ITO[index % 8], border: '1px solid var(--line-strong)', borderRadius: 6 }}>
          {id}: {positions[id] ? `(${positions[id][0].toFixed(2)}, ${positions[id][1].toFixed(2)})` : 'click to place'}
        </button>)}
      </div>
      <SpawnMap sceneName={setup.scene} positions={positions} robotIds={setup.robot_ids} onPick={pick} />
      <footer style={{ padding: '14px 22px', display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
        <span role="alert" style={{ color: '#ffa89b', flex: 1 }}>{error}</span>
        {restarting && <button disabled={pending} onClick={() => { setSetup(null); setRestartPickerOpen(false); }}>Cancel</button>}
        <button disabled={pending} onClick={() => confirm(setup.defaults)}>Use default positions</button>
        <button disabled={pending || setup.robot_ids.some((id) => !positions[id])} onClick={() => confirm(positions)} style={{ background: 'var(--button-primary)', color: 'white', border: 0, padding: '10px 18px', borderRadius: 6 }}>{pending ? 'Starting...' : restarting ? 'Restart simulation' : 'Start simulation'}</button>
      </footer>
    </section>
  </div>;
}
