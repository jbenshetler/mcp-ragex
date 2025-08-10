# Docker Architecture Guide

This document describes the Docker architecture for MCP-Ragex, including multi-platform support (CPU/GPU), development workflows, and CI/CD publishing.

## Architecture Overview

MCP-Ragex uses a structured Docker architecture that separates CPU and GPU builds while following Docker best practices:

```
mcp-ragex/
├── docker/
│   ├── cpu/                        # CPU-only builds
│   │   ├── Dockerfile              # Production CPU image
│   │   └── Dockerfile.base         # Base CPU image
│   ├── cuda/                       # NVIDIA GPU builds
│   │   ├── Dockerfile              # Production CUDA image
│   │   └── Dockerfile.base         # Base CUDA image
│   ├── common/                     # Shared resources
│   │   ├── entrypoint.sh           # Common entrypoint script
│   │   └── .dockerignore           # Common ignore patterns
│   └── compose/                    # Compose file templates
│       ├── docker-compose.base.yml # Common service definitions
│       ├── docker-compose.cpu.yml  # CPU development
│       └── docker-compose.nvidia.yml # NVIDIA GPU development
├── requirements/                   # Platform-specific dependencies
│   ├── base.txt                    # Common Python packages
│   ├── cpu.txt                     # CPU-only PyTorch
│   ├── cuda.txt                    # CUDA PyTorch
│   ├── rocm.txt                    # AMD ROCm PyTorch (future)
│   └── mps.txt                     # Mac Metal PyTorch (future)
├── Makefile                        # Build orchestration
├── docker-compose.yml              # CPU development (default)
├── docker-compose.nvidia.yml       # NVIDIA GPU development
└── .dockerignore                   # Project-level ignores
```

## Image Hierarchy

### Layered Architecture (3-Layer System)

RAGex uses a three-layer Docker architecture for optimal build performance and security:

```
System Base → ML Base → Application Image
     ↓           ↓          ↓
System deps → PyTorch → App code
   (~50MB)   (~1.2GB)   (~50MB)
```

#### Layer 1: System Base Images
- **CPU System Base**: Built from `docker/base/Dockerfile.system`
  - Python 3.10 + system dependencies (ripgrep, git)
  - Non-root user setup and data directories
  - Environment variables for ML frameworks

#### Layer 2: ML Base Images  
- **CPU ML Base**: Built from `docker/cpu/Dockerfile.ml`
  - PyTorch CPU-only + ML dependencies
  - **Pre-bundled fast embedding model** (~90MB)
  - Tree-sitter parsers and other ML tools
  
- **CUDA ML Base**: Built from `docker/cuda/Dockerfile.ml`
  - PyTorch with CUDA support + GPU libraries
  - **Pre-bundled fast embedding model** (~90MB)
  - NVIDIA runtime dependencies

#### Layer 3: Application Images
- **CPU Application**: `ghcr.io/jbenshetler/mcp-ragex:cpu-{version}`
  - Built from `docker/cpu/Dockerfile`
  - Multi-stage build for optimized size
  - Includes application code and dependencies
  - Inherits all ML capabilities from base layers
  
- **CUDA Application**: `ghcr.io/jbenshetler/mcp-ragex:cuda-{version}`
  - Built from `docker/cuda/Dockerfile`
  - GPU-enabled application image
  - Requires nvidia-docker runtime
  - Built on CUDA ML base layer

### Security-Enhanced Model Management

#### Default Model Inclusion
All images include the **fast embedding model** (`all-MiniLM-L6-v2`) by default:
- ✅ **Immediate functionality** - works without network access
- ✅ **Air-gap compatible** - no external dependencies at runtime  
- ✅ **Security by default** - containers can run with `--network none`
- ✅ **Small overhead** - only 90MB addition to 1.2GB ML layer (7.5% increase)

#### Runtime Model Selection
Users can specify different models per project:
```bash
ragex index . --model fast          # Use pre-bundled model (default)
ragex index . --model balanced      # Download if network available
ragex index . --model accurate      # Download if network available
```

#### Network Security Modes
Installation supports different security levels:
```bash
install.sh --cpu                    # Default: network allowed for model downloads
install.sh --cpu --no-network       # High security: no network access ever
```

## PyTorch Platform Support

### CPU-Only (requirements/cpu.txt)
```
--extra-index-url https://download.pytorch.org/whl/cpu
torch==2.1.1+cpu
torchvision==0.16.1+cpu
```
- Works on all platforms (Linux, Mac, Windows containers)
- Smaller image size, faster builds
- No GPU acceleration

### NVIDIA CUDA (requirements/cuda.txt)
```
--extra-index-url https://download.pytorch.org/whl/cu121
torch==2.1.1+cu121
torchvision==0.16.1+cu121
```
- Requires NVIDIA GPU with CUDA 12.1+
- Linux containers only
- GPU acceleration for PyTorch operations

### AMD ROCm (requirements/rocm.txt) - Future
```
--extra-index-url https://download.pytorch.org/whl/rocm6.0
torch==2.1.1+rocm6.0
torchvision==0.16.1+rocm6.0
```
- AMD GPU support on Linux
- Not currently implemented

### Mac Metal (requirements/mps.txt) - Future
```
torch>=2.1.1
torchvision>=0.16.1
```
- Apple M1/M2 GPU acceleration
- Native Mac development (not containerized)

## Build Targets

### Development Images
- Built locally for development
- Include development tools and faster build times
- Tagged as `{image}:cpu-dev` or `{image}:cuda-dev`

### Production Images  
- Multi-stage builds for optimized size
- Built for multiple platforms where supported
- Tagged with version and platform: `{image}:{version}-cpu`

### Base Images
- Provide common layers for application images
- Can be published separately for reuse
- Reduce build times for application images

## Docker Compose Configurations

### CPU Development (docker-compose.yml)
```yaml
# Default development environment
# Uses CPU-only image for broad compatibility
# Most developers should use this
```

### NVIDIA GPU Development (docker-compose.nvidia.yml)
```yaml
# NVIDIA GPU development environment
# Requires nvidia-docker runtime
# For developers with NVIDIA GPUs
```

### Usage
```bash
# CPU development (default)
docker-compose up

# NVIDIA GPU development
docker-compose -f docker-compose.nvidia.yml up
```

## Multi-Platform Builds

### CPU Images
- **Platforms**: `linux/amd64`, `linux/arm64`
- Supports Intel/AMD and ARM64 processors
- Broad compatibility across deployment targets

### GPU Images
- **Platforms**: `linux/amd64` only
- NVIDIA CUDA images are x86_64 specific
- ARM64 CUDA support limited in ecosystem

## File Organization Best Practices

### Dockerfiles
- **Separation**: CPU and GPU builds in separate directories
- **Multi-stage**: Production images use multi-stage builds
- **Base images**: Common layers extracted to base images
- **Security**: Non-root user, minimal attack surface

### Requirements
- **Modular**: Platform-specific requirements inherit from base
- **Explicit**: Pin versions for reproducible builds
- **Indexed**: Use appropriate PyTorch index URLs

### Compose Files
- **Inheritance**: Use extends for common configuration
- **Profiles**: Optional services like indexer
- **Environment**: Flexible configuration via environment variables

## Security Considerations

### Container Security
- **Non-root user**: All containers run as user `ragex` (UID 1000)
- **Read-only workspace**: Source code mounted read-only
- **Resource limits**: Memory and CPU limits in production
- **Minimal base**: Use slim Python images

### Dependency Management
- **Pinned versions**: All dependencies have explicit versions
- **Trusted sources**: Use official PyTorch index URLs
- **Vulnerability scanning**: Regular base image updates

### Runtime Security
- **No privileged**: Containers don't require privileged mode
- **GPU access**: NVIDIA runtime provides controlled GPU access
- **Network isolation**: Default Docker networking

## Performance Considerations

### Build Performance
- **Multi-stage builds**: Separate build and runtime environments
- **Layer caching**: Optimize Dockerfile layer ordering
- **Parallel builds**: Use docker buildx for multi-platform

### Runtime Performance
- **Volume mounts**: Efficient data access patterns
- **GPU memory**: Proper CUDA memory management
- **Image size**: Minimal runtime images

### Development Workflow
- **Fast rebuilds**: Development images optimize for speed
- **Hot reloads**: Volume mounts for live code changes
- **Parallel development**: Multiple developers can work simultaneously

## Troubleshooting

### Common Issues

#### Build Failures
```bash
# Clear build cache
make clean

# Rebuild from scratch
docker buildx prune -f
make cpu
```

#### GPU Access Issues
```bash
# Verify nvidia-docker
docker run --rm --gpus all nvidia/cuda:12.1-runtime-ubuntu22.04 nvidia-smi

# Check runtime configuration
docker info | grep -i runtime
```

#### Permission Issues
```bash
# Set correct user ID
export UID=$(id -u)
export GID=$(id -g)
docker-compose up
```

#### Platform Issues
```bash
# Force platform
docker build --platform linux/amd64 -f docker/cpu/Dockerfile .

# List available platforms
docker buildx ls
```

## Migration from Previous Architecture

### From Single Dockerfile
1. **Backup current setup**: Commit current state
2. **Update references**: Change Dockerfile paths in CI/CD
3. **Test builds**: Verify both CPU and GPU builds work
4. **Update documentation**: Link to this architecture guide

### From Monolithic Requirements
1. **Split dependencies**: Separate CPU/GPU/base requirements
2. **Update Dockerfiles**: Reference new requirements structure  
3. **Test installs**: Verify all platforms install correctly
4. **Update CI/CD**: Use new requirements paths