#!/usr/bin/env python3
"""Convert OBJ scene files to a single GLB for Three.js rendering.

Loads all OBJ files from the DimOS office scene directory and exports
them as a single GLB file suitable for the C2 frontend 3D viewer.

Input:  dimos/data/mujoco_sim/scene_office1/office_split/*.obj
Output: frontend/public/scene.glb

Methods (tried in order):
1. trimesh library (pip install trimesh) -- pure Python, most portable
2. gltfpack CLI (from meshoptimizer) -- if available on PATH

Usage:
    python scripts/convert_scene_glb.py
    python scripts/convert_scene_glb.py --input-dir path/to/objs --output path/to/scene.glb
"""


import argparse
import shutil
import sys
from pathlib import Path


def find_default_input_dir() -> Path:
    """Locate the default OBJ input directory."""
    project_root = Path(__file__).parent.parent
    candidates = [
        project_root / "dimos" / "data" / "mujoco_sim" / "scene_office1" / "office_split",
        project_root / "dimos" / "data" / "mujoco_sim" / "scene_office1",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]  # Return first even if missing, for error message


def find_default_output() -> Path:
    """Return the default output path for the GLB file."""
    project_root = Path(__file__).parent.parent
    return project_root / "frontend" / "public" / "scene.glb"


def convert_with_trimesh(input_dir: Path, output: Path) -> bool:
    """Convert OBJ files to GLB using trimesh.

    Args:
        input_dir: Directory containing .obj files.
        output: Output .glb file path.

    Returns:
        True if conversion succeeded.
    """
    try:
        import trimesh
    except ImportError:
        print("trimesh not installed. Install with: pip install trimesh")
        return False

    obj_files = sorted(input_dir.glob("*.obj"))
    if not obj_files:
        print(f"No .obj files found in {input_dir}")
        return False

    print(f"Found {len(obj_files)} OBJ files in {input_dir}")
    scene = trimesh.Scene()

    for obj_file in obj_files:
        print(f"  Loading: {obj_file.name}")
        try:
            mesh = trimesh.load(str(obj_file), force="mesh")
            scene.add_geometry(mesh, node_name=obj_file.stem)
        except Exception as e:
            print(f"  Warning: could not load {obj_file.name}: {e}")
            # Try loading as scene (multi-object OBJ)
            try:
                loaded = trimesh.load(str(obj_file))
                if hasattr(loaded, "geometry"):
                    for name, geom in loaded.geometry.items():
                        scene.add_geometry(geom, node_name=f"{obj_file.stem}_{name}")
                else:
                    scene.add_geometry(loaded, node_name=obj_file.stem)
            except Exception as e2:
                print(f"  Skipping {obj_file.name}: {e2}")

    if len(scene.geometry) == 0:
        print("No geometry loaded -- cannot export GLB.")
        return False

    # Ensure output directory exists
    output.parent.mkdir(parents=True, exist_ok=True)

    print(f"\nExporting {len(scene.geometry)} meshes to {output}")
    scene.export(str(output), file_type="glb")
    size_mb = output.stat().st_size / (1024 * 1024)
    print(f"GLB written: {output} ({size_mb:.1f} MB)")
    return True


def convert_with_gltfpack(input_dir: Path, output: Path) -> bool:
    """Convert OBJ files to GLB using gltfpack CLI.

    Args:
        input_dir: Directory containing .obj files.
        output: Output .glb file path.

    Returns:
        True if conversion succeeded.
    """
    import subprocess
    import tempfile

    gltfpack = shutil.which("gltfpack")
    if not gltfpack:
        print("gltfpack not found on PATH.")
        print("Install: download from https://github.com/zeux/meshoptimizer/releases")
        return False

    obj_files = sorted(input_dir.glob("*.obj"))
    if not obj_files:
        print(f"No .obj files found in {input_dir}")
        return False

    # Convert each OBJ individually, then try to merge
    output.parent.mkdir(parents=True, exist_ok=True)
    glb_parts = []

    with tempfile.TemporaryDirectory() as tmpdir:
        for obj_file in obj_files:
            part_glb = Path(tmpdir) / f"{obj_file.stem}.glb"
            print(f"  Converting: {obj_file.name}")
            try:
                subprocess.run(
                    [gltfpack, "-i", str(obj_file), "-o", str(part_glb)],
                    check=True,
                    capture_output=True,
                )
                glb_parts.append(part_glb)
            except subprocess.CalledProcessError as e:
                print(f"  Warning: gltfpack failed for {obj_file.name}: {e}")

        if not glb_parts:
            print("No GLB parts created.")
            return False

        # If only one part, just copy it
        if len(glb_parts) == 1:
            shutil.copy2(glb_parts[0], output)
        else:
            # Try trimesh to merge the GLB parts
            try:
                import trimesh
                scene = trimesh.Scene()
                for part in glb_parts:
                    loaded = trimesh.load(str(part))
                    if hasattr(loaded, "geometry"):
                        for name, geom in loaded.geometry.items():
                            scene.add_geometry(geom)
                    else:
                        scene.add_geometry(loaded)
                scene.export(str(output), file_type="glb")
            except ImportError:
                # Fall back to just using the first part
                print("  trimesh not available for merging; using first part only")
                shutil.copy2(glb_parts[0], output)

    size_mb = output.stat().st_size / (1024 * 1024)
    print(f"GLB written: {output} ({size_mb:.1f} MB)")
    return True


def main():
    """Run the OBJ-to-GLB conversion."""
    parser = argparse.ArgumentParser(description="Convert OBJ scene files to GLB")
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=None,
        help="Directory containing .obj files (default: dimos/data/mujoco_sim/scene_office1/office_split/)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output .glb file path (default: frontend/public/scene.glb)",
    )
    args = parser.parse_args()

    input_dir = args.input_dir or find_default_input_dir()
    output = args.output or find_default_output()

    print(f"Scene GLB Conversion")
    print(f"  Input:  {input_dir}")
    print(f"  Output: {output}")
    print()

    if not input_dir.exists():
        print(f"ERROR: Input directory does not exist: {input_dir}")
        print("Ensure the DimOS scene data is available:")
        print("  cd dimos && git lfs pull --include 'data/.lfs/mujoco_sim.tar.gz'")
        sys.exit(1)

    # Try trimesh first (most portable), then gltfpack
    if convert_with_trimesh(input_dir, output):
        print("\nConversion complete (trimesh).")
        return

    print("\nFalling back to gltfpack...")
    if convert_with_gltfpack(input_dir, output):
        print("\nConversion complete (gltfpack).")
        return

    print("\nERROR: All conversion methods failed.")
    print("Install trimesh: pip install trimesh")
    print("Or install gltfpack: https://github.com/zeux/meshoptimizer/releases")
    sys.exit(1)


if __name__ == "__main__":
    main()
