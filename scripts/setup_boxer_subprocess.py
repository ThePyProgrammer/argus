"""Cross-platform CPU setup for the pinned upstream BoxeR worker."""

import json
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SHA = "df474128a76ba42b05bc81feca7ac1a53fab41af"
VENV = ROOT / "subprocess_venvs" / "boxer"
REPO = VENV / "repo"
MODELS = ROOT / "models" / "boxer" / SHA
FILES = (
    "boxernet_hw960in4x6d768-wssxpf9p.ckpt",
    "dinov3_vits16plus_pretrain_lvd1689m-4057cbaa.pth",
    "owlv2-base-patch16-ensemble.pt",
)


def main():
    python = VENV / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
    ready = VENV / ".ready"
    if ready.is_file() and ready.read_text().strip() == SHA and python.is_file() and all(
        (MODELS / name).is_file() and (MODELS / name).stat().st_size > 1024 for name in FILES
    ):
        print("BoxeR already ready; skipping setup.", flush=True)
        return
    uv = shutil.which("uv")
    if uv is None:
        raise RuntimeError("Install uv before running BoxeR setup")
    VENV.mkdir(parents=True, exist_ok=True)
    if not REPO.exists():
        subprocess.run(["git", "clone", "https://github.com/facebookresearch/boxer", str(REPO)], check=True)
    subprocess.run(["git", "-C", str(REPO), "checkout", SHA], check=True)
    subprocess.run([uv, "venv", "--allow-existing", "--python", "3.12", str(VENV)], check=True)
    subprocess.run([uv, "pip", "install", "--python", str(python), "torch==2.10.0",
                    "--index-url", "https://download.pytorch.org/whl/cpu"], check=True)
    subprocess.run([uv, "pip", "install", "--python", str(python), "numpy", "opencv-python-headless",
                    "tqdm", "dill", "scipy", "msgpack", "pyzmq"], check=True)
    MODELS.mkdir(parents=True, exist_ok=True)
    # Resolve once so all three downloads come from the same model revision.
    revision_file = MODELS / "source_revision.txt"
    if revision_file.is_file():
        revision = revision_file.read_text().strip()
    else:
        with urllib.request.urlopen("https://huggingface.co/api/models/facebook/boxer", timeout=60) as response:
            revision = json.load(response)["sha"]
    for name in FILES:
        target = MODELS / name
        if target.is_file() and target.stat().st_size > 1024:
            print(f"Already downloaded: {name}", flush=True)
            continue
        print(f"Downloading {name}", flush=True)
        temporary = target.with_suffix(target.suffix + ".part")
        with urllib.request.urlopen(
            f"https://huggingface.co/facebook/boxer/resolve/{revision}/{name}", timeout=120,
        ) as response, temporary.open("wb") as destination:
            shutil.copyfileobj(response, destination, length=1024 * 1024)
        temporary.replace(target)
    (MODELS / "source_revision.txt").write_text(revision + "\n")
    subprocess.run([str(python), "-c", "import torch, cv2, scipy, zmq, msgpack, dill"], check=True)
    (VENV / ".ready").write_text(SHA + "\n")
    print("BoxeR CPU environment and checkpoints are ready.", flush=True)


if __name__ == "__main__":
    main()
