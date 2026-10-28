import * as THREE from 'three';
export interface SceneGeometry {
  bounds: [number, number, number, number];
  geoms: { name: string; type: number; size: number[]; position: number[]; rotation: number[]; rgba: number[]; floor: boolean; walkable?: boolean }[];
}
/** Build the same compiled MuJoCo primitives in a Y-up viewer group. */
export function buildSceneGeometry(data: SceneGeometry, colored = true): THREE.Group {
  const group = new THREE.Group();
  group.rotation.x = -Math.PI / 2;
  for (const geom of data.geoms) {
    const [a, b, c] = geom.size;
    let geometry: THREE.BufferGeometry;
    switch (geom.type) {
      case 0: geometry = new THREE.PlaneGeometry(a * 2, b * 2); break;
      case 2: geometry = new THREE.SphereGeometry(a, 20, 12); break;
      case 3: geometry = new THREE.CapsuleGeometry(a, b * 2, 6, 16).rotateX(Math.PI / 2); break;
      case 4: geometry = new THREE.SphereGeometry(1, 20, 12).scale(a, b, c); break;
      case 5: geometry = new THREE.CylinderGeometry(a, a, b * 2, 24).rotateX(Math.PI / 2); break;
      case 6: geometry = new THREE.BoxGeometry(a * 2, b * 2, c * 2); break;
      default: throw new Error(`Unsupported scene geometry ${geom.type}`);
    }
    const [r, g, blue, alpha] = geom.rgba;
    const material = new THREE.MeshBasicMaterial({ color: colored ? new THREE.Color(r, g, blue) : new THREE.Color(geom.floor ? '#26352e' : '#819087'), transparent: alpha < 1, opacity: alpha, side: THREE.DoubleSide });
    const mesh = new THREE.Mesh(geometry, material);
    mesh.name = geom.name;
    mesh.position.set(geom.position[0], geom.position[1], geom.position[2]);
    const m = geom.rotation;
    mesh.quaternion.setFromRotationMatrix(new THREE.Matrix4().set(m[0],m[1],m[2],0, m[3],m[4],m[5],0, m[6],m[7],m[8],0, 0,0,0,1));
    mesh.userData.spawnFloor = geom.floor || geom.walkable;
    group.add(mesh);
  }
  return group;
}

export function disposeScene(object: THREE.Object3D) {
  object.traverse(child => {
    if (child instanceof THREE.Mesh) {
      child.geometry.dispose();
      (Array.isArray(child.material) ? child.material : [child.material]).forEach(material => material.dispose());
    }
  });
}
