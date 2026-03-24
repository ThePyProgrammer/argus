import { useEffect, useRef, useState } from 'react';
import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { useControlStore } from '../stores/controlStore';

/**
 * Loads GLB scene file and toggles visibility via controlStore.showScene.
 */
export function useSceneLoader(parent: THREE.Object3D | null): {
  loading: boolean;
  error: string | null;
} {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const sceneObjRef = useRef<THREE.Object3D | null>(null);
  const sceneColored = useControlStore((s) => s.sceneColored);

  useEffect(() => {
    if (!parent) return;

    // Clean up any previously loaded scene
    if (sceneObjRef.current?.parent) {
      sceneObjRef.current.parent.remove(sceneObjRef.current);
    }
    sceneObjRef.current = null;

    let cancelled = false;
    const loader = new GLTFLoader();
    const glbUrl = sceneColored ? '/scene_colored.glb' : '/scene.glb';
    setLoading(true);
    setError(null);

    loader.load(
      glbUrl,
      (gltf) => {
        if (cancelled) return;
        sceneObjRef.current = gltf.scene;
        gltf.scene.visible = useControlStore.getState().showScene;
        parent.add(gltf.scene);
        setLoading(false);
      },
      undefined,
      (err) => {
        if (cancelled) return;
        const message =
          err instanceof Error ? err.message : `Failed to load ${glbUrl}`;
        console.warn('[useSceneLoader] GLB not available, using empty scene:', message);
        setError(message);
        setLoading(false);
      },
    );

    return () => {
      cancelled = true;
      // Remove scene from parent on cleanup so re-run loads fresh
      if (sceneObjRef.current?.parent === parent) {
        parent.remove(sceneObjRef.current);
      }
      sceneObjRef.current = null;
    };
  }, [parent, sceneColored]);

  // Subscribe to showScene toggle
  useEffect(() => {
    const unsub = useControlStore.subscribe((state, prev) => {
      if (state.showScene !== prev.showScene && sceneObjRef.current) {
        sceneObjRef.current.visible = state.showScene;
      }
    });
    return unsub;
  }, []);

  return { loading, error };
}
