#!/bin/bash
set -e

# Build multi-architecture images with architecture-specific optimizations
# This approach keeps image sizes small by using CPU-optimized PyTorch on AMD64

IMAGE_BASE="ghcr.io/jbenshetler/mcp-ragex"
VERSION="cpu-latest"

echo "🔨 Building architecture-specific images..."

# Build AMD64 image with CPU-optimized PyTorch
echo "📦 Building AMD64 image (CPU-optimized)..."
docker buildx build \
  --platform linux/amd64 \
  -f docker/cpu/Dockerfile.amd64 \
  -t "${IMAGE_BASE}:${VERSION}-amd64" \
  --load \
  .

# Build ARM64 image with regular PyTorch
echo "📦 Building ARM64 image..."  
docker buildx build \
  --platform linux/arm64 \
  -f docker/cpu/Dockerfile.arm64 \
  -t "${IMAGE_BASE}:${VERSION}-arm64" \
  --load \
  .

# Create and push manifest list
echo "🔗 Creating multi-architecture manifest..."
docker manifest create "${IMAGE_BASE}:${VERSION}" \
  "${IMAGE_BASE}:${VERSION}-amd64" \
  "${IMAGE_BASE}:${VERSION}-arm64"

# Annotate architectures
docker manifest annotate "${IMAGE_BASE}:${VERSION}" \
  "${IMAGE_BASE}:${VERSION}-amd64" --arch amd64
docker manifest annotate "${IMAGE_BASE}:${VERSION}" \
  "${IMAGE_BASE}:${VERSION}-arm64" --arch arm64

echo "✅ Multi-architecture build complete!"
echo "📏 Image sizes:"
docker images "${IMAGE_BASE}" --format "table {{.Repository}}:{{.Tag}}\t{{.Size}}"

# Optionally push (uncomment when ready)
# echo "📤 Pushing manifest list..."
# docker manifest push "${IMAGE_BASE}:${VERSION}"