"""Recover unavailable office assets from the frontend's bundled geometry."""

import logging
import xml.etree.ElementTree as ET
from pathlib import Path

logger = logging.getLogger(__name__)
_LFS_HEADER = b"version https://git-lfs.github.com/spec/v1"


def ensure_colored_scene(glb_path: Path, xml_path: Path, output: Path) -> None:
    """Create the optional colored viewer asset from bundled meshes and MJCF colors."""
    if output.exists() or not glb_path.is_file() or not xml_path.is_file():
        return
    import numpy as np
    import trimesh

    root = ET.parse(xml_path).getroot()
    colors = {
        mat.attrib["name"]: [float(v) for v in mat.get("rgba", "0.8 0.8 0.8 1").split()]
        for mat in root.findall("asset/material")
    }
    materials = {
        geom.attrib["mesh"]: geom.get("material", "")
        for geom in root.iter("geom") if geom.get("mesh")
    }
    source = trimesh.load_scene(glb_path, process=False)
    colored = trimesh.Scene()
    for node in source.graph.nodes_geometry:
        material = materials.get(node, "")
        rgba = colors.get(material, [0.8, 0.8, 0.8, 1])
        if "_convex_" in node or material == "mat_invisible" or rgba[3] == 0:
            continue
        transform, geometry = source.graph[node]
        mesh = source.geometry[geometry].copy()
        mesh.visual = trimesh.visual.ColorVisuals(
            mesh=mesh, face_colors=np.round(np.array(rgba) * 255).astype(np.uint8),
        )
        colored.add_geometry(mesh, node_name=node, transform=transform)
    if not colored.geometry:
        raise ValueError(f"No visible office meshes found in {glb_path}")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(colored.export(file_type="glb"))
    logger.info("Generated colored office scene at %s", output)


def recover_office_assets(
    root: ET.Element, assets: dict[str, bytes], glb_path: Path,
) -> None:
    """Fill missing mesh bytes, retaining the original MJCF collision geometry.

    The bundled GLB was exported from the OBJ files without applying the MJCF
    body transforms. Use its node names (not geometry names) to recover those
    local meshes; the original XML still supplies all placement and rotation.
    Unavailable textures fall back to the material's existing RGBA color.
    """
    asset = root.find("asset")
    if asset is None:
        return

    def unavailable(filename: str) -> bool:
        data = assets.get(filename)
        return not data or data.startswith(_LFS_HEADER)

    missing_meshes = [
        mesh for mesh in asset.findall("mesh")
        if mesh.get("file") and unavailable(mesh.attrib["file"])
    ]
    if missing_meshes:
        if not glb_path.is_file():
            raise FileNotFoundError(
                f"Office meshes are missing or Git LFS pointers, and {glb_path} "
                "is unavailable. Recover the LFS assets or restore frontend/public/scene.glb."
            )
        import trimesh

        scene = trimesh.load_scene(glb_path, process=False)
        for mesh in missing_meshes:
            filename = mesh.attrib["file"]
            node = Path(filename).stem
            if node not in scene.graph.nodes_geometry:
                raise ValueError(f"Office GLB is missing required mesh node {node!r}")
            transform, geometry = scene.graph[node]
            recovered = scene.geometry[geometry].copy()
            recovered.apply_transform(transform)
            assets[filename] = recovered.export(
                file_type="obj", include_texture=False, include_normals=False,
            ).encode("utf-8")
            # GLB stores float32 positions; thin visual surfaces can become
            # exactly planar. Surface inertia avoids a spurious volume error.
            mesh.set("inertia", "shell")
        logger.warning("Recovered %d office meshes from %s", len(missing_meshes), glb_path)
        # Rounding in float32 planar meshes can also violate the triangle
        # inequality by epsilon when MuJoCo combines their surface inertias.
        compiler = root.find("compiler")
        if compiler is not None:
            compiler.set("balanceinertia", "true")

    missing_textures = {
        texture.attrib["name"] for texture in asset.findall("texture")
        if texture.get("file") and unavailable(texture.attrib["file"])
    }
    for texture in list(asset.findall("texture")):
        if texture.get("name") in missing_textures:
            asset.remove(texture)
    for material in asset.findall("material"):
        if material.get("texture") in missing_textures:
            del material.attrib["texture"]
    if missing_textures:
        logger.warning("%d office textures unavailable; using material colors", len(missing_textures))
