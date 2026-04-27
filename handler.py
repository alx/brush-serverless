# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Alexandre Girard

import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
import urllib.parse
import urllib.request
from pathlib import Path

import requests
import runpod


def _download_gofile(url: str, dest: Path):
    sys.path.insert(0, "/app/scripts")
    from gofile_downloader import Manager as _GofileManager  # noqa: PLC0415
    with tempfile.TemporaryDirectory() as dl_dir:
        os.environ["GF_DOWNLOAD_DIR"] = dl_dir
        _GofileManager(url_or_file=url).run()
        files = sorted(f for f in Path(dl_dir).rglob("*") if f.is_file())
        if not files:
            raise RuntimeError(f"No file downloaded from GoFile: {url}")
        shutil.move(str(files[0]), str(dest))


def _upload_gofile(path: Path) -> str:
    server = requests.get("https://api.gofile.io/servers", timeout=30).json()["data"]["servers"][0]["name"]
    with open(path, "rb") as fh:
        resp = requests.post(
            f"https://{server}.gofile.io/uploadFile",
            files={"file": fh},
            timeout=300,
        ).json()
    return resp["data"]["downloadPage"]


def handler(event):
    inp = event["input"]

    workspace_url = inp.get("colmap_workspace_url")
    if not workspace_url:
        return {"error": "Provide colmap_workspace_url"}

    steps        = int(inp.get("steps", 30000))
    eval_every   = int(inp.get("eval_every", 1000))
    export_every = int(inp.get("export_every", 5000))

    with tempfile.TemporaryDirectory() as tmp:
        project_dir = Path(tmp) / "project"
        project_dir.mkdir()

        tarball = Path(tmp) / "colmap_workspace.tar.gz"
        print(f"Downloading workspace from {workspace_url}", flush=True)
        if urllib.parse.urlparse(workspace_url).netloc in ("gofile.io", "www.gofile.io"):
            _download_gofile(workspace_url, tarball)
        else:
            with urllib.request.urlopen(workspace_url) as resp:
                tarball.write_bytes(resp.read())

        with tarfile.open(tarball, "r:gz") as tar:
            tar.extractall(project_dir)

        start = time.time()
        result = subprocess.run(
            [
                "python3", "/app/scripts/brush_pipeline.py",
                "--project", str(project_dir),
                "--steps", str(steps),
                "--eval-every", str(eval_every),
                "--export-every", str(export_every),
            ],
            stderr=subprocess.PIPE, text=True,
        )
        training_time = int(time.time() - start)

        if result.returncode != 0:
            return {"error": f"Brush pipeline failed (exit {result.returncode}):\n{result.stderr[-3000:]}"}

        output_ply = project_dir / "output.ply"
        resolved_ply = output_ply.resolve()
        num_gaussians = _count_gaussians(resolved_ply)

        print("Uploading PLY to GoFile.io…", flush=True)
        ply_url = _upload_gofile(resolved_ply)

        output_splat = project_dir / "output.splat"
        splat_url = None
        if output_splat.exists():
            print("Uploading SPLAT to GoFile.io…", flush=True)
            splat_url = _upload_gofile(output_splat)

    return {
        "ply_url": ply_url,
        "splat_url": splat_url,
        "num_gaussians": num_gaussians,
        "training_time_seconds": training_time,
        "steps_completed": steps,
        "status": "done",
    }


def _count_gaussians(ply_path: Path) -> int:
    try:
        with open(ply_path, "rb") as f:
            for line in f:
                line = line.decode("ascii", errors="ignore").strip()
                if line.startswith("element vertex"):
                    return int(line.split()[-1])
                if line == "end_header":
                    break
    except Exception:
        pass
    return -1


runpod.serverless.start({"handler": handler})
