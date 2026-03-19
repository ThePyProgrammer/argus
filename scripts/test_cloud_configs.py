#!/usr/bin/env python3
"""Interactive 3D viewer to compare depth_to_cloud + pose transform configs.

Opens a web browser with a Three.js scene showing the robot position
and point clouds from different configurations. Click buttons to switch
between configs and visually compare which one places the cloud correctly.

Usage: python scripts/test_cloud_configs.py
Then open http://localhost:8888 in your browser.
"""

import json
import math
import threading
from http.server import HTTPServer, SimpleHTTPRequestHandler
import io

import numpy as np
import open3d as o3d

from src.coordination.multi_robot_config import MultiRobotConfig
from src.bridge.multi_bridge import MultiRobotBridge
from src.bridge.sensor_types import CameraIntrinsics


def compute_all_configs():
    """Run sim, compute clouds for all configs, return JSON data."""
    config = MultiRobotConfig(scene="flat")
    bridge = MultiRobotBridge(config)
    frames = bridge.start()

    w, h = config.resolution
    fx = (w / 2.0) / math.tan(math.radians(45.0) / 2.0)
    intrinsics = CameraIntrinsics(fx=fx, fy=fx, cx=w/2.0, cy=h/2.0, width=w, height=h)

    # Step forward
    for i in range(15):
        bridge.set_velocity("robot_a", np.array([0.5, 0.0]), 0.0)
        bridge.set_velocity("robot_b", np.array([0.0, 0.0]), 0.0)
        frames = bridge.step()

    frame = frames["robot_a"]
    body_pose = bridge._extract_pose("robot_a")
    body_pos = body_pose[:3, 3].tolist()

    cam_id = bridge._cam_ids["robot_a"]
    cam_pos = bridge._data.cam_xpos[cam_id].copy()
    cam_mat = bridge._data.cam_xmat[cam_id].reshape(3, 3).copy()

    bridge.stop()

    # Unproject depth
    depth = frame.depth
    rgb = frame.rgb
    hu, wu = depth.shape
    u, v = np.meshgrid(np.arange(wu), np.arange(hu))
    valid = (depth > 0) & (depth < 10.0)
    z = depth[valid]
    cx = (u[valid] - intrinsics.cx) * z / intrinsics.fx
    cy = (v[valid] - intrinsics.cy) * z / intrinsics.fy

    cloud_frames = {
        "A: [cx, -cy, -z]": np.stack([cx, -cy, -z], axis=-1),
        "B: [cx, cy, -z]": np.stack([cx, cy, -z], axis=-1),
        "C: [z, -cx, -cy]": np.stack([z, -cx, -cy], axis=-1),
        "D: [z, cx, -cy]": np.stack([z, cx, -cy], axis=-1),
        "E: [-z, cx, cy]": np.stack([-z, cx, cy], axis=-1),
        "F: [cx, -cy, z]": np.stack([cx, -cy, z], axis=-1),
        "G: [-cx, -cy, -z]": np.stack([-cx, -cy, -z], axis=-1),
        "H: [z, -cx, cy]": np.stack([z, -cx, cy], axis=-1),
    }

    # Build pose transforms
    cam_pose_noT = np.eye(4, dtype=np.float64)
    cam_pose_noT[:3, 3] = cam_pos
    cam_pose_noT[:3, :3] = cam_mat

    cam_pose_T = np.eye(4, dtype=np.float64)
    cam_pose_T[:3, 3] = cam_pos
    cam_pose_T[:3, :3] = cam_mat.T

    pose_transforms = {
        "body_pose": body_pose,
        "cam (no .T)": cam_pose_noT,
        "cam (.T)": cam_pose_T,
    }

    # Compute all combos, downsample for web
    results = {}
    for cname, pts in cloud_frames.items():
        for pname, pose in pose_transforms.items():
            pcd = o3d.geometry.PointCloud()
            pcd.points = o3d.utility.Vector3dVector(pts.copy())
            pcd.transform(pose)
            pcd = pcd.voxel_down_sample(0.2)  # coarse for web perf
            world_pts = np.asarray(pcd.points)
            if len(world_pts) == 0:
                continue
            center = world_pts.mean(axis=0)
            key = f"{cname} | {pname}"
            results[key] = {
                "points": world_pts.tolist(),
                "center": center.tolist(),
                "count": len(world_pts),
            }

    return {
        "body_pos": body_pos,
        "cam_pos": cam_pos.tolist(),
        "configs": results,
    }


HTML = """<!DOCTYPE html>
<html>
<head>
<title>Cloud Config Viewer</title>
<style>
  body { margin: 0; background: #111; color: #eee; font-family: monospace; }
  #controls { position: fixed; top: 10px; left: 10px; z-index: 10; max-height: 95vh; overflow-y: auto; }
  #controls button { display: block; margin: 2px 0; padding: 6px 12px; cursor: pointer;
    background: #333; color: #ddd; border: 1px solid #555; font-family: monospace; font-size: 11px;
    text-align: left; width: 100%; white-space: nowrap; }
  #controls button:hover { background: #555; }
  #controls button.active { background: #27ae60; color: #fff; border-color: #2ecc71; }
  #info { position: fixed; bottom: 10px; left: 10px; z-index: 10; background: rgba(0,0,0,0.7);
    padding: 10px; border-radius: 5px; font-size: 13px; }
  canvas { display: block; }
</style>
</head>
<body>
<div id="controls"></div>
<div id="info">Loading...</div>
<script type="importmap">
{
  "imports": {
    "three": "https://cdn.jsdelivr.net/npm/three@0.162.0/build/three.module.js",
    "three/addons/": "https://cdn.jsdelivr.net/npm/three@0.162.0/examples/jsm/"
  }
}
</script>
<script type="module">
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';

let scene, camera, renderer, controls, worldRoot;
let cloudMesh = null;
let data = null;

async function init() {
  scene = new THREE.Scene();
  scene.background = new THREE.Color(0x111122);

  // Z-up to Y-up conversion (same as C2 interface)
  worldRoot = new THREE.Group();
  worldRoot.rotation.x = -Math.PI / 2;
  scene.add(worldRoot);

  camera = new THREE.PerspectiveCamera(60, window.innerWidth/window.innerHeight, 0.1, 200);
  camera.position.set(3, 8, 8);
  camera.lookAt(0, 0, 0);

  renderer = new THREE.WebGLRenderer({ antialias: true });
  renderer.setSize(window.innerWidth, window.innerHeight);
  document.body.appendChild(renderer.domElement);

  controls = new OrbitControls(camera, renderer.domElement);

  // Lighting
  scene.add(new THREE.AmbientLight(0x666666));
  const dirLight = new THREE.DirectionalLight(0xffffff, 1);
  dirLight.position.set(5, 10, 5);
  scene.add(dirLight);

  // Grid on the ground (in worldRoot = Z-up space)
  const grid = new THREE.GridHelper(30, 30, 0x444444, 0x222222);
  grid.rotation.x = Math.PI / 2; // make it flat in Z-up
  worldRoot.add(grid);

  // Axes in worldRoot
  worldRoot.add(new THREE.AxesHelper(3));

  // Fetch data
  const resp = await fetch('/data.json');
  data = await resp.json();

  // Load Go2 GLB model for robot marker (same as C2 interface)
  const loader = new GLTFLoader();
  try {
    const gltf = await loader.loadAsync('/go2.glb');
    const model = gltf.scene;
    model.scale.setScalar(1.0);
    // Tint green
    model.traverse((child) => {
      if (child.isMesh) {
        child.material = new THREE.MeshStandardMaterial({
          color: 0x00cc66, emissive: 0x00cc66, emissiveIntensity: 0.2,
          transparent: true, opacity: 0.85,
        });
      }
    });
    model.position.set(data.cam_pos[0], data.cam_pos[1], data.cam_pos[2]);
    worldRoot.add(model);
  } catch(e) {
    // Fallback sphere if GLB not available
    const robotGeo = new THREE.SphereGeometry(0.2, 16, 16);
    const robotMat = new THREE.MeshBasicMaterial({ color: 0x00ff00 });
    const robotMesh = new THREE.Mesh(robotGeo, robotMat);
    robotMesh.position.set(data.cam_pos[0], data.cam_pos[1], data.cam_pos[2]);
    worldRoot.add(robotMesh);
  }

  // Camera position marker (small yellow sphere)
  const camGeo = new THREE.SphereGeometry(0.1, 8, 8);
  const camMat = new THREE.MeshBasicMaterial({ color: 0xffff00 });
  const camMesh = new THREE.Mesh(camGeo, camMat);
  camMesh.position.set(data.cam_pos[0], data.cam_pos[1], data.cam_pos[2]);
  worldRoot.add(camMesh);

  // Body position marker (small red sphere)
  const bodyGeo = new THREE.SphereGeometry(0.1, 8, 8);
  const bodyMat = new THREE.MeshBasicMaterial({ color: 0xff3333 });
  const bodyMesh = new THREE.Mesh(bodyGeo, bodyMat);
  bodyMesh.position.set(data.body_pos[0], data.body_pos[1], data.body_pos[2]);
  worldRoot.add(bodyMesh);

  // Labels
  const infoEl = document.getElementById('info');
  infoEl.innerHTML = `<b style="color:#0c6">Go2 model</b> = robot (at cam pos) &nbsp;
    <b style="color:#ff3">●</b> = camera &nbsp;
    <b style="color:#f33">●</b> = body<br>
    Body: [${data.body_pos.map(v=>v.toFixed(2)).join(', ')}]<br>
    Camera: [${data.cam_pos.map(v=>v.toFixed(2)).join(', ')}]<br>
    <i>Scene uses Z-up worldRoot with -90° X rotation (same as C2)</i><br>
    <span id="cloud-info">Select a config</span>`;

  // Focus camera on robot
  controls.target.set(data.cam_pos[0], 0.5, -data.cam_pos[1]);

  // Build buttons
  const ctrlDiv = document.getElementById('controls');

  // Reset button
  const resetBtn = document.createElement('button');
  resetBtn.textContent = '↺ Show all eliminated';
  resetBtn.style.background = '#553';
  resetBtn.style.marginBottom = '8px';
  resetBtn.onclick = () => {
    ctrlDiv.querySelectorAll('button').forEach(b => b.style.display = 'block');
  };
  ctrlDiv.appendChild(resetBtn);

  // Instructions
  const hint = document.createElement('div');
  hint.style.cssText = 'font-size:10px; color:#888; margin-bottom:8px; padding:0 4px;';
  hint.textContent = 'Click = show | Right-click or Shift+click = eliminate';
  ctrlDiv.appendChild(hint);

  const keys = Object.keys(data.configs);
  keys.forEach(key => {
    const btn = document.createElement('button');
    const cfg = data.configs[key];
    const c = cfg.center;
    const offset = [c[0]-data.body_pos[0], c[1]-data.body_pos[1], c[2]-data.body_pos[2]];
    const good = (offset[0]>1 && offset[0]<10 && Math.abs(offset[1])<1 && Math.abs(offset[2])<0.5);
    btn.textContent = `${key} (${cfg.count}pts) [${offset.map(v=>v.toFixed(1)).join(',')}]${good?' ✓':''}`;
    if (good) btn.style.borderColor = '#2ecc71';
    btn.onclick = (e) => {
      if (e.shiftKey) {
        // Shift+click to eliminate
        btn.style.display = 'none';
        if (cloudMesh) { worldRoot.remove(cloudMesh); cloudMesh.geometry.dispose(); cloudMesh.material.dispose(); cloudMesh = null; }
      } else {
        showConfig(key, btn);
      }
    };
    // Right-click to eliminate
    btn.oncontextmenu = (e) => {
      e.preventDefault();
      btn.style.display = 'none';
      if (cloudMesh) { worldRoot.remove(cloudMesh); cloudMesh.geometry.dispose(); cloudMesh.material.dispose(); cloudMesh = null; }
    };
    ctrlDiv.appendChild(btn);
  });

  // Show first good config or first config
  const firstGood = keys.find(k => {
    const c = data.configs[k].center;
    const o = [c[0]-data.body_pos[0], c[1]-data.body_pos[1], c[2]-data.body_pos[2]];
    return o[0]>1 && o[0]<10 && Math.abs(o[1])<1 && Math.abs(o[2])<0.5;
  });
  if (firstGood) showConfig(firstGood, ctrlDiv.children[keys.indexOf(firstGood)]);

  animate();
}

function showConfig(key, btn) {
  // Update button styles
  document.querySelectorAll('#controls button').forEach(b => b.classList.remove('active'));
  if (btn) btn.classList.add('active');

  // Remove old cloud
  if (cloudMesh) { worldRoot.remove(cloudMesh); cloudMesh.geometry.dispose(); cloudMesh.material.dispose(); }

  const cfg = data.configs[key];
  const positions = new Float32Array(cfg.points.flat());
  const geo = new THREE.BufferGeometry();
  geo.setAttribute('position', new THREE.BufferAttribute(positions, 3));
  const mat = new THREE.PointsMaterial({ color: 0x4488ff, size: 0.08 });
  cloudMesh = new THREE.Points(geo, mat);
  worldRoot.add(cloudMesh);

  // Update info
  const c = cfg.center;
  const offset = [c[0]-data.body_pos[0], c[1]-data.body_pos[1], c[2]-data.body_pos[2]];
  document.getElementById('cloud-info').innerHTML =
    `<b>${key}</b><br>` +
    `Cloud center: [${c.map(v=>v.toFixed(2)).join(', ')}]<br>` +
    `Offset from robot: [${offset.map(v=>v.toFixed(2)).join(', ')}]<br>` +
    `Points: ${cfg.count}`;

  // Focus camera on cloud
  controls.target.set(c[0], c[1], c[2]);
}

function animate() {
  requestAnimationFrame(animate);
  controls.update();
  renderer.render(scene, camera);
}

window.addEventListener('resize', () => {
  camera.aspect = window.innerWidth / window.innerHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(window.innerWidth, window.innerHeight);
});

init();
</script>
</body>
</html>
"""


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, json_data=None, **kwargs):
        self._json_data = json_data
        super().__init__(*args, **kwargs)

    def do_GET(self):
        if self.path == '/' or self.path == '/index.html':
            self.send_response(200)
            self.send_header('Content-Type', 'text/html')
            self.end_headers()
            self.wfile.write(HTML.encode())
        elif self.path == '/data.json':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(self._json_data).encode())
        elif self.path == '/go2.glb':
            # Serve Go2 GLB from c2-frontend public dir
            from pathlib import Path
            glb_path = Path(__file__).parent.parent / "frontend" / "public" / "go2.glb"
            if glb_path.exists():
                self.send_response(200)
                self.send_header('Content-Type', 'model/gltf-binary')
                self.end_headers()
                self.wfile.write(glb_path.read_bytes())
            else:
                self.send_error(404, "go2.glb not found")
        else:
            self.send_error(404)

    def log_message(self, format, *args):
        pass  # quiet


def main():
    print("Computing cloud configs (running MuJoCo sim)...")
    data = compute_all_configs()

    print(f"Generated {len(data['configs'])} configs")
    for key, cfg in data['configs'].items():
        c = cfg['center']
        bp = data['body_pos']
        offset = [c[i]-bp[i] for i in range(3)]
        good = offset[0]>1 and offset[0]<10 and abs(offset[1])<1 and abs(offset[2])<0.5
        mark = " ✓" if good else ""
        print(f"  {key:<40} offset=[{offset[0]:>6.2f},{offset[1]:>6.2f},{offset[2]:>6.2f}]{mark}")

    # Serve
    def handler_factory(*args, **kwargs):
        return Handler(*args, json_data=data, **kwargs)

    server = HTTPServer(('0.0.0.0', 8888), handler_factory)
    print(f"\nOpen http://localhost:8888 in your browser")
    print("Press Ctrl+C to stop\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nDone.")


if __name__ == "__main__":
    main()
