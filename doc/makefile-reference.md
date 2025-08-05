# Makefile Commands Reference

This document provides a comprehensive reference for all Docker-related Makefile commands in MCP-Ragex.

## Quick Reference

```bash
make help          # Show all available commands
make cpu           # Build CPU development image
make cuda          # Build CUDA development image
make install-cpu   # Build and install CPU image locally
make install-cuda  # Build and install CUDA image locally
make cpu-cicd      # Build CPU image for CI/CD
make publish-cpu   # Build and publish CPU image
make clean         # Clean up Docker artifacts
```

## Development Commands

### Installation Helpers

#### `make install-cpu`
- **Purpose**: Build and install CPU image locally
- **Equivalent**: `make cpu && RAGEX_IMAGE=mcp-ragex:cpu-dev ./install.sh`
- **Output**: Installs `ragex` command with CPU image
- **Requirements**: Docker access
- **Use case**: Quick setup for CPU development

#### `make install-cuda`
- **Purpose**: Build and install CUDA image locally
- **Equivalent**: `make cuda && RAGEX_IMAGE=mcp-ragex:cuda-dev ./install.sh`
- **Output**: Installs `ragex` command with CUDA image
- **Requirements**: Docker access
- **Use case**: Quick setup for GPU development

### Local Image Builds

#### `make cpu`
- **Purpose**: Build CPU image for local development
- **Output**: `mcp-ragex:cpu-dev`
- **Dockerfile**: `docker/cpu/Dockerfile`
- **Requirements**: `requirements/cpu.txt`
- **Platforms**: Current architecture only
- **Use case**: Local CPU development and testing

#### `make cuda`
- **Purpose**: Build CUDA image for local development  
- **Output**: `mcp-ragex:cuda-dev`
- **Dockerfile**: `docker/cuda/Dockerfile`
- **Requirements**: `requirements/cuda.txt`
- **Platforms**: linux/amd64 only
- **Use case**: Local GPU development and testing

## Base Image Commands

### Base Image Builds

#### `make cpu-base`
- **Purpose**: Build CPU base image
- **Output**: `ghcr.io/jbenshetler/mcp-ragex-base:cpu-{version}`
- **Also tags**: `ghcr.io/jbenshetler/mcp-ragex-base:cpu-latest`
- **Dockerfile**: `docker/cpu/Dockerfile.base`
- **Use case**: Create reusable base for CPU applications

#### `make cuda-base`
- **Purpose**: Build CUDA base image
- **Output**: `ghcr.io/jbenshetler/mcp-ragex-base:cuda-{version}`
- **Also tags**: `ghcr.io/jbenshetler/mcp-ragex-base:cuda-latest` 
- **Dockerfile**: `docker/cuda/Dockerfile.base`
- **Use case**: Create reusable base for CUDA applications

### Base Image Publishing

#### `make publish-cpu-base`
- **Purpose**: Build and publish CPU base image
- **Registry**: `ghcr.io/jbenshetler/mcp-ragex-base`
- **Platforms**: linux/amd64, linux/arm64
- **Tags**: `cpu-{version}`, `cpu-latest`
- **Requirements**: GHCR authentication
- **Use case**: Publish base image for reuse

#### `make publish-cuda-base`
- **Purpose**: Build and publish CUDA base image
- **Registry**: `ghcr.io/jbenshetler/mcp-ragex-base`
- **Platforms**: linux/amd64
- **Tags**: `cuda-{version}`, `cuda-latest`
- **Requirements**: GHCR authentication
- **Use case**: Publish CUDA base image for reuse

## CI/CD Commands

### Production Builds

#### `make cpu-cicd`
- **Purpose**: Build CPU image optimized for CI/CD
- **Output**: `ghcr.io/jbenshetler/mcp-ragex:{version}-cpu`
- **Also tags**: `ghcr.io/jbenshetler/mcp-ragex:latest-cpu`
- **Platforms**: linux/amd64, linux/arm64
- **Optimizations**: Multi-stage build, smaller size
- **Use case**: CI/CD pipeline builds

#### `make cuda-cicd`
- **Purpose**: Build CUDA image optimized for CI/CD
- **Output**: `ghcr.io/jbenshetler/mcp-ragex:{version}-cuda`
- **Also tags**: `ghcr.io/jbenshetler/mcp-ragex:latest-cuda`
- **Platforms**: linux/amd64
- **Optimizations**: Multi-stage build, GPU-optimized
- **Use case**: CI/CD pipeline builds (future)

### Image Publishing

#### `make publish-cpu`
- **Purpose**: Build and publish CPU application image
- **Registry**: `ghcr.io/jbenshetler/mcp-ragex`
- **Platforms**: linux/amd64, linux/arm64
- **Tags**: `{version}-cpu`, `latest-cpu`
- **Requirements**: GHCR authentication
- **Use case**: Release CPU version to registry

#### `make publish-cuda`
- **Purpose**: Build and publish CUDA application image
- **Registry**: `ghcr.io/jbenshetler/mcp-ragex`
- **Platforms**: linux/amd64
- **Tags**: `{version}-cuda`, `latest-cuda`
- **Requirements**: GHCR authentication, CUDA support
- **Use case**: Release GPU version to registry (future)

## Utility Commands

### Cleanup

#### `make clean`
- **Purpose**: Clean up build artifacts and cache
- **Actions**: 
  - `docker system prune -f` - Remove unused containers, networks, images
  - `docker buildx prune -f` - Remove build cache
- **Use case**: Free disk space, reset build environment

### Help

#### `make help`
- **Purpose**: Display all available commands with descriptions
- **Format**: Aligned command list with descriptions
- **Use case**: Quick reference and discovery

## Configuration Variables

### Registry Settings
```makefile
REGISTRY := ghcr.io/jbenshetler          # Container registry
IMAGE_NAME := mcp-ragex                  # Main image name
BASE_IMAGE_NAME := mcp-ragex-base        # Base image name
```

### Version Detection
```makefile
VERSION := $(shell git describe --tags --dirty 2>/dev/null || echo "dev")
```
- Uses Git tags for version detection
- Falls back to "dev" for untagged commits
- Appends "-dirty" for uncommitted changes

### Platform Support
```makefile
PLATFORMS_CPU := linux/amd64,linux/arm64    # CPU multi-platform
PLATFORMS_GPU := linux/amd64                # GPU x86_64 only
```

## Common Workflows

### Development Workflow
```bash
# Build and install CPU image
make install-cpu

# Start development daemon
ragex start

# Make code changes - daemon auto-reindexes
ragex search "new code"
```

### GPU Development Workflow
```bash
# Build and install GPU image
make install-cuda

# Start GPU development daemon
ragex start

# Test GPU functionality
ragex start
docker exec ragex_daemon_$(ragex info | grep "Project ID" | cut -d: -f2 | tr -d ' ') nvidia-smi
```

### Release Workflow
```bash
# Tag release
git tag v1.0.0
git push origin v1.0.0

# Build production images
make cpu-cicd

# Publish to registry
make publish-cpu

# Future: GPU release
# make cuda-cicd
# make publish-cuda
```

### Base Image Workflow
```bash
# Build base images
make cpu-base
make cuda-base

# Test base images
docker run --rm ghcr.io/jbenshetler/mcp-ragex-base:cpu-latest python --version

# Publish base images (manual)
make publish-cpu-base
make publish-cuda-base
```

## Troubleshooting

### Build Issues

#### Permission Errors
```bash
# Ensure proper user ID mapping
export UID=$(id -u)
export GID=$(id -g)
make dev
```

#### Build Cache Issues
```bash
# Clear all caches
make clean

# Force rebuild without cache
docker build --no-cache -f docker/cpu/Dockerfile .
```

#### Platform Issues
```bash
# Check available platforms
docker buildx ls

# Force specific platform
docker build --platform linux/amd64 -f docker/cpu/Dockerfile .
```

### Publishing Issues

#### Authentication
```bash
# Login to registry
echo $GHCR_TOKEN | docker login ghcr.io -u jbenshetler --password-stdin

# Verify login
docker info | grep -A 1 Registry
```

#### Network Issues
```bash
# Test registry connectivity
docker pull hello-world
docker tag hello-world ghcr.io/jbenshetler/test:latest
docker push ghcr.io/jbenshetler/test:latest
```

### GPU Issues

#### NVIDIA Docker
```bash
# Test nvidia-docker installation
docker run --rm --gpus all nvidia/cuda:12.1-runtime-ubuntu22.04 nvidia-smi

# Check runtime configuration
docker info | grep -i runtime
```

#### CUDA Version Mismatch
```bash
# Check host CUDA version
nvidia-smi

# Verify container CUDA version
docker run --rm --gpus all ragex/mcp-server:cuda-dev nvidia-smi
```

## Performance Tips

### Build Performance
- **Layer caching**: Order Dockerfile commands by change frequency
- **Multi-stage efficiency**: Keep builder stage minimal
- **Parallel builds**: Use `docker buildx` for multi-platform

### Development Speed  
- **Volume mounts**: Use for live code reloading
- **Development images**: Optimized for rebuild speed
- **Incremental builds**: Only rebuild changed layers

### CI/CD Optimization
- **Build cache**: Use GitHub Actions cache
- **Parallel jobs**: Build CPU and GPU independently  
- **Registry caching**: Pull existing layers when possible

## Environment Variables

### Build-time Variables
- `DOCKER_BUILDKIT=1` - Enable BuildKit features
- `BUILDX_NO_DEFAULT_ATTESTATIONS=1` - Disable attestations
- `DOCKER_BUILDKIT_PROGRESS=plain` - Verbose build output

### Runtime Variables
- `UID=$(id -u)` - User ID for container
- `GID=$(id -g)` - Group ID for container
- `GHCR_TOKEN` - GitHub Container Registry token

## Integration with CI/CD

### GitHub Actions
```bash
# In workflow file
- name: Build CPU image
  run: make cpu-cicd

- name: Publish CPU image  
  run: make publish-cpu
```

### Local CI Testing
```bash
# Simulate CI build locally
make cpu-cicd

# Test published image
docker run --rm ghcr.io/jbenshetler/mcp-ragex:dev-cpu --version
```