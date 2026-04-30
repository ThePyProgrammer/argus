"""Built-in SLAM backends. Importing this package registers all built-in backends."""

from src.slam.registry import SLAMRegistry

from src.slam.backends import icp_backend


def _register_backend(name: str, display: str, class_path: str) -> None:
    existing = SLAMRegistry._backends.get(name)
    if existing is None:
        SLAMRegistry.register(name, display, class_path)
        return
    if existing["class_path"] != class_path:
        SLAMRegistry.register(name, display, class_path)


def register_builtin_backends() -> None:
    _register_backend(
        "icp",
        "ICP Odometry",
        f"{icp_backend.ICPBackend.__module__}.{icp_backend.ICPBackend.__qualname__}",
    )

    for module_name, class_name, name, display in (
        ("orbslam3_backend", "ORBSlam3Backend", "orbslam3", "ORB-SLAM3"),
        ("openvins_backend", "OpenVINSBackend", "openvins", "OpenVINS (VIO)"),
        ("svopro_backend", "SVOProBackend", "svopro", "SVO Pro / DSO"),
    ):
        try:
            module = __import__(f"src.slam.backends.{module_name}", fromlist=[class_name])
            klass = getattr(module, class_name)
        except Exception:
            continue
        _register_backend(name, display, f"{klass.__module__}.{klass.__qualname__}")


register_builtin_backends()
