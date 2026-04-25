# ── Build args ────────────────────────────────────────────────────────────────
# cuda12.5 target: CUDA_VERSION=12.5.1  UBUNTU_VERSION=24.04  (default/latest)
# cuda12.4 target: CUDA_VERSION=12.4.1  UBUNTU_VERSION=22.04
ARG CUDA_VERSION=12.5.1
ARG UBUNTU_VERSION=24.04

# ── Stage 1: compile Brush from source ────────────────────────────────────────
# Brush uses wgpu (Vulkan) for GPU — no CUDA dependency at compile time.
FROM rust:latest AS brush-builder

RUN apt-get update && apt-get install -y \
    git pkg-config libssl-dev lld \
    && rm -rf /var/lib/apt/lists/*

RUN git clone --depth 1 https://github.com/ArthurBrussee/brush.git /brush

WORKDIR /brush
RUN RUSTFLAGS="-C link-arg=-fuse-ld=lld" \
    cargo build --release -p brush-app --bin brush_app

# ── Stage 2: runtime with CUDA + Vulkan ───────────────────────────────────────
# Brush uses Vulkan (wgpu), not CUDA — CUDA base image provides driver access.
# Runtime packages are identical on ubuntu22.04 and ubuntu24.04 for Brush.
FROM nvidia/cuda:${CUDA_VERSION}-base-ubuntu${UBUNTU_VERSION}
ENV DEBIAN_FRONTEND=noninteractive
ENV NVIDIA_DRIVER_CAPABILITIES=compute,utility,graphics

RUN apt-get update && apt-get install -y \
    python3 python3-pip xvfb libvulkan1 \
    && rm -rf /var/lib/apt/lists/* \
    && mkdir -p /usr/share/vulkan/icd.d /etc/vulkan/icd.d

WORKDIR /app
RUN pip3 install --no-cache-dir --break-system-packages runpod numpy Pillow plyfile

COPY --from=brush-builder /brush/target/release/brush_app /app/binaries/brush_app_linux
COPY scripts/ /app/scripts/
COPY handler.py /app/handler.py

CMD ["python3", "-u", "handler.py"]
