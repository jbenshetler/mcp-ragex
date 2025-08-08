# Enhanced Architecture Targeting and Publishing Plan

This document outlines the enhanced architecture targeting strategy with granular control while preserving multi-platform publishing capabilities.

## Architecture Build Strategy

### Native vs Cross-Compilation Approach

**AMD64 Builds (Native on AMD64 host):**
- Use regular `docker build` for maximum speed
- Native compilation, fastest builds
- Build time: ~8.5min initial, ~30s rebuilds

**ARM64 Builds (Cross-compilation on AMD64 host):**
- Use `docker buildx build --platform linux/arm64` for consistency
- Cross-compilation from AMD64 to ARM64
- Automatic `TARGETARCH` detection ensures correct PyTorch installation
- Build time: ~12-15min initial, ~2-3min rebuilds

**CUDA Builds (Native on AMD64 host):**
- Use regular `docker build` (CUDA requires native)
- AMD64 only (NVIDIA doesn't support ARM64 CUDA)
- Build time: ~8-10min monolithic

## Development Targets

### Core Architecture Targets

```makefile
# Parameterized CPU build (supports AMD64 and ARM64)
cpu:               ## Build CPU image (ARCH=amd64|arm64, default: amd64)
	@if [ "$(ARCH)" = "arm64" ]; then \
		$(MAKE) arm64; \
	else \
		# AMD64 native build using docker build
		$(MAKE) cpu-base ARCH=amd64; \
		$(MAKE) cpu-ml ARCH=amd64; \
		docker build -f docker/app/Dockerfile ...; \
	fi

# ARM64 cross-compilation (uses buildx throughout)
arm64:             ## Build ARM64 CPU image (cross-compiled)
	$(MAKE) arm64-base    # buildx --platform linux/arm64
	$(MAKE) arm64-ml      # buildx --platform linux/arm64  
	docker buildx build --platform linux/arm64 -f docker/app/Dockerfile ...

# CUDA native build
cuda:              ## Build CUDA image (AMD64 only)
	$(MAKE) cuda-base     # docker build (native)
	$(MAKE) cuda-ml       # docker build (native)
	docker build -f docker/app/Dockerfile ...
```

### Explicit Architecture Targets

```makefile
amd64:             ## Build AMD64 CPU image (explicit)
	$(MAKE) cpu ARCH=amd64

cpu-amd64:         ## Build AMD64 CPU image (alias)
	$(MAKE) cpu ARCH=amd64

cpu-arm64:         ## Build ARM64 CPU image (alias)  
	$(MAKE) arm64

cuda-amd64:        ## Build CUDA AMD64 image (alias)
	$(MAKE) cuda
```

## Layer Build Targets

### AMD64 Layers (Native)
```makefile
cpu-base:          ## Build CPU system base (ARCH=amd64|arm64)
	docker build -f docker/cpu/Dockerfile.base \
		-t mcp-ragex:cpu-base \
		-t mcp-ragex:cpu-$(ARCH)-base .

cpu-ml:            ## Build CPU ML layer (ARCH=amd64|arm64) 
	docker build -f docker/cpu/Dockerfile.ml \
		--build-arg BASE_IMAGE=mcp-ragex:cpu-$(ARCH)-base \
		-t mcp-ragex:cpu-ml \
		-t mcp-ragex:cpu-$(ARCH)-ml .
```

### ARM64 Layers (Cross-compile)
```makefile
arm64-base:        ## Build ARM64 system base (cross-compiled)
	docker buildx build --platform linux/arm64 \
		-f docker/arm64/Dockerfile.base \
		-t mcp-ragex:arm64-base --load .

arm64-ml:          ## Build ARM64 ML layer (cross-compiled)
	docker buildx build --platform linux/arm64 \
		-f docker/arm64/Dockerfile.ml \
		--build-arg BASE_IMAGE=mcp-ragex:arm64-base \
		-t mcp-ragex:arm64-ml --load .
```

### CUDA Layers (Native)
```makefile
cuda-base:         ## Build CUDA system base
	docker build -f docker/cuda/Dockerfile.base \
		-t mcp-ragex:cuda-base .

cuda-ml:           ## Build CUDA ML layer  
	docker build -f docker/cuda/Dockerfile.ml \
		--build-arg BASE_IMAGE=mcp-ragex:cuda-base \
		-t mcp-ragex:cuda-ml .
```

## Publishing Targets

### Individual Architecture Publishing

```makefile
publish-amd64:     ## Publish AMD64 layered image to GHCR
	$(MAKE) cpu ARCH=amd64
	docker tag mcp-ragex:amd64-dev $(REGISTRY)/$(IMAGE_NAME):latest-cpu-amd64
	docker tag mcp-ragex:amd64-dev $(REGISTRY)/$(IMAGE_NAME):$(VERSION)-cpu-amd64
	docker push $(REGISTRY)/$(IMAGE_NAME):latest-cpu-amd64
	docker push $(REGISTRY)/$(IMAGE_NAME):$(VERSION)-cpu-amd64

publish-arm64:     ## Publish ARM64 layered image to GHCR
	$(MAKE) arm64
	docker tag mcp-ragex:arm64-dev $(REGISTRY)/$(IMAGE_NAME):latest-cpu-arm64
	docker tag mcp-ragex:arm64-dev $(REGISTRY)/$(IMAGE_NAME):$(VERSION)-cpu-arm64
	docker push $(REGISTRY)/$(IMAGE_NAME):latest-cpu-arm64
	docker push $(REGISTRY)/$(IMAGE_NAME):$(VERSION)-cpu-arm64

publish-cuda:      ## Publish CUDA image to GHCR  
	$(MAKE) cuda
	docker tag mcp-ragex:cuda-dev $(REGISTRY)/$(IMAGE_NAME):cuda-amd64
	docker tag mcp-ragex:cuda-dev $(REGISTRY)/$(IMAGE_NAME):$(VERSION)-cuda-amd64
	docker tag mcp-ragex:cuda-dev $(REGISTRY)/$(IMAGE_NAME):cuda-latest
	docker push $(REGISTRY)/$(IMAGE_NAME):cuda-amd64
	docker push $(REGISTRY)/$(IMAGE_NAME):$(VERSION)-cuda-amd64
	docker push $(REGISTRY)/$(IMAGE_NAME):cuda-latest
```

### Multi-Platform Publishing (Enhanced)

```makefile
publish-cpu:       ## Build and publish CPU images (multi-platform)
	# Use fast layered builds instead of buildx rebuild
	$(MAKE) publish-amd64
	$(MAKE) publish-arm64
	# Create multi-platform manifest
	docker manifest create $(REGISTRY)/$(IMAGE_NAME):latest-cpu \
		$(REGISTRY)/$(IMAGE_NAME):latest-cpu-amd64 \
		$(REGISTRY)/$(IMAGE_NAME):latest-cpu-arm64
	docker manifest push $(REGISTRY)/$(IMAGE_NAME):latest-cpu

publish:           ## Publish all architectures
	$(MAKE) publish-cpu
	$(MAKE) publish-cuda
	# Create comprehensive manifest  
	docker manifest create $(REGISTRY)/$(IMAGE_NAME):latest \
		$(REGISTRY)/$(IMAGE_NAME):latest-cpu-amd64 \
		$(REGISTRY)/$(IMAGE_NAME):latest-cpu-arm64 \
		$(REGISTRY)/$(IMAGE_NAME):cuda-amd64
	docker manifest push $(REGISTRY)/$(IMAGE_NAME):latest
```

### Base Layer Publishing (Optional)

```makefile
publish-base-amd64:    ## Publish AMD64 base layer
	$(MAKE) cpu-base ARCH=amd64
	docker tag mcp-ragex:cpu-amd64-base $(REGISTRY)/$(IMAGE_NAME):cpu-base-amd64-$(VERSION)
	docker push $(REGISTRY)/$(IMAGE_NAME):cpu-base-amd64-$(VERSION)

publish-base-arm64:    ## Publish ARM64 base layer
	$(MAKE) arm64-base
	docker tag mcp-ragex:arm64-base $(REGISTRY)/$(IMAGE_NAME):cpu-base-arm64-$(VERSION)
	docker push $(REGISTRY)/$(IMAGE_NAME):cpu-base-arm64-$(VERSION)

publish-base-cuda:     ## Publish CUDA base layer
	$(MAKE) cuda-base
	docker tag mcp-ragex:cuda-base $(REGISTRY)/$(IMAGE_NAME):cuda-base-$(VERSION)
	docker push $(REGISTRY)/$(IMAGE_NAME):cuda-base-$(VERSION)
```

## Usage Examples

### Development Workflow

**Build specific architectures:**
```bash
make amd64           # AMD64 native (~8.5min first, 30s rebuild)
make arm64           # ARM64 cross-compile (~15min first, 2min rebuild)
make cuda            # CUDA native (~8min)

# Parameterized approach  
make cpu             # AMD64 default
make cpu ARCH=amd64  # AMD64 explicit
make cpu ARCH=arm64  # ARM64 (calls make arm64)
```

**Layer-by-layer building:**
```bash
# AMD64 layers (native)
make cpu-base ARCH=amd64
make cpu-ml ARCH=amd64

# ARM64 layers (cross-compile)
make arm64-base
make arm64-ml

# CUDA layers (native)
make cuda-base  
make cuda-ml
```

### Publishing Workflow

**Individual architecture publishing:**
```bash
make publish-amd64   # ~30s (uses cached layered build)
make publish-arm64   # ~30s (uses cached layered build)
make publish-cuda    # ~30s (uses cached build)
```

**Multi-platform publishing:**
```bash
make publish-cpu     # AMD64 + ARM64 + manifest (~1min)
make publish         # All architectures + comprehensive manifest (~2min)
```

**Selective publishing for time constraints:**
```bash
# Quick AMD64 only (30s)
make publish-amd64

# Quick multi-platform CPU (1min)  
make publish-cpu

# Full suite (2min)
make publish
```

## Performance Characteristics

### Build Times

| Architecture | Initial Build | Rebuild (Code) | Rebuild (Deps) |
|-------------|---------------|----------------|----------------|
| **AMD64 (Native)** | 8.5 min | 30s | 4-5 min |
| **ARM64 (Cross-compile)** | 12-15 min | 2-3 min | 6-8 min |
| **CUDA (Native)** | 8-10 min | 2 min | 6-8 min |

### Publishing Times

| Target | Time | Description |
|--------|------|-------------|
| `publish-amd64` | ~30s | Uses cached layered build + push |
| `publish-arm64` | ~30s | Uses cached layered build + push |
| `publish-cuda` | ~30s | Uses cached build + push |
| `publish-cpu` | ~1min | Both CPU archs + manifest |
| `publish` | ~2min | All architectures + manifests |

## Architecture Detection Benefits

### Automatic TARGETARCH with buildx
```dockerfile
# docker/cpu/Dockerfile.ml (works with both approaches)
ARG TARGETARCH
RUN set -e; \
    echo "Building ML layer for architecture: ${TARGETARCH:-unknown}"; \
    if [ "$TARGETARCH" = "amd64" ] || [ -z "$TARGETARCH" ]; then \
      echo "Installing AMD64 CPU-only PyTorch..."; \
      pip install --no-cache-dir -r requirements/cpu-amd64.txt; \
    elif [ "$TARGETARCH" = "arm64" ]; then \
      echo "Installing ARM64 PyTorch..."; \
      pip install --no-cache-dir -r requirements/cpu-arm64.txt; \
    fi
```

**AMD64 Flow:**
- `docker build` → `TARGETARCH` empty → defaults to AMD64 path ✅
- Installs `torch==2.1.2+cpu` (CPU-optimized, 1.6GB) ✅

**ARM64 Flow:**
- `docker buildx build --platform linux/arm64` → `TARGETARCH=arm64` ✅  
- Installs `torch==2.1.2` (regular PyTorch, ~4GB) ✅

## Registry Structure

### Published Image Tags

**Individual Architecture Tags:**
```
ghcr.io/user/mcp-ragex:latest-cpu-amd64     # AMD64 layered build
ghcr.io/user/mcp-ragex:latest-cpu-arm64     # ARM64 layered build  
ghcr.io/user/mcp-ragex:cuda-amd64           # CUDA build
ghcr.io/user/mcp-ragex:cuda-latest          # CUDA (alias)
```

**Multi-Platform Manifests:**
```
ghcr.io/user/mcp-ragex:latest-cpu           # AMD64 + ARM64 manifest
ghcr.io/user/mcp-ragex:latest               # All architectures manifest
```

**Versioned Tags:**
```
ghcr.io/user/mcp-ragex:v1.0.0-cpu-amd64
ghcr.io/user/mcp-ragex:v1.0.0-cpu-arm64
ghcr.io/user/mcp-ragex:v1.0.0-cuda-amd64
```

## Implementation Benefits

### Technical Benefits
- **Cross-platform support** without ARM64 hardware
- **Optimized PyTorch** for each architecture (CPU-only vs regular)
- **Fast rebuilds** through layered caching
- **Consistent tooling** per architecture (buildx for ARM64, docker for native)

### Operational Benefits  
- **Granular control** - build/publish exactly what you need
- **Time flexibility** - quick publishes when in hurry, comprehensive when time permits
- **Multi-platform users** can pull appropriate architecture automatically
- **CI/CD ready** - clear targets for automation

### Maintenance Benefits
- **Clear architecture separation** in build logic
- **Preserved multi-platform** publishing for compatibility  
- **Tool consistency** - each architecture uses optimal build approach
- **Future extensible** - easy to add new architectures or optimize further

This enhanced approach provides the granular control requested while leveraging the strengths of each build tool for their optimal use cases.