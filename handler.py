# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Alexandre Girard

import base64
import subprocess
import tarfile
import tempfile
import time
import urllib.request
from pathlib import Path

import runpod


def handler(event):
    inp = event["input"]

    workspace_b64 = inp.get("colmap_workspace_b64")
    workspace_url  = inp.get("colmap_workspace_url")

    if not workspace_b64 and not workspace_url:
        return {"error": "Provide colmap_workspace_b64 or colmap_workspace_url"}

    if not workspace_b64:
        with urllib.request.urlopen(workspace_url) as resp:
            workspace_b64 = base64.b64encode(resp.read()).decode()

    steps        = int(inp.get("steps", 30000))
    eval_every   = int(inp.get("eval_every", 1000))
    export_every = int(inp.get("export_every", 5000))

    with tempfile.TemporaryDirectory() as tmp:
        project_dir = Path(tmp) / "project"
        project_dir.mkdir()

        tarball = Path(tmp) / "colmap_workspace.tar.gz"
        tarball.write_bytes(base64.b64decode(workspace_b64))
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
        ply_data = resolved_ply.read_bytes()

        output_splat = project_dir / "output.splat"
        splat_data = output_splat.read_bytes() if output_splat.exists() else b""

        num_gaussians = _count_gaussians(resolved_ply)

    return {
        "ply_base64": base64.b64encode(ply_data).decode(),
        "splat_base64": base64.b64encode(splat_data).decode() if splat_data else None,
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
