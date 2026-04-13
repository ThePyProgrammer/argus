#!/usr/bin/env python3
"""Convert OBJ scene files to a single GLB for Three.js rendering.

Loads all OBJ files from the office scene directory and exports
them as a single GLB file suitable for the Argus frontend 3D viewer.

Input:  data/scenes/scene_office1/office_split/*.obj
Output: frontend/public/scene.glb

Methods (tried in order):
1. trimesh library (pip install trimesh) -- pure Python, most portable
2. gltfpack CLI (from meshoptimizer) -- if available on PATH

Usage:
    python scripts/convert_scene_glb.py
    python scripts/convert_scene_glb.py --colored
    python scripts/convert_scene_glb.py --input-dir path/to/objs --output path/to/scene.glb
"""


import argparse
import shutil
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


def find_default_input_dir() -> Path:
    """Locate the default OBJ input directory."""
    project_root = Path(__file__).parent.parent
    candidates = [
        project_root / "data" / "scenes" / "scene_office1" / "office_split",
        project_root / "data" / "scenes" / "scene_office1",
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


def parse_mujoco_materials(xml_path: Path) -> dict:
    """Parse MuJoCo XML for material RGBA colors, textures, and mesh-to-material mappings.

    Args:
        xml_path: Path to the MuJoCo XML scene file.

    Returns:
        Dict with keys: colors, textures, mesh_to_material, texture_dir
    """
    tree = ET.parse(str(xml_path))
    root = tree.getroot()

    # Get texture directory from compiler element
    compiler = root.find("compiler")
    texture_dir_rel = compiler.get("texturedir", "") if compiler is not None else ""
    texture_dir = xml_path.parent / texture_dir_rel if texture_dir_rel else xml_path.parent

    # Build texture name -> file mapping
    texture_files: dict[str, str] = {}
    for tex in root.iter("texture"):
        name = tex.get("name", "")
        file_ = tex.get("file", "")
        if name and file_:
            texture_files[name] = file_

    # Build material name -> RGBA and material name -> texture file
    material_colors: dict[str, tuple[float, float, float, float]] = {}
    material_textures: dict[str, str] = {}
    for mat in root.iter("material"):
        name = mat.get("name", "")
        if not name:
            continue
        rgba_str = mat.get("rgba", "")
        if rgba_str:
            parts = rgba_str.split()
            if len(parts) == 4:
                material_colors[name] = tuple(float(x) for x in parts)  # type: ignore[assignment]
        tex_ref = mat.get("texture", "")
        if tex_ref and tex_ref in texture_files:
            material_textures[name] = texture_files[tex_ref]

    # Build mesh name -> material name from geom elements
    mesh_to_material: dict[str, str] = {}
    for geom in root.iter("geom"):
        mesh_name = geom.get("mesh", "")
        mat_name = geom.get("material", "")
        if mesh_name and mat_name:
            mesh_to_material[mesh_name] = mat_name

    return {
        "colors": material_colors,
        "textures": material_textures,
        "mesh_to_material": mesh_to_material,
        "texture_dir": texture_dir,
    }


def convert_colored_with_trimesh(input_dir: Path, output: Path, xml_path: Path) -> bool:
    """Convert OBJ files to a colored GLB using MuJoCo XML material data.

    Args:
        input_dir: Directory containing .obj files.
        output: Output .glb file path.
        xml_path: Path to MuJoCo XML with material definitions.

    Returns:
        True if conversion succeeded.
    """
    try:
        import numpy as np
        import trimesh
    except ImportError:
        print("trimesh or numpy not installed. Install with: pip install trimesh numpy")
        return False

    mat_data = parse_mujoco_materials(xml_path)
    material_colors = mat_data["colors"]
    material_textures = mat_data["textures"]
    mesh_to_material = mat_data["mesh_to_material"]
    texture_dir = mat_data["texture_dir"]

    obj_files = sorted(input_dir.glob("*.obj"))
    if not obj_files:
        print(f"No .obj files found in {input_dir}")
        return False

    print(f"Found {len(obj_files)} OBJ files in {input_dir}")
    print(f"Materials: {len(material_colors)} colors, {len(material_textures)} textured")
    print(f"Mesh-to-material mappings: {len(mesh_to_material)}")
    scene = trimesh.Scene()
    loaded_count = 0
    skipped_count = 0

    for obj_file in obj_files:
        stem = obj_file.stem

        # Skip collision meshes
        if "_convex_" in stem:
            skipped_count += 1
            continue

        mat_name = mesh_to_material.get(stem, "")

        # Skip invisible materials
        if mat_name == "mat_invisible":
            skipped_count += 1
            continue

        try:
            mesh = trimesh.load(str(obj_file), force="mesh")
        except Exception as e:
            print(f"  Warning: could not load {obj_file.name}: {e}")
            continue

        # Try texture first, fall back to flat color
        textured = False
        if mat_name in material_textures:
            tex_file = texture_dir / material_textures[mat_name]
            if tex_file.exists():
                try:
                    from PIL import Image
                    img = Image.open(str(tex_file))
                    material = trimesh.visual.texture.SimpleMaterial(image=img)
                    if hasattr(mesh.visual, "uv") and mesh.visual.uv is not None and len(mesh.visual.uv) > 0:
                        mesh.visual = trimesh.visual.TextureVisuals(
                            uv=mesh.visual.uv, material=material
                        )
                        textured = True
                        print(f"  Textured: {stem} -> {material_textures[mat_name]}")
                except Exception as e:
                    print(f"  Texture fallback for {stem}: {e}")

        if not textured and mat_name in material_colors:
            rgba = material_colors[mat_name]
            # Force untextured light-grey materials (0.8,0.8,0.8) to white
            # so bare floor/ceiling areas match the white background
            if all(0.75 < c < 0.85 for c in rgba[:3]) and rgba[3] >= 1.0:
                rgba = (1.0, 1.0, 1.0, 1.0)
            rgba_uint8 = tuple(int(c * 255) for c in rgba)
            face_colors = np.full((len(mesh.faces), 4), rgba_uint8, dtype=np.uint8)
            mesh.visual.face_colors = face_colors
            print(f"  Colored: {stem} -> {mat_name} rgba={rgba}")
        elif not textured:
            print(f"  No material: {stem}")

        scene.add_geometry(mesh, node_name=stem)
        loaded_count += 1

    if loaded_count == 0:
        print("No geometry loaded -- cannot export colored GLB.")
        return False

    output.parent.mkdir(parents=True, exist_ok=True)
    print(f"\nExporting {loaded_count} colored meshes to {output} (skipped {skipped_count} convex/invisible)")
    scene.export(str(output), file_type="glb")
    size_mb = output.stat().st_size / (1024 * 1024)
    print(f"Colored GLB written: {output} ({size_mb:.1f} MB)")
    return True


def main():
    """Run the OBJ-to-GLB conversion."""
    parser = argparse.ArgumentParser(description="Convert OBJ scene files to GLB")
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=None,
        help="Directory containing .obj files (default: data/scenes/scene_office1/office_split/)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output .glb file path (default: frontend/public/scene.glb)",
    )
    parser.add_argument(
        "--colored",
        action="store_true",
        default=False,
        help="Also generate scene_colored.glb with MuJoCo material colors",
    )
    parser.add_argument(
        "--xml",
        type=Path,
        default=None,
        help="MuJoCo XML path (default: data/scenes/scene_office1.xml)",
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
        print("Ensure the office scene data is available at data/scenes/scene_office1/.")
        sys.exit(1)

    # Try trimesh first (most portable), then gltfpack
    if convert_with_trimesh(input_dir, output):
        print("\nConversion complete (trimesh).")
    else:
        print("\nFalling back to gltfpack...")
        if convert_with_gltfpack(input_dir, output):
            print("\nConversion complete (gltfpack).")
        else:
            print("\nERROR: All conversion methods failed.")
            print("Install trimesh: pip install trimesh")
            print("Or install gltfpack: https://github.com/zeux/meshoptimizer/releases")
            sys.exit(1)

    # Generate colored GLB if requested
    if args.colored:
        project_root = Path(__file__).parent.parent
        xml_path = args.xml or (project_root / "data" / "scenes" / "scene_office1.xml")
        colored_output = output.parent / "scene_colored.glb"

        if not xml_path.exists():
            print(f"\nERROR: MuJoCo XML not found: {xml_path}")
            print("Provide --xml path/to/scene_office1.xml")
            sys.exit(1)

        print(f"\n--- Generating colored GLB ---")
        print(f"  XML:    {xml_path}")
        print(f"  Output: {colored_output}")
        if convert_colored_with_trimesh(input_dir, colored_output, xml_path):
            print("\nColored GLB generation complete.")
        else:
            print("\nERROR: Colored GLB generation failed.")
            sys.exit(1)


if __name__ == "__main__":
    main()
