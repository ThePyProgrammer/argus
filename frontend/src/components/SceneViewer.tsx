import { useEffect, useRef, useState } from 'react';
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { PointCloudManager } from './PointCloud';
import { VoxelManager } from './VoxelManager';
import { MeshManager } from './MeshManager';
import { RobotMarkerManager } from './RobotMarker';
import { TrajectoryTrailManager } from './TrajectoryTrail';
import { DetectionBoxManager } from './DetectionBoxes';
import { CameraFrustumManager } from './CameraFrustum';
import { useRobotStore } from '../stores/robotStore';
import { useControlStore } from '../stores/controlStore';
import { useSlamStore } from '../stores/slamStore';
import { useDetectorStore } from '../stores/detectorStore';
import { useMetricsStore } from '../stores/metricsStore';
import { RestartOverlay } from './RestartOverlay';
import { CrashToast } from './CrashToast';
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
    const isColoredInit = useControlStore.getState().sceneColored;
    scene.background = new THREE.Color(isColoredInit ? 0xffffff : 0x0d0d1a);

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

    // Adjust background when toggling colored/grey scene
    const unsubSceneColor = useControlStore.subscribe((state, prev) => {
      if (state.sceneColored !== prev.sceneColored) {
        scene.background = new THREE.Color(state.sceneColored ? 0xffffff : 0x0d0d1a);
      }
    });

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
    const voxelManager = new VoxelManager(worldRoot, 0.1);
    const meshManager = new MeshManager(worldRoot);
    const robotMarkerManager = new RobotMarkerManager(worldRoot);
    const trailManager = new TrajectoryTrailManager(worldRoot);
    const detectionBoxManager = new DetectionBoxManager(worldRoot);
    const cameraFrustumManager = new CameraFrustumManager(worldRoot);

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
        // Also update voxel manager with same data (voxels use same positions/colors)
        voxelManager.updateFull(
          state.pointCloudPositions,
          state.pointCloudColors,
        );
      }

      // Robot markers and trails
      for (const [id, robot] of state.robots) {
        const prev = prevState.robots.get(id);
        if (!prev || prev.position !== robot.position || prev.rotation !== robot.rotation || prev.trackingStatus !== robot.trackingStatus || prev.bodyYaw !== robot.bodyYaw) {
          robotMarkerManager.updateRobot(id, robot.position, robot.colorIndex, robot.rotation, robot.trackingStatus, robot.bodyYaw);
        }
        if (!prev || prev.trajectory !== robot.trajectory) {
          trailManager.updateTrail(
            id,
            robot.trajectory,
            robot.trajectoryAlphas,
            robot.colorIndex,
          );
        }
        // Camera frustum visualization
        if (!prev || prev.position !== robot.position || prev.rotation !== robot.rotation) {
          if (robot.rotation.length === 9) {
            cameraFrustumManager.updateFrustum(
              id, robot.position, robot.rotation, robot.colorIndex,
            );
          }
        }
        // 3D detection bounding boxes (Phase 2: detections_3d envelope)
        if (!prev || prev.detections_3d !== robot.detections_3d) {
          detectionBoxManager.updateDetections(
            id,
            robot.detections_3d,
            robot.colorIndex,
          );
        }
      }
    });

    // --- Cross-fade state ---
    let fadeOutManager: { getMaterial(): THREE.Material; setVisible(v: boolean): void } | null = null;
    let fadeInManager: { getMaterial(): THREE.Material; setVisible(v: boolean): void } | null = null;
    let isFading = false;
    let fadeStartTime = 0;
    const FADE_DURATION = 300; // ms

    const getManager = (mode: 'cloud' | 'voxel' | 'mesh') => {
      switch (mode) {
        case 'cloud': return { getMaterial: () => pointCloudManager.getMaterial() as THREE.Material, setVisible: (v: boolean) => pointCloudManager.setVisible(v) };
        case 'voxel': return { getMaterial: () => voxelManager.getMaterial() as THREE.Material, setVisible: (v: boolean) => voxelManager.setVisible(v) };
        case 'mesh': return { getMaterial: () => meshManager.getMaterial() as THREE.Material, setVisible: (v: boolean) => meshManager.setVisible(v) };
      }
    };

    let currentMode = useMetricsStore.getState().outputMode;
    const initialHidden = useMetricsStore.getState().outputHidden;
    if (!initialHidden) {
      const initialManager = getManager(currentMode);
      initialManager.setVisible(true);
    }

    const unsubMetrics = useMetricsStore.subscribe((state, prev) => {
      // Output mode change -> start cross-fade (skip if output is hidden)
      if (state.outputMode !== prev.outputMode && !state.outputHidden) {
        const oldMode = currentMode;
        const newMode = state.outputMode;
        currentMode = newMode;

        // Cancel any in-progress fade
        if (isFading && fadeOutManager) {
          const mat = fadeOutManager.getMaterial();
          mat.opacity = 0;
          (mat as any).transparent = false;
          (mat as any).depthWrite = true;
          fadeOutManager.setVisible(false);
        }

        fadeOutManager = getManager(oldMode);
        fadeInManager = getManager(newMode);

        // Prepare fade-in geometry to be visible but transparent
        const fadeInMat = fadeInManager.getMaterial();
        (fadeInMat as any).transparent = true;
        fadeInMat.opacity = 0;
        (fadeInMat as any).depthWrite = false;
        fadeInManager.setVisible(true);

        // Prepare fade-out
        const fadeOutMat = fadeOutManager.getMaterial();
        (fadeOutMat as any).transparent = true;
        (fadeOutMat as any).depthWrite = false;

        isFading = true;
        fadeStartTime = performance.now();
      }

      // Mesh data update
      if (state.meshVertices !== prev.meshVertices && state.meshVertices && state.meshFaces) {
        meshManager.updateMesh(state.meshVertices, state.meshFaces, state.meshColors);
      }
    });

    // --- Output hidden subscription (hide point cloud / voxels / mesh but keep scene) ---
    let prevOutputHidden = useMetricsStore.getState().outputHidden;
    const unsubOutputHidden = useMetricsStore.subscribe((state) => {
      if (state.outputHidden !== prevOutputHidden) {
        prevOutputHidden = state.outputHidden;
        if (state.outputHidden) {
          pointCloudManager.setVisible(false);
          voxelManager.setVisible(false);
          meshManager.setVisible(false);
        } else {
          // Restore visibility for the active output mode only
          pointCloudManager.setVisible(state.outputMode === 'cloud');
          voxelManager.setVisible(state.outputMode === 'voxel');
          meshManager.setVisible(state.outputMode === 'mesh');
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

    // --- Click-to-place: raycast to Z=0 plane in worldRoot coords ---
    const raycaster = new THREE.Raycaster();
    const mouse = new THREE.Vector2();
    // Ground plane normal in Z-up worldRoot space

    const handleClick = (event: MouseEvent) => {
      const placing = useControlStore.getState().placingRobot;
      if (!placing) return;

      const rect = renderer.domElement.getBoundingClientRect();
      mouse.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
      mouse.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;

      raycaster.setFromCamera(mouse, camera);

      // Intersect with the ground plane in world space
      // worldRoot has rotation, so we need to transform the plane into scene space
      const worldPlaneNormal = new THREE.Vector3(0, 0, 1).applyQuaternion(worldRoot.quaternion);
      const scenePlane = new THREE.Plane(worldPlaneNormal, 0);
      const intersection = new THREE.Vector3();
      const hit = raycaster.ray.intersectPlane(scenePlane, intersection);

      if (hit) {
        // Convert back to Z-up coords (worldRoot local space)
        const local = worldRoot.worldToLocal(intersection.clone());
        const sendRaw = useControlStore.getState().sendRaw;
        sendRaw?.({
          type: 'command',
          payload: {
            action: 'send_to',
            robot_id: placing,
            target: [local.x, local.y, 0],
          },
        });
        console.log(`[Argus] Sending ${placing} to (${local.x.toFixed(1)}, ${local.y.toFixed(1)})`);
        useControlStore.getState().setPlacingRobot(null);
      }
    };
    renderer.domElement.addEventListener('click', handleClick);

    // --- Render loop ---
    let animationId = 0;
    const animate = () => {
      animationId = requestAnimationFrame(animate);

      // Cross-fade animation
      if (isFading && fadeOutManager && fadeInManager) {
        const elapsed = performance.now() - fadeStartTime;
        const t = Math.min(elapsed / FADE_DURATION, 1.0);

        const fadeOutMat = fadeOutManager.getMaterial();
        fadeOutMat.opacity = 1.0 - t;

        const fadeInMat = fadeInManager.getMaterial();
        fadeInMat.opacity = t;

        if (t >= 1.0) {
          // Fade complete
          fadeOutMat.opacity = 0;
          (fadeOutMat as any).transparent = false;
          (fadeOutMat as any).depthWrite = true;
          fadeOutManager.setVisible(false);

          (fadeInMat as any).transparent = false;
          fadeInMat.opacity = 1.0;
          (fadeInMat as any).depthWrite = true;

          isFading = false;
          fadeOutManager = null;
          fadeInManager = null;
        }
      }

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
      unsubMetrics();
      unsubOutputHidden();
      unsubSceneColor();
      renderer.domElement.removeEventListener('click', handleClick);
      window.removeEventListener('focus-robot', handleCenterOnRobot);
      window.removeEventListener('resize', handleResize);
      resizeObserver.disconnect();
      controls.dispose();
      pointCloudManager.dispose();
      voxelManager.dispose();
      meshManager.dispose();
      robotMarkerManager.dispose();
      trailManager.dispose();
      detectionBoxManager.dispose();
      cameraFrustumManager.dispose();
      renderer.dispose();
      if (container.contains(renderer.domElement)) {
        container.removeChild(renderer.domElement);
      }
    };
  }, []);

  const placingRobot = useControlStore((s) => s.placingRobot);
  const isRestarting = useSlamStore((s) => s.isRestarting);
  const activeDisplay = useSlamStore((s) => s.activeDisplay);
  const crashMessage = useSlamStore((s) => s.crashMessage);
  // D-12 stacked RestartOverlay support: detector and lifter restarts share
  // detectorStore.isRestarting; restartSubsystem discriminates which overlay renders.
  const detectorRestarting = useDetectorStore((s) => s.isRestarting);
  const detectorDisplay = useDetectorStore((s) => s.activeDisplay);
  const lifterDisplay = useDetectorStore((s) => s.activeLifterDisplay);
  const restartSubsystem = useDetectorStore((s) => s.restartSubsystem);

  return (
    <div style={{ width: '100%', height: '100%', position: 'relative', overflow: 'hidden' }}>
      <div
        ref={containerRef}
        style={{
          width: '100%', height: '100%',
          cursor: placingRobot ? 'crosshair' : 'grab',
        }}
      />
      {placingRobot && (
        <div style={{
          position: 'absolute', top: '12px', left: '50%', transform: 'translateX(-50%)',
          background: 'rgba(0,0,0,0.8)', color: '#ff9800', padding: '8px 20px',
          borderRadius: '6px', fontSize: '14px', fontWeight: 600,
          border: '1px solid #ff9800', pointerEvents: 'none',
        }}>
          Click on the scene to send {placingRobot} to that position
        </div>
      )}
      {isRestarting && <RestartOverlay subsystem="slam" name={activeDisplay} />}
      {detectorRestarting && restartSubsystem === 'detector' && (
        <RestartOverlay subsystem="detector" name={detectorDisplay} />
      )}
      {detectorRestarting && restartSubsystem === 'lifter' && (
        <RestartOverlay subsystem="lifter" name={lifterDisplay} />
      )}
      {crashMessage && <CrashToast />}
    </div>
  );
}
