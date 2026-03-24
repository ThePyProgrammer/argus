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
  const loadedRef = useRef(false);
  const sceneObjRef = useRef<THREE.Object3D | null>(null);

  useEffect(() => {
    if (!parent) return;

    // If already loaded into THIS parent, skip
    if (loadedRef.current && sceneObjRef.current?.parent === parent) return;

    // Clean up any previously loaded scene (e.g. after Strict Mode remount)
    if (sceneObjRef.current?.parent) {
      sceneObjRef.current.parent.remove(sceneObjRef.current);
    }

    loadedRef.current = true;
    let cancelled = false;

    const loader = new GLTFLoader();
    setLoading(true);

    loader.load(
      '/scene.glb',
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
          err instanceof Error ? err.message : 'Failed to load scene.glb';
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
      loadedRef.current = false;
    };
  }, [parent]);

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
