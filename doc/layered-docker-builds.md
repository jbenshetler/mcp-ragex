# Layered Docker Builds for Cloud Efficiency

This document outlines the architecture for layered Docker builds optimized for cloud environments with specific constraints for build time (<10 minutes) and memory usage (<14GB).

## Overview

The layered build strategy maximizes Docker layer caching while supporting multiple architectures (AMD64, ARM64) and compute targets (CPU, CUDA) efficiently.

## Constraints

- **Build Time**: <10 minutes per image build
- **Memory Usage**: <14GB RAM during build
- **Architecture Support**: AMD64, ARM64
- **Compute Targets**: CPU-only, CUDA GPU

## Current Image Size Reference

- **CPU AMD64**: ~1.6GiB (`torch+cpu` optimized)
- **CPU ARM64**: ~4GiB (`torch` regular build, necessary)
- **CUDA**: ~8-12GiB (estimated with CUDA runtime)

## Layer Architecture Strategy

### Layer 1: Base System Layer (~500MB, 2-3min)

**File**: `docker/base/Dockerfile.system`

```dockerfile
FROM python:3.11-slim

# System dependencies shared across all variants
RUN apt-get update && apt-get install -y \
    ripgrep \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Create user and directories
RUN useradd -m -s /bin/bash appuser
WORKDIR /app
USER appuser
```

**Purpose**: Shared system dependencies and user setup across all variants.

### Layer 2A: CPU Base Layer (~2.5GiB, 4-5min)

**File**: `docker/cpu/Dockerfile.base`

```dockerfile
ARG TARGETARCH
FROM ghcr.io/user/mcp-ragex:system-base

# Copy requirements files
COPY requirements/ /tmp/requirements/

# Install PyTorch based on architecture using requirements files
RUN if [ "$TARGETARCH" = "amd64" ]; then \
      pip install --no-cache-dir -r /tmp/requirements/cpu-amd64.txt; \
    else \
      pip install --no-cache-dir -r /tmp/requirements/cpu-arm64.txt; \
    fi

# Install core ML dependencies
RUN pip install --no-cache-dir -r /tmp/requirements/base-ml.txt
```

**Purpose**: CPU-optimized PyTorch and ML dependencies with architecture-specific optimization.

### Layer 2B: CUDA Base Layer (~8GiB, 6-8min)

**File**: `docker/cuda/Dockerfile.base`

```dockerfile
FROM nvidia/cuda:11.8-runtime-ubuntu20.04

# Install Python and system deps
RUN apt-get update && apt-get install -y \
    python3.11 python3.11-pip python3.11-dev \
    ripgrep curl git \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install CUDA dependencies
COPY requirements/ /tmp/requirements/
RUN pip install --no-cache-dir -r /tmp/requirements/cuda.txt
RUN pip install --no-cache-dir -r /tmp/requirements/base-ml.txt

RUN useradd -m -s /bin/bash appuser
WORKDIR /app
USER appuser
```

**Purpose**: CUDA runtime with GPU-accelerated PyTorch and ML dependencies.

### Layer 3: Application Layer (~200MB, 1-2min)

**File**: `docker/app/Dockerfile`

```dockerfile
ARG BASE_IMAGE
FROM ${BASE_IMAGE}

# Copy application code
COPY --chown=appuser:appuser src/ ./src/
COPY --chown=appuser:appuser requirements/app.txt /tmp/

# Install app-specific dependencies
RUN pip install --no-cache-dir -r /tmp/app.txt

# Copy entrypoint
COPY --chown=appuser:appuser docker/common/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
```

**Purpose**: Application code and lightweight runtime dependencies that change frequently.

## Requirements File Strategy

### Directory Structure

```bash
requirements/
├── base-ml.txt           # Heavy ML dependencies (ChromaDB, transformers, etc.)
├── app.txt              # Lightweight app dependencies (MCP, aiofiles, etc.)
├── cpu-amd64.txt        # CPU PyTorch for AMD64
├── cpu-arm64.txt        # Regular PyTorch for ARM64
├── cuda.txt             # CUDA PyTorch
├── dev.txt              # Development dependencies
├── base-ml.in           # Input file for pip-tools
└── requirements.lock    # Locked versions for production
```

### Core Requirements Files

**requirements/base-ml.txt** (~1.5GiB):
```txt
# Core ML dependencies (architecture-agnostic)
sentence-transformers==2.2.2
transformers==4.36.2
chromadb>=0.4.0
numpy>=1.23.0,<1.24.0
scipy>=1.7.0
scikit-learn>=1.0.0
tree-sitter>=0.22.0
tree-sitter-python>=0.23.0
tree-sitter-javascript>=0.23.0
tree-sitter-typescript>=0.23.0
tqdm>=4.65.0
```

**requirements/app.txt** (~50MB):
```txt
# Lightweight application dependencies
mcp>=0.1.0
pydantic>=2.0
aiofiles
pathspec>=0.11.0
watchdog>=3.0.0
```

**requirements/cpu-amd64.txt**:
```txt
# CPU-only PyTorch installation for AMD64
--extra-index-url https://download.pytorch.org/whl/cpu
torch==2.1.2+cpu
torchvision==0.16.2+cpu

# Include base dependencies
-r base.txt
```

**requirements/cpu-arm64.txt**:
```txt
# Regular PyTorch installation for ARM64 (Apple Silicon)
# CPU-specific builds not available for ARM64
torch==2.1.2
torchvision==0.16.2

# Include base dependencies
-r base.txt
```

**requirements/cuda.txt**:
```txt
# CUDA PyTorch installation
--extra-index-url https://download.pytorch.org/whl/cu118
torch==2.1.2+cu118
torchvision==0.16.2+cu118

# Include base dependencies
-r base.txt
```

## Build Pipeline Design

### GitHub Actions Workflow

**File**: `.github/workflows/docker-build.yml`

```yaml
name: Multi-Architecture Docker Build

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  build-base-layers:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        include:
          - name: system-base
            dockerfile: docker/base/Dockerfile.system
            platforms: linux/amd64,linux/arm64
            max-time: 3
            
          - name: cpu-base-amd64  
            dockerfile: docker/cpu/Dockerfile.base
            platforms: linux/amd64
            max-time: 5
            
          - name: cpu-base-arm64
            dockerfile: docker/cpu/Dockerfile.base  
            platforms: linux/arm64
            max-time: 8
            
          - name: cuda-base
            dockerfile: docker/cuda/Dockerfile.base
            platforms: linux/amd64
            max-time: 8
            
    steps:
      - name: Checkout
        uses: actions/checkout@v4
        
      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3
        
      - name: Log in to GitHub Container Registry
        uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}
          
      - name: Build and push base layer
        uses: docker/build-push-action@v5
        with:
          context: .
          file: ${{ matrix.dockerfile }}
          platforms: ${{ matrix.platforms }}
          push: true
          tags: ghcr.io/${{ github.repository }}:${{ matrix.name }}
          cache-from: type=gha
          cache-to: type=gha,mode=max
          build-args: |
            TARGETARCH=${{ matrix.platforms == 'linux/arm64' && 'arm64' || 'amd64' }}

  build-final-images:
    needs: build-base-layers
    runs-on: ubuntu-latest
    strategy:
      matrix:
        include:
          - name: cpu-latest
            base-image: ghcr.io/${{ github.repository }}:cpu-base-amd64
            platforms: linux/amd64
            
          - name: cpu-arm64  
            base-image: ghcr.io/${{ github.repository }}:cpu-base-arm64
            platforms: linux/arm64
            
          - name: cuda-latest
            base-image: ghcr.io/${{ github.repository }}:cuda-base
            platforms: linux/amd64
            
    steps:
      - name: Checkout
        uses: actions/checkout@v4
        
      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3
        
      - name: Log in to GitHub Container Registry
        uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}
          
      - name: Build and push final image
        uses: docker/build-push-action@v5
        with:
          context: .
          file: docker/app/Dockerfile
          platforms: ${{ matrix.platforms }}
          push: true
          tags: ghcr.io/${{ github.repository }}:${{ matrix.name }}
          build-args: BASE_IMAGE=${{ matrix.base-image }}
          cache-from: type=gha
          cache-to: type=gha,mode=max

  create-manifests:
    needs: build-final-images
    runs-on: ubuntu-latest
    steps:
      - name: Log in to GitHub Container Registry
        uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}
          
      - name: Create CPU multi-platform manifest
        run: |
          docker manifest create ghcr.io/${{ github.repository }}:cpu-latest \
            ghcr.io/${{ github.repository }}:cpu-latest \
            ghcr.io/${{ github.repository }}:cpu-arm64
          docker manifest push ghcr.io/${{ github.repository }}:cpu-latest
```

## Makefile Integration

**Enhanced Makefile** with layered build support:

```makefile
# Variables for layered builds
REGISTRY := ghcr.io/jbenshetler
IMAGE_NAME := mcp-ragex
ARCH ?= amd64

# Base layer builds (run once, cached for weeks)
build-base-system:      ## Build system base layer (multi-platform)
	docker buildx build --platform linux/amd64,linux/arm64 \
		-f docker/base/Dockerfile.system \
		-t $(REGISTRY)/$(IMAGE_NAME):system-base \
		--push .

build-base-cpu:         ## Build CPU base layers (both architectures)
	docker buildx build --platform linux/amd64 \
		-f docker/cpu/Dockerfile.base \
		-t $(REGISTRY)/$(IMAGE_NAME):cpu-base-amd64 \
		--push .
	docker buildx build --platform linux/arm64 \
		-f docker/cpu/Dockerfile.base \
		-t $(REGISTRY)/$(IMAGE_NAME):cpu-base-arm64 \
		--push .

build-base-cuda:        ## Build CUDA base layer
	docker buildx build --platform linux/amd64 \
		-f docker/cuda/Dockerfile.base \
		-t $(REGISTRY)/$(IMAGE_NAME):cuda-base \
		--push .

build-all-bases:        ## Build all base layers
	$(MAKE) build-base-system
	$(MAKE) build-base-cpu  
	$(MAKE) build-base-cuda

# Fast application builds (2-3min, frequent)
cpu:                    ## Build CPU image for development (ARCH=amd64|arm64)
	docker buildx build \
		--build-arg BASE_IMAGE=$(REGISTRY)/$(IMAGE_NAME):cpu-base-$(ARCH) \
		-f docker/app/Dockerfile \
		-t $(IMAGE_NAME):cpu-dev \
		-t $(IMAGE_NAME):cpu-$(ARCH)-dev \
		-t $(IMAGE_NAME):$(ARCH)-dev \
		--load .

cuda:                   ## Build CUDA image for development (AMD64 only)
	docker buildx build \
		--build-arg BASE_IMAGE=$(REGISTRY)/$(IMAGE_NAME):cuda-base \
		--platform linux/amd64 \
		-f docker/app/Dockerfile \
		-t $(IMAGE_NAME):cuda-dev \
		-t $(IMAGE_NAME):cuda-amd64-dev \
		-t $(IMAGE_NAME):amd64-cuda-dev \
		--load .

# Production builds
publish-cpu:            ## Build and publish CPU images (multi-platform)
	# AMD64 build with multiple tags
	docker buildx build \
		--build-arg BASE_IMAGE=$(REGISTRY)/$(IMAGE_NAME):cpu-base-amd64 \
		--platform linux/amd64 \
		-f docker/app/Dockerfile \
		-t $(REGISTRY)/$(IMAGE_NAME):latest-cpu-amd64 \
		-t $(REGISTRY)/$(IMAGE_NAME):$(VERSION)-cpu-amd64 \
		--push .
	# ARM64 build with multiple tags
	docker buildx build \
		--build-arg BASE_IMAGE=$(REGISTRY)/$(IMAGE_NAME):cpu-base-arm64 \
		--platform linux/arm64 \
		-f docker/app/Dockerfile \
		-t $(REGISTRY)/$(IMAGE_NAME):latest-cpu-arm64 \
		-t $(REGISTRY)/$(IMAGE_NAME):$(VERSION)-cpu-arm64 \
		--push .
	# Create multi-platform manifest
	docker manifest create $(REGISTRY)/$(IMAGE_NAME):latest-cpu \
		$(REGISTRY)/$(IMAGE_NAME):latest-cpu-amd64 \
		$(REGISTRY)/$(IMAGE_NAME):latest-cpu-arm64
	docker manifest push $(REGISTRY)/$(IMAGE_NAME):latest-cpu

publish-cuda:           ## Build and publish CUDA image
	docker buildx build \
		--build-arg BASE_IMAGE=$(REGISTRY)/$(IMAGE_NAME):cuda-base \
		--platform linux/amd64 \
		-f docker/app/Dockerfile \
		-t $(REGISTRY)/$(IMAGE_NAME):cuda-amd64 \
		-t $(REGISTRY)/$(IMAGE_NAME):$(VERSION)-cuda-amd64 \
		-t $(REGISTRY)/$(IMAGE_NAME):cuda-latest \
		--push .

help:                   ## Show this help
	@echo "Layered Docker Build System"
	@echo ""
	@echo "Base Layers (build once, cache for weeks):"
	@echo "  make build-base-system    # System dependencies (500MB, 3min)"
	@echo "  make build-base-cpu       # CPU PyTorch layers (2.5-4GiB, 5-8min)"
	@echo "  make build-base-cuda      # CUDA PyTorch layer (8GiB, 8min)"
	@echo "  make build-all-bases      # Build all base layers"
	@echo ""
	@echo "Development Builds (fast, 2-3min):"
	@echo "  make cpu                  # CPU development image (AMD64)"
	@echo "  make cpu ARCH=arm64       # CPU development image (ARM64)"  
	@echo "  make cuda                 # CUDA development image (AMD64 only)"
	@echo ""
	@echo "Production Builds:"
	@echo "  make publish-cpu          # Multi-platform CPU images"
	@echo "  make publish-cuda         # CUDA production image"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'
```

## Docker Tagging Strategy

### Multi-Tag Strategy for Architecture Differentiation

The build system uses a multi-tag strategy to provide multiple ways to reference the same image while maintaining backward compatibility.

#### Development Build Tags

Each development build receives multiple tags:

**CPU AMD64 build** (`make cpu` or `make cpu ARCH=amd64`):
- `mcp-ragex:cpu-dev` (backward compatible, latest built)
- `mcp-ragex:cpu-amd64-dev` (architecture-specific)
- `mcp-ragex:amd64-dev` (short form)

**CPU ARM64 build** (`make cpu ARCH=arm64`):
- `mcp-ragex:cpu-dev` (backward compatible, latest built)  
- `mcp-ragex:cpu-arm64-dev` (architecture-specific)
- `mcp-ragex:arm64-dev` (short form)

**CUDA AMD64 build** (`make cuda`):
- `mcp-ragex:cuda-dev` (backward compatible)
- `mcp-ragex:cuda-amd64-dev` (architecture-specific)
- `mcp-ragex:amd64-cuda-dev` (short form with compute type)

#### Production Build Tags

**Platform-specific tags**:
- `ghcr.io/user/mcp-ragex:latest-cpu-amd64`
- `ghcr.io/user/mcp-ragex:latest-cpu-arm64`
- `ghcr.io/user/mcp-ragex:cuda-amd64`

**Multi-platform manifest tags**:
- `ghcr.io/user/mcp-ragex:latest-cpu` (automatically pulls correct architecture)

### Architecture and ARCH Parameter Usage

#### CPU Builds
```bash
make cpu              # CPU AMD64 (default, uses ARCH=amd64)
make cpu ARCH=arm64   # CPU ARM64 (Apple Silicon)
```

#### CUDA Builds
```bash
make cuda             # CUDA AMD64 (ARCH parameter not needed/ignored)
```

**Note**: CUDA is only available on AMD64 architecture. NVIDIA doesn't provide ARM64 CUDA support in their official Docker images.

### Usage Examples

#### Running Images by Tag

```bash
# Backward compatible - runs latest built image
docker run mcp-ragex:cpu-dev

# Architecture-specific selection
docker run mcp-ragex:cpu-amd64-dev      # Explicitly AMD64 CPU
docker run mcp-ragex:cpu-arm64-dev      # Explicitly ARM64 CPU
docker run mcp-ragex:cuda-amd64-dev     # CUDA build

# Short form tags
docker run mcp-ragex:amd64-dev          # AMD64 CPU (short)
docker run mcp-ragex:arm64-dev          # ARM64 CPU (short)
docker run mcp-ragex:amd64-cuda-dev     # CUDA (short with compute type)
```

#### Local Image Listing

```bash
$ docker images mcp-ragex
REPOSITORY   TAG              IMAGE ID     SIZE
mcp-ragex    cpu-dev          abc123       1.6GB  # Latest (AMD64 in this case)
mcp-ragex    cpu-amd64-dev    abc123       1.6GB  # Same image, arch-specific tag
mcp-ragex    amd64-dev        abc123       1.6GB  # Same image, short tag
mcp-ragex    cpu-arm64-dev    def456       4.0GB  # ARM64 build
mcp-ragex    arm64-dev        def456       4.0GB  # Same image, short tag
mcp-ragex    cuda-amd64-dev   xyz789       8.0GB  # CUDA build
```

## Cloud Build Optimization

### Build Time Estimates

| Layer | Build Time | Size | Frequency |
|-------|------------|------|-----------|
| System Base | 2-3 minutes | ~500MB | Weekly |
| CPU Base AMD64 | 4-5 minutes | ~2.5GiB | Weekly |
| CPU Base ARM64 | 6-8 minutes | ~4GiB | Weekly |
| CUDA Base | 6-8 minutes | ~8GiB | Weekly |
| Application Layer | 1-2 minutes | ~200MB | Every commit |

**Total per variant**: 6-10 minutes ✅ (under 10min limit)

### Memory Usage During Builds

| Build Phase | RAM Usage | Peak |
|-------------|-----------|------|
| System Layer | ~1GB | 1GB |
| ML Dependencies | ~4GB | 4GB |
| CUDA Layer | ~6GB | 8GB |
| Application | ~2GB | 2GB |

**Peak per build**: 8-12GB ✅ (under 14GB limit)

### Cache Strategy

1. **Base Layers**: 
   - Rebuilt weekly or on dependency changes
   - Cached in GitHub Container Registry
   - Shared across all application builds

2. **Application Layer**: 
   - Rebuilt on every code change
   - Fast builds due to small size and layer caching

3. **GitHub Actions Cache**: 
   - Aggressive caching between runs using `type=gha`
   - Separate cache keys for each base layer

4. **Registry Cache**: 
   - Base images pulled from GHCR
   - Multi-stage build optimization

## Development Workflow

### Local Development

```bash
# Pull base images once
docker pull ghcr.io/user/mcp-ragex:cpu-base-amd64
docker pull ghcr.io/user/mcp-ragex:cpu-base-arm64
docker pull ghcr.io/user/mcp-ragex:cuda-base

# Fast development builds (2-3 minutes)
make cpu              # AMD64: Creates cpu-dev, cpu-amd64-dev, amd64-dev tags
make cpu ARCH=arm64   # ARM64: Creates cpu-dev, cpu-arm64-dev, arm64-dev tags  
make cuda             # CUDA: Creates cuda-dev, cuda-amd64-dev, amd64-cuda-dev tags

# Use specific tags to run the right architecture
docker run mcp-ragex:cpu-amd64-dev    # Always AMD64
docker run mcp-ragex:cpu-arm64-dev    # Always ARM64
docker run mcp-ragex:cuda-amd64-dev   # CUDA build
```

### Dependency Updates

```bash
# Update ML dependencies (rebuilds base layers)
pip-compile requirements/base-ml.in
git commit -m "Update ML dependencies"
# Triggers base layer rebuilds in CI

# Update app dependencies (fast rebuilds)  
edit requirements/app.txt
git commit -m "Update app dependencies"
# Only rebuilds application layer
```

### Production Deployment

```bash
# Automated via GitHub Actions on main branch
git push origin main

# Manual production builds
make publish-cpu      # Multi-platform CPU
make publish-cuda     # CUDA GPU
```

## Benefits

1. **Fast Development Cycles**: 2-3 minute application builds
2. **Cloud Efficiency**: All builds complete under 10 minutes, 14GB RAM
3. **Cache Optimization**: Base layers cached for weeks
4. **Multi-Architecture**: Native ARM64 and AMD64 support
5. **Architecture Clarity**: Multiple tags for easy architecture identification
6. **Backward Compatibility**: Existing `cpu-dev` and `cuda-dev` tags still work
7. **Dependency Management**: Requirements files for reproducibility
8. **Production Ready**: Automated CI/CD with manifest lists

## File Structure

```
docker/
├── base/
│   └── Dockerfile.system          # System base layer
├── cpu/
│   └── Dockerfile.base           # CPU base layer
├── cuda/
│   └── Dockerfile.base           # CUDA base layer
├── app/
│   └── Dockerfile                # Application layer
└── common/
    └── entrypoint.sh             # Shared entrypoint

requirements/
├── base-ml.txt                   # Heavy ML dependencies
├── app.txt                       # App dependencies
├── cpu-amd64.txt                 # AMD64 CPU PyTorch
├── cpu-arm64.txt                 # ARM64 CPU PyTorch
├── cuda.txt                      # CUDA PyTorch
└── dev.txt                       # Development tools

.github/workflows/
└── docker-build.yml             # CI/CD pipeline

doc/
└── layered-docker-builds.md     # This document
```

This layered architecture provides efficient cloud builds while maintaining fast development cycles and proper dependency management through requirements files.