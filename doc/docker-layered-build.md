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

### Layer 1: System Base Layer (~1GB, 3-4min)

#### CPU System Base
**File**: `docker/cpu/Dockerfile.base`

```dockerfile
FROM python:3.10

# Install minimal required system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    ripgrep \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN useradd -m -u 1000 ragex

WORKDIR /app

# Create data directory
RUN mkdir -p /data && chown -R ragex:ragex /data

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV RAGEX_DATA_DIR=/data
ENV HF_HOME=/data/models
ENV SENTENCE_TRANSFORMERS_HOME=/data/models
ENV DOCKER_CONTAINER=true
ENV RAGEX_LOG_LEVEL=INFO
ENV CUDA_VISIBLE_DEVICES=""

# Switch to non-root user
USER ragex
```

#### CUDA System Base
**File**: `docker/cuda/Dockerfile.base`

```dockerfile
FROM nvidia/cuda:12.1.0-devel-ubuntu22.04

# Install Python and system dependencies
RUN apt-get update && apt-get install -y \
    python3.10 \
    python3.10-dev \
    python3-pip \
    git \
    ripgrep \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Create symlinks for python
RUN ln -sf /usr/bin/python3.10 /usr/bin/python && \
    ln -sf /usr/bin/python3.10 /usr/bin/python3

# Create non-root user
RUN useradd -m -u 1000 ragex

WORKDIR /app

# Create data directory
RUN mkdir -p /data && chown -R ragex:ragex /data

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV RAGEX_DATA_DIR=/data
ENV HF_HOME=/data/models
ENV SENTENCE_TRANSFORMERS_HOME=/data/models
ENV DOCKER_CONTAINER=true
ENV RAGEX_LOG_LEVEL=INFO

# Switch to non-root user
USER ragex
```

**Purpose**: Platform-specific system dependencies, Python environment, and user setup.

### Layer 2: ML Base Layer (~2-8GiB, 4-6min) - WITH CACHED MODELS

#### CPU ML Layer
**File**: `docker/cpu/Dockerfile.ml`

```dockerfile
ARG BASE_IMAGE=scratch
FROM ${BASE_IMAGE}

# Copy requirements files
COPY --chown=ragex:ragex requirements/ ./requirements/

# Install PyTorch and ML dependencies based on architecture using requirements files
ARG TARGETARCH
RUN set -e; \
    echo "Building ML layer for architecture: ${TARGETARCH:-unknown}"; \
    if [ "$TARGETARCH" = "amd64" ] || [ -z "$TARGETARCH" ]; then \
      echo "Installing AMD64 CPU-only PyTorch and ML deps..."; \
      pip install --no-cache-dir --no-warn-script-location -r requirements/cpu-amd64.txt; \
    elif [ "$TARGETARCH" = "arm64" ]; then \
      echo "Installing ARM64 PyTorch and ML deps..."; \
      pip install --no-cache-dir --no-warn-script-location -r requirements/cpu-arm64.txt; \
    else \
      echo "Unsupported architecture: $TARGETARCH"; \
      exit 1; \
    fi

# Install core ML dependencies
RUN pip install --no-cache-dir --no-warn-script-location -r requirements/base-ml.txt

# Pre-download tree-sitter language parsers
RUN python -c "import tree_sitter; import tree_sitter_python as tspython; import tree_sitter_javascript as tsjavascript; import tree_sitter_typescript as tstypescript"

# Pre-download fast embedding model for offline operation
# Switch to root to create directory, then back to ragex
USER root
RUN mkdir -p /opt/models && chown ragex:ragex /opt/models
USER ragex
# Set cache directories to use build-time location
ENV HF_HOME=/opt/models
ENV SENTENCE_TRANSFORMERS_HOME=/opt/models
RUN python -c "from sentence_transformers import SentenceTransformer; print('Downloading fast embedding model for offline operation...'); SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2'); print('Fast model cached successfully!')"
```

#### CUDA ML Layer
**File**: `docker/cuda/Dockerfile.ml`

```dockerfile
ARG BASE_IMAGE=scratch
FROM ${BASE_IMAGE}

# Switch to root to install ML dependencies
USER root

# Copy requirements files
COPY --chown=ragex:ragex requirements/ /tmp/requirements/

# Install CUDA PyTorch and ML dependencies
RUN pip install --no-cache-dir --no-warn-script-location -r /tmp/requirements/cuda.txt
RUN pip install --no-cache-dir --no-warn-script-location -r /tmp/requirements/base-ml.txt

# Pre-download tree-sitter language parsers
RUN python -c "import tree_sitter; import tree_sitter_python as tspython; import tree_sitter_javascript as tsjavascript; import tree_sitter_typescript as tstypescript"

# Pre-download fast embedding model for offline operation
# Create cache directory and set ownership (running as root)
RUN mkdir -p /opt/models && chown ragex:ragex /opt/models
# Set cache directories to use build-time location
ENV HF_HOME=/opt/models
ENV SENTENCE_TRANSFORMERS_HOME=/opt/models
RUN python -c "from sentence_transformers import SentenceTransformer; print('Downloading fast embedding model for offline operation...'); SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2'); print('Fast model cached successfully!')"

# Switch back to non-root user
USER ragex
```

**Purpose**: Platform-specific PyTorch + ML dependencies + **pre-cached embedding models for offline operation**.

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

## Offline Model Caching Strategy

The ML layer (Layer 2) pre-downloads and caches embedding models during build time, enabling completely offline operation:

### Pre-cached Models
- **Fast Model**: `sentence-transformers/all-MiniLM-L6-v2` (~90MB)
- **Cache Location**: `/opt/models` (persistent in image)
- **Runtime Detection**: Application checks `/opt/models` first, then `/data/models`

### Offline Benefits
- ✅ **Immediate functionality** - works without network access
- ✅ **Air-gap compatible** - no external dependencies at runtime  
- ✅ **Security by default** - containers can run with `--network none`
- ✅ **Fast model loading** - no download delays during container startup

### Runtime Model Selection
```bash
ragex index . --model fast          # Use pre-bundled model (default)
ragex index . --model balanced      # Download if network available
ragex index . --model accurate      # Download if network available
```

### Network Security Modes
Installation supports different security levels:
```bash
install.sh --cpu                    # Default: network allowed for model downloads
install.sh --cpu --no-network       # High security: no network access ever
```

### Technical Implementation
The embedding manager tries offline mode first:
```python
# Force offline mode first
os.environ['HF_HUB_OFFLINE'] = '1'
os.environ['TRANSFORMERS_OFFLINE'] = '1'

# Check build-time cache first (/opt/models), then runtime cache (/data/models)
cache_locations = ['/opt/models', '/data/models']
for cache_dir in cache_locations:
    if os.path.exists(cache_dir):
        os.environ['HF_HOME'] = cache_dir
        os.environ['SENTENCE_TRANSFORMERS_HOME'] = cache_dir
        break

model = SentenceTransformer(model_name)  # Loads from cache
```

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

## Build System Integration

The Makefile implements this layered architecture through several key concepts:

### Layer Build Dependencies

Each layer has prerequisites that must be satisfied:
- **Base Layer**: No dependencies (system packages and Python environment)
- **ML Layer**: Requires corresponding base layer image to be built
- **App Layer**: Requires corresponding ML layer image to be built

### Development Workflow

The build system supports fast iterative development:

**Local Development Builds**: 
- `make amd64` - Builds complete 3-layer AMD64 CPU stack locally (base → ml → app)
- `make arm64` - Builds complete 3-layer ARM64 CPU stack locally (base → ml → app)
- `make cuda` - Builds complete 3-layer CUDA stack locally (base → ml → app)
- Each layer is cached, so subsequent builds only rebuild changed layers

**Architecture Selection**:
- AMD64: Explicit `make amd64` target for x86_64 systems
- ARM64: Explicit `make arm64` target for Apple Silicon compatibility
- CUDA: AMD64-only (NVIDIA limitation)
- Legacy: `make cpu` defaults to AMD64 but `make cpu ARCH=arm64` routes to ARM64

### Production Publishing Strategy

Production builds implement proper layer dependency management:

**Incremental Publishing**: Each layer is built and published individually:
1. Base layer published first with version tags
2. ML layer built using published base layer as dependency
3. Application layer built using published ML layer as dependency

