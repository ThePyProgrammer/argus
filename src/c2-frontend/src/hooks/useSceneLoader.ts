import { useEffect, useRef, useState } from 'react';
import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';

/**
 * Attempts to load a GLB scene file into the provided Three.js scene.
 * Gracefully handles 404 (scene.glb may not exist yet).
 */
export function useSceneLoader(scene: THREE.Scene | null): {
  loading: boolean;
  error: string | null;
} {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const loadedRef = useRef(false);

  useEffect(() => {
    if (!scene || loadedRef.current) return;
    loadedRef.current = true;

    const loader = new GLTFLoader();
    setLoading(true);

    loader.load(
      '/assets/scene.glb',
      (gltf) => {
        scene.add(gltf.scene);
        setLoading(false);
      },
      undefined,
      (err) => {
        // Graceful fallback -- GLB may not exist yet
        const message =
          err instanceof Error ? err.message : 'Failed to load scene.glb';
        console.warn('[useSceneLoader] GLB not available, using empty scene:', message);
        setError(message);
        setLoading(false);
      },
    );
  }, [scene]);

  return { loading, error };
}
