#!/usr/bin/env python3
"""Brush pipeline: colmap/ workspace → 3D Gaussian Splat PLY + SPLAT."""

import argparse
import os
import subprocess
import sys
from pathlib import Path

_LFS_MARKER = b"version https://git-lfs.github.com"


def run(cmd: list, **kwargs):
    print(f"+ {' '.join(str(c) for c in cmd)}", flush=True)
    subprocess.run(cmd, check=True, **kwargs)


def find_brush_binary() -> Path:
    candidates = [
        Path("/app/binaries/brush_app_linux"),
        Path("/usr/local/bin/brush_app"),
    ]
    for p in candidates:
        if not p.exists():
            continue
        with open(p, "rb") as f:
            if f.read(64).startswith(_LFS_MARKER):
                continue
        if os.access(p, os.X_OK):
            return p
    raise FileNotFoundError("brush_app binary not found at /app/binaries/brush_app_linux")


def run_brush(project_dir: Path, steps: int, eval_every: int, export_every: int):
    brush_bin = find_brush_binary()
    print(f"Using brush binary: {brush_bin}", flush=True)
    colmap_dir = project_dir / "colmap"
    brush_dir = project_dir / "brush"
    brush_dir.mkdir(parents=True, exist_ok=True)
    export_name = f"export_{steps:06d}.ply"
    run([
        "xvfb-run", "-a",
        str(brush_bin),
        str(colmap_dir),
        "--export-path", str(brush_dir),
        "--export-name", export_name,
        "--total-steps", str(steps),
        "--eval-every", str(eval_every),
        "--export-every", str(export_every),
    ])
    _normalise_brush_exports(brush_dir, export_name)


def _normalise_brush_exports(brush_dir: Path, expected_name: str):
    stem = Path(expected_name).stem
    bare = brush_dir / stem
    if bare.exists() and not bare.suffix:
        bare.rename(brush_dir / f"{stem}.ply")

    plys = sorted(brush_dir.glob("export_*.ply"))
    if not plys:
        return
    latest = plys[-1]
    link = brush_dir / "export.ply"
    if link.is_symlink() or link.exists():
        link.unlink()
    link.symlink_to(latest.name)
    print(f"export.ply → {latest.name}", flush=True)


def convert_to_splat(project_dir: Path) -> Path:
    from convert import process_ply_to_splat, save_splat_file

    brush_dir = project_dir / "brush"
    link = brush_dir / "export.ply"
    if link.is_symlink():
        final_ply = link.resolve()
    else:
        plys = sorted(brush_dir.glob("export_*.ply"))
        if not plys:
            raise FileNotFoundError(f"No PLY exports found in {brush_dir}")
        final_ply = plys[-1]

    output_ply = project_dir / "output.ply"
    if output_ply.is_symlink() or output_ply.exists():
        output_ply.unlink()
    output_ply.symlink_to(final_ply)

    output_splat = project_dir / "output.splat"
    print(f"Converting {final_ply.name} → output.splat", flush=True)
    save_splat_file(process_ply_to_splat(str(final_ply)), str(output_splat))
    return output_splat


def main():
    parser = argparse.ArgumentParser(description="Brush pipeline: colmap workspace → PLY")
    parser.add_argument("--project", required=True, type=Path,
                        help="Project directory containing colmap/ subdirectory")
    parser.add_argument("--steps", type=int, default=30000,
                        help="Brush training steps (default: 30000)")
    parser.add_argument("--eval-every", type=int, default=1000,
                        help="Evaluate loss every N steps (default: 1000)")
    parser.add_argument("--export-every", type=int, default=5000,
                        help="Export intermediate PLY every N steps (default: 5000)")
    args = parser.parse_args()

    project_dir = args.project.resolve()

    if not (project_dir / "colmap").exists():
        print(f"Error: {project_dir / 'colmap'} not found", file=sys.stderr)
        sys.exit(1)

    sys.path.insert(0, str(Path(__file__).parent))

    print("\n[brush] Running Brush 3DGS training...", flush=True)
    run_brush(project_dir, args.steps, args.eval_every, args.export_every)

    print("\n[convert] Converting PLY → SPLAT...", flush=True)
    convert_to_splat(project_dir)

    print(f"\nDone! Output: {project_dir / 'output.ply'}", flush=True)


if __name__ == "__main__":
    main()