**Version Consistency**: All layers for a release share the same version tag:
- `$(REGISTRY)/$(IMAGE_NAME):$(VERSION)-cpu-base`
- `$(REGISTRY)/$(IMAGE_NAME):$(VERSION)-cpu-ml`  
- `$(REGISTRY)/$(IMAGE_NAME):$(VERSION)-cpu`

**Cache Management**: 
- `NO_CACHE=true` parameter disables Docker build cache
- Individual layer caching maximizes reuse between builds
- Registry-based layer sharing across different build environments

### Multi-Platform Support

The build system handles platform differences transparently:

**CPU Builds**: Support both AMD64 and ARM64 through multi-platform buildx
**CUDA Builds**: AMD64-only due to NVIDIA Docker image limitations
**Layer Sharing**: Base system layers can be shared across architectures where possible

### Build Commands

Core build targets follow the layered architecture:
- **Base Commands**: `make cpu-base`, `make cuda-base` (build base layers)
- **ML Commands**: `make cpu-ml`, `make cuda-ml` (build ML layers with models)  
- **App Commands**: `make amd64`, `make arm64`, `make cuda` (build complete application stacks)
- **Publishing**: `make publish-cpu`, `make publish-cuda`, `make publish-all`

This integration ensures that the offline model caching, multi-platform support, and efficient build times are maintained across both development and production environments.

## Docker Tagging Strategy

### Multi-Tag Strategy for Architecture Differentiation

The build system uses a multi-tag strategy to provide multiple ways to reference the same image while maintaining backward compatibility.

#### Development Build Tags

Each development build receives multiple tags:

**AMD64 CPU build** (`make amd64`):
- `mcp-ragex:cpu-dev` (backward compatible, latest built)
- `mcp-ragex:cpu-amd64-dev` (architecture-specific)
- `mcp-ragex:amd64-dev` (short form)

**ARM64 CPU build** (`make arm64`):
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
make amd64            # AMD64 CPU (explicit)
make arm64            # ARM64 CPU (Apple Silicon)
make cpu              # CPU AMD64 (legacy, defaults to amd64)
make cpu ARCH=arm64   # CPU ARM64 (legacy, routes to arm64)
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
make amd64            # AMD64: Creates cpu-dev, cpu-amd64-dev, amd64-dev tags
make arm64            # ARM64: Creates cpu-dev, cpu-arm64-dev, arm64-dev tags  
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

## Installation System

The build system provides comprehensive installation targets with automatic hardware detection:

### Primary Installation Commands

**`make install`** - Recommended for most users. Auto-detects your system:
- **AMD64 with CUDA**: Detects NVIDIA GPU → installs CUDA build
- **AMD64 without CUDA**: Installs optimized AMD64 CPU build  
- **ARM64**: Installs ARM64 CPU build (Apple Silicon compatible)

**Architecture-Specific Installation**:
- `make install-amd64` - Explicit AMD64 CPU installation
- `make install-arm64` - Explicit ARM64 CPU installation
- `make install-cuda` - Force CUDA installation (requires NVIDIA GPU)
- `make install-cpu` - Force CPU-only (useful for testing CUDA systems without GPU)

### Advanced Options

Pass additional flags to the installer:
```bash
# Network-enabled installation with specific model
INSTALL_FLAGS="--network --model balanced" make install

# Force CPU with custom model
INSTALL_FLAGS="--model accurate" make install-cpu
```

Available installer flags:
- `--network` - Enable network access for model downloads
- `--model <name>` - Specify model (fast, balanced, accurate, multilingual)

## Benefits

1. **Fast Development Cycles**: 2-3 minute application builds
2. **Cloud Efficiency**: All builds complete under 10 minutes, 14GB RAM
3. **Cache Optimization**: Base layers cached for weeks
4. **Multi-Architecture**: Native ARM64 and AMD64 support
5. **Architecture Clarity**: Multiple tags for easy architecture identification
6. **Backward Compatibility**: Existing `cpu-dev` and `cuda-dev` tags still work
7. **Dependency Management**: Requirements files for reproducibility
8. **Production Ready**: Automated CI/CD with manifest lists
9. **Smart Installation**: Auto-detection with explicit override options

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