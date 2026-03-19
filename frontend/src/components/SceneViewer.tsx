import { useEffect, useRef, useState } from 'react';
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { PointCloudManager } from './PointCloud';
import { RobotMarkerManager } from './RobotMarker';
import { TrajectoryTrailManager } from './TrajectoryTrail';
import { useRobotStore } from '../stores/robotStore';
import { useControlStore } from '../stores/controlStore';
import { useSceneLoader } from '../hooks/useSceneLoader';

/**
 * Three.js scene viewer -- the hero 3D view.
 *
 * Mounts a WebGL canvas into its container div and manages the full
 * scene lifecycle: camera, lights, orbit controls, grid, and the three
 * imperative managers (point cloud, robot markers, trajectory trails).
 *
 * Store updates drive the scene imperatively via Zustand.subscribe()
 * to avoid React re-render overhead.
 */
export default function SceneViewer() {
  const containerRef = useRef<HTMLDivElement>(null);
  const worldRootRef = useRef<THREE.Group | null>(null);
  const sceneObjRef = useRef<THREE.Scene | null>(null);
  const [sceneReady, setSceneReady] = useState(false);

  // GLB scene loaded into raw scene (OBJ meshes are Y-up, no rotation needed)
  useSceneLoader(sceneReady ? sceneObjRef.current : null);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    // --- Renderer ---
    const renderer = new THREE.WebGLRenderer({ antialias: true });
    renderer.setPixelRatio(window.devicePixelRatio);
    renderer.setSize(container.clientWidth, container.clientHeight);
    container.appendChild(renderer.domElement);

    // --- Scene ---
    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x0d0d1a);

    // --- Z-up to Y-up conversion ---
    // MuJoCo uses Z-up; Three.js uses Y-up. Rotate the world root
    // by -90° around X so all data (point cloud, markers, GLB) renders correctly.
    const worldRoot = new THREE.Group();
    worldRoot.rotation.x = -Math.PI / 2;
    scene.add(worldRoot);
    worldRootRef.current = worldRoot;
    sceneObjRef.current = scene;
    setSceneReady(true);

    // --- Camera ---
    const aspect = container.clientWidth / container.clientHeight;
    const camera = new THREE.PerspectiveCamera(60, aspect, 0.1, 1000);
    camera.position.set(0, 10, 10);
    camera.lookAt(0, 0, 0);

    // --- Lights ---
    const ambient = new THREE.AmbientLight(0xffffff, 0.4);
    scene.add(ambient);
    const directional = new THREE.DirectionalLight(0xffffff, 0.8);
    directional.position.set(10, 20, 15);
    scene.add(directional);

    // --- Grid helper ---
    const grid = new THREE.GridHelper(50, 50, 0x444466, 0x222244);
    scene.add(grid);

    // --- OrbitControls ---
    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.1;
    controls.minDistance = 1;
    controls.maxDistance = 50;
    controls.target.set(0, 0, 0);

    // --- Managers (added to worldRoot so Z-up rotation applies) ---
    const pointCloudManager = new PointCloudManager(worldRoot);
    const robotMarkerManager = new RobotMarkerManager(worldRoot);
    const trailManager = new TrajectoryTrailManager(worldRoot);

    // --- Cloud offset subscription ---
    const unsubControl = useControlStore.subscribe((state, prev) => {
      if (state.cloudOffset !== prev.cloudOffset) {
        const [ox, oy, oz] = state.cloudOffset;
        pointCloudManager.setOffset(ox, oy, oz);
      }
    });

    // --- Zustand subscription (imperative, no React re-renders) ---
    const unsub = useRobotStore.subscribe((state, prevState) => {
      // Point cloud update
      if (
        state.pointCloudPositions !== prevState.pointCloudPositions ||
        state.colorMode !== prevState.colorMode
      ) {
        pointCloudManager.updateFull(
          state.pointCloudPositions,
          state.pointCloudColors,
        );
      }

      // Robot markers and trails
      for (const [id, robot] of state.robots) {
        const prev = prevState.robots.get(id);
        if (!prev || prev.position !== robot.position) {
          robotMarkerManager.updateRobot(id, robot.position, robot.colorIndex);
        }
        if (!prev || prev.trajectory !== robot.trajectory) {
          trailManager.updateTrail(
            id,
            robot.trajectory,
            robot.trajectoryAlphas,
            robot.colorIndex,
          );
        }
      }
    });

    // --- Center-on-robot custom event ---
    const handleCenterOnRobot = (e: Event) => {
      const robotId = (e as CustomEvent<string>).detail;
      const pos = robotMarkerManager.centerOnRobot(robotId);
      if (pos) {
        controls.target.set(pos[0], pos[1], pos[2]);
        controls.update();
      }
    };
    window.addEventListener('focus-robot', handleCenterOnRobot);

    // --- Render loop ---
    let animationId = 0;
    const animate = () => {
      animationId = requestAnimationFrame(animate);
      controls.update();
      renderer.render(scene, camera);
    };
    animate();

    // --- Resize handler ---
    const handleResize = () => {
      if (!container) return;
      const w = container.clientWidth;
      const h = container.clientHeight;
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
      renderer.setSize(w, h);
    };
    window.addEventListener('resize', handleResize);

    // Also observe container size changes (e.g. sidebar collapse)
    const resizeObserver = new ResizeObserver(handleResize);
    resizeObserver.observe(container);

    // --- Cleanup ---
    return () => {
      cancelAnimationFrame(animationId);
      unsub();
      unsubControl();
      window.removeEventListener('focus-robot', handleCenterOnRobot);
      window.removeEventListener('resize', handleResize);
      resizeObserver.disconnect();
      controls.dispose();
      pointCloudManager.dispose();
      robotMarkerManager.dispose();
      trailManager.dispose();
      renderer.dispose();
      if (container.contains(renderer.domElement)) {
        container.removeChild(renderer.domElement);
      }
    };
  }, []);

  return (
    <div
      ref={containerRef}
      style={{ width: '100%', height: '100%', overflow: 'hidden' }}
    />
  );
}
