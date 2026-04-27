# brush-serverless

[![Runpod](https://api.runpod.io/badge/alx/brush-serverless)](https://console.runpod.io/hub/alx/brush-serverless)

Serverless [RunPod](https://www.runpod.io/) endpoint that trains a **3D Gaussian Splatting** model using [Brush](https://github.com/ArthurBrussee/brush), built from source. Part of the [RunSplat](https://github.com/alx/runsplat) pipeline.

**Input:** COLMAP workspace (base64 tar.gz) from [colmap-serverless](https://github.com/alx/colmap-serverless)  
**Output:** 3D Gaussian Splat `.ply` + web-ready `.splat` binary (base64)

```
colmap_workspace_b64 (tar.gz)
    │
    ▼  untar → colmap/ directory
    │
    ▼  Brush training (GPU, configurable steps)
    │
    ▼  PLY export (3D Gaussian Splat)
    │
    ▼  convert PLY → SPLAT (web-optimised binary)
    │
    ▼  ply_base64 + splat_base64
```

---

## What is 3D Gaussian Splatting?

3D Gaussian Splatting (3DGS) is a novel view synthesis technique that represents a scene as millions of tiny ellipsoidal "Gaussians", each with a position, orientation, size, opacity, and colour. Unlike traditional meshes or point clouds, the result lets you **fly through the scene and see it exactly as it is — from every angle — with real photographic textures**.

**Why it matters for drone professionals:**

- **See your land as it really looks** — not an abstraction, not a wireframe, but the actual site
- **Easier to understand than technical maps** — clients and decision-makers get it immediately
- **Ideal for design and planning** — walk through the future space before breaking ground
- **Remote measurements** — measure distances, areas, and heights from the browser
- **No heavy software** — view and share via URL, runs in any modern browser with WebGL
- **Track construction or erosion** — compare scenes from different flights over time

Explore the ecosystem:
- [superspl.at](https://superspl.at/) — The Home for 3D Gaussian Splatting
- [antimatter15/splat](https://antimatter15.com/splat/) — WebGL Gaussian Splat Viewer (the viewer embedded in RunSplat)

---

## Drone capture tips

The quality of the Gaussian Splat depends heavily on the diversity of viewing angles during capture. **Circular flight patterns** dramatically outperform traditional grid surveys:

> *Unlike traditional grid or double-grid patterns, Circlegrammetry enables drones to fly in circular patterns, with the camera angled between 45° and 70° toward the center of each circle. This method captures images from more angles in fewer flights.*
>
> — [SPH Engineering, Circlegrammetry](https://www.sphengineering.com/news/sph-engineering-launches-circlegrammetry-a-game-changer-in-drone-photogrammetry)

More viewing angles → richer Gaussian initialisation from COLMAP → better-trained splat.

---

## Stack

| Component | Version | Role |
|-----------|---------|------|
| [Brush](https://github.com/ArthurBrussee/brush) | `main` (built from source) | 3DGS trainer |
| CUDA | 12.9 | GPU training acceleration |
| Vulkan | system | wgpu backend for Brush |
| Xvfb | system | Virtual display (headless Vulkan) |
| [RunPod SDK](https://docs.runpod.io/serverless/workers/handlers/overview) | latest | Serverless handler |
| Rust | `latest` | Brush compilation |
| Build base | `rust:latest` | Cargo build stage |
| Runtime base | `nvidia/cuda:12.9.0-base-ubuntu24.04` | Runtime stage |

Brush is compiled with `lld` linker to avoid OOM link failures during `cargo build`.

---

## API

### Input

```json
{
  "input": {
    "colmap_workspace_b64": "<base64 tar.gz from colmap-serverless>",
    "steps": 30000,
    "eval_every": 1000,
    "export_every": 5000
  }
}
```

### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `colmap_workspace_b64` | string | *(required)* | Base64 tar.gz of `colmap/` directory (output of colmap-serverless) |
| `steps` | int | `30000` | Training iterations. More = higher quality, longer runtime. |
| `eval_every` | int | `1000` | Evaluate and log training loss every N steps |
| `export_every` | int | `5000` | Save intermediate PLY checkpoint every N steps |

#### Quality presets

| Preset | Steps | Approx. time | Use case |
|--------|-------|-------------|----------|
| Fast preview | 5 000 | ~3–5 min | Quick look, client preview |
| Standard | 30 000 | ~15–25 min | Deliverable quality |
| High quality | 60 000 | ~35–50 min | Archive, detailed inspection |

### Output

```json
{
  "ply_base64": "<base64 PLY file>",
  "splat_base64": "<base64 SPLAT binary for WebGL>",
  "num_gaussians": 1842311,
  "training_time_seconds": 1187,
  "steps_completed": 30000,
  "status": "done"
}
```

| Field | Description |
|-------|-------------|
| `ply_base64` | Standard PLY point cloud file containing all Gaussian parameters. Import into Blender, DCC tools, or any 3DGS viewer. |
| `splat_base64` | Web-optimised binary SPLAT format. Load directly in [antimatter15/splat](https://antimatter15.com/splat/) or the RunSplat viewer. |
| `num_gaussians` | Total Gaussians in the trained scene (typically 500k–5M depending on scene complexity). |
| `training_time_seconds` | Wall time for the Brush training run (excludes workspace extraction and PLY conversion). |

---

## Local build & test

### Requirements

- Docker with [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html)
- NVIDIA GPU with CUDA 12.9 driver support and ≥24 GB VRAM (for large scenes)
- A COLMAP workspace fixture (see below)

### Build

```bash
# First build compiles Brush from source — allow ~15–25 min
docker build -t brush-serverless:local .

# Stream output and save log
docker build -t brush-serverless:local . 2>&1 | tee /tmp/build.log

# Test only the Rust compilation stage
docker build --target brush-builder -t brush-builder . 2>&1 | tee /tmp/build-brush.log
```

### Test

The test requires a pre-generated COLMAP workspace fixture (lighthouse.mp4, 30 frames).
It is downloaded automatically from the brush-serverless GitHub releases:

```bash
./scripts/test_local.sh

# Skip rebuild if already built
./scripts/test_local.sh --no-build
```

To generate your own fixture from a local video:

```bash
# 1. Run colmap-serverless test and capture the workspace
docker run --rm --gpus all colmap-serverless:local \
  python3 handler.py --test_input '{
    "input": {
      "video_url": "https://github.com/alx/runsplat/releases/download/v0.1.5/lighthouse.mp4",
      "num_frames": 30
    }
  }' | python3 -c "
import sys, json, base64
out = json.loads(sys.stdin.read().split('\n')[-2])
open('/tmp/colmap.tar.gz', 'wb').write(base64.b64decode(out['colmap_workspace_b64']))
print('Saved /tmp/colmap.tar.gz')
"

# 2. Use the fixture in the brush test
WORKSPACE_B64=$(base64 -w 0 /tmp/colmap.tar.gz)
docker run --rm --gpus all brush-serverless:local \
  python3 handler.py --test_input "{\"input\":{\"colmap_workspace_b64\":\"$WORKSPACE_B64\",\"steps\":500}}"
```

---

## Publishing to RunPod Hub

1. Verify local build and test pass
2. Push to GitHub and create a release: `gh release create v1.0.0 --generate-notes`
3. RunPod Hub detects the release, builds the image, runs `.runpod/tests.json`
4. After tests pass, submit for review on the [Hub page](https://www.runpod.io/console/hub)

Configuration is in `.runpod/hub.json`. Available presets: **Fast preview** (5k), **Standard quality** (30k), **High quality** (60k).

---

## Brush documentation

- [Brush GitHub](https://github.com/ArthurBrussee/brush)
- [3DGS original paper](https://repo-sam.inria.fr/fungraph/3d-gaussian-splatting/) — Kerbl et al., SIGGRAPH 2023
- [superspl.at](https://superspl.at/) — Community hub for Gaussian Splatting
- [antimatter15/splat](https://antimatter15.com/splat/) — WebGL viewer used in RunSplat

---

## Related repos

| Repo | Role |
|------|------|
| [runsplat](https://github.com/alx/runsplat) | Full pipeline orchestrator + result viewer |
| [colmap-serverless](https://github.com/alx/colmap-serverless) | COLMAP SfM (produces input for this repo) |

---

## Credits

- [Brush](https://github.com/ArthurBrussee/brush) — Arthur Brussee, 3DGS trainer
- [antimatter15/splat](https://github.com/antimatter15/splat) — Kevin Kwok, WebGL viewer
- [COLMAP](https://github.com/colmap/colmap) — Schönberger & Frahm, Structure-from-Motion
- [RunPod](https://www.runpod.io/) — Serverless GPU infrastructure
- [SPH Engineering](https://www.sphengineering.com/news/sph-engineering-launches-circlegrammetry-a-game-changer-in-drone-photogrammetry) — Circlegrammetry technique
