# Layered CI/CD Adaptation Plan

This document outlines the strategy to adapt CI/CD infrastructure to fully utilize the existing layered Docker build architecture.

## Current State Analysis

### Existing Layered Architecture Status

#### CPU Builds (Complete Layering ✅)
- **CPU AMD64**: Base → ML → App (fully implemented)
- **CPU ARM64**: Base → ML → App (fully implemented)
- **Layer sizes**: Base ~519MB, ML ~1.6GB total, App minimal
- **Build time**: 8.5 min total, with excellent caching potential

#### CUDA Builds (Incomplete Layering ❌)
- **CUDA Base**: ✅ Exists (`docker/cuda/Dockerfile.base`)
- **CUDA ML**: ❌ Missing (`docker/cuda/Dockerfile.ml`)
- **CUDA App**: ❌ Currently monolithic multi-stage approach
- **Current**: Single `docker/cuda/Dockerfile` with builder/runtime stages
- **Issue**: No layered caching benefits, still 8+ min builds

### Current CI/CD Issues
- `cpu-cicd` and `cuda-cicd` use monolithic `Dockerfile.conditional` (CPU) and multi-stage (CUDA)
- `publish-cpu` builds everything from scratch (8+ minutes)
- **CUDA not utilizing layered architecture** - missing ML separation
- No base layer publishing/caching strategy
- Missing multi-platform layer coordination

## Layered CI/CD Strategy

### Phase 1: Base Layer Management

**Objective**: Establish cached base layers that rarely need rebuilding

#### 1.1 Base Layer Publishing Targets
```makefile
publish-cpu-base-layered:    ## Build and publish CPU base layers (multi-platform)
	# AMD64 base
	docker buildx build --push --platform linux/amd64 \
		-f docker/cpu/Dockerfile.base \
		-t $(REGISTRY)/$(IMAGE_NAME):cpu-base-amd64-$(VERSION) \
		-t $(REGISTRY)/$(IMAGE_NAME):cpu-base-amd64-latest .
	
	# ARM64 base  
	docker buildx build --push --platform linux/arm64 \
		-f docker/arm64/Dockerfile.base \
		-t $(REGISTRY)/$(IMAGE_NAME):cpu-base-arm64-$(VERSION) \
		-t $(REGISTRY)/$(IMAGE_NAME):cpu-base-arm64-latest .

publish-cuda-base-layered:   ## Build and publish CUDA base layer
	docker buildx build --push --platform linux/amd64 \
		-f docker/cuda/Dockerfile.base \
		-t $(REGISTRY)/$(IMAGE_NAME):cuda-base-$(VERSION) \
		-t $(REGISTRY)/$(IMAGE_NAME):cuda-base-latest .
```

#### 1.2 Base Layer Triggers
- **Manual**: `make publish-cpu-base-layered` when system deps change
- **Automated**: Weekly scheduled build to refresh base images
- **Dependency-triggered**: When `python:3.10` base image updates

### Phase 2: ML Layer Management

**Objective**: Cache ML dependencies separately from app code

#### 2.1 ML Layer Publishing Targets
```makefile
publish-cpu-ml-layered:      ## Build and publish CPU ML layers (multi-platform)
	# AMD64 ML layer (depends on base)
	docker buildx build --push --platform linux/amd64 \
		-f docker/cpu/Dockerfile.ml \
		--build-arg BASE_IMAGE=$(REGISTRY)/$(IMAGE_NAME):cpu-base-amd64-latest \
		-t $(REGISTRY)/$(IMAGE_NAME):cpu-ml-amd64-$(VERSION) \
		-t $(REGISTRY)/$(IMAGE_NAME):cpu-ml-amd64-latest .
	
	# ARM64 ML layer (depends on base)
	docker buildx build --push --platform linux/arm64 \
		-f docker/arm64/Dockerfile.ml \
		--build-arg BASE_IMAGE=$(REGISTRY)/$(IMAGE_NAME):cpu-base-arm64-latest \
		-t $(REGISTRY)/$(IMAGE_NAME):cpu-ml-arm64-$(VERSION) \
		-t $(REGISTRY)/$(IMAGE_NAME):cpu-ml-arm64-latest .

publish-cuda-ml-layered:     ## Build and publish CUDA ML layer
	docker buildx build --push --platform linux/amd64 \
		-f docker/cuda/Dockerfile.ml \
		--build-arg BASE_IMAGE=$(REGISTRY)/$(IMAGE_NAME):cuda-base-latest \
		-t $(REGISTRY)/$(IMAGE_NAME):cuda-ml-$(VERSION) \
		-t $(REGISTRY)/$(IMAGE_NAME):cuda-ml-latest .
```

#### 2.2 ML Layer Triggers
- **Requirements changes**: When `requirements/base-ml.txt`, `requirements/cpu-*.txt`, or `requirements/cuda.txt` change
- **PyTorch updates**: When ML dependencies need updates
- **Manual**: `make publish-cpu-ml-layered` for testing

### Phase 3: Application Layer CI/CD

**Objective**: Fast builds using cached base and ML layers

#### 3.1 Application Layer Publishing Targets
```makefile
publish-cpu-layered:        ## Build and publish CPU application layers (multi-platform)
	# AMD64 application layer
	docker buildx build --push --platform linux/amd64 \
		-f docker/app/Dockerfile \
		--build-arg BASE_IMAGE=$(REGISTRY)/$(IMAGE_NAME):cpu-ml-amd64-latest \
		-t $(REGISTRY)/$(IMAGE_NAME):latest-cpu-amd64 \
		-t $(REGISTRY)/$(IMAGE_NAME):$(VERSION)-cpu-amd64 .
	
	# ARM64 application layer  
	docker buildx build --push --platform linux/arm64 \
		-f docker/app/Dockerfile \
		--build-arg BASE_IMAGE=$(REGISTRY)/$(IMAGE_NAME):cpu-ml-arm64-latest \
		-t $(REGISTRY)/$(IMAGE_NAME):latest-cpu-arm64 \
		-t $(REGISTRY)/$(IMAGE_NAME):$(VERSION)-cpu-arm64 .
	
	# Create multi-platform manifest
	docker manifest create $(REGISTRY)/$(IMAGE_NAME):latest-cpu \
		$(REGISTRY)/$(IMAGE_NAME):latest-cpu-amd64 \
		$(REGISTRY)/$(IMAGE_NAME):latest-cpu-arm64
	docker manifest push $(REGISTRY)/$(IMAGE_NAME):latest-cpu

publish-cuda-layered:       ## Build and publish CUDA application layer
	docker buildx build --push --platform linux/amd64 \
		-f docker/app/Dockerfile \
		--build-arg BASE_IMAGE=$(REGISTRY)/$(IMAGE_NAME):cuda-ml-latest \
		-t $(REGISTRY)/$(IMAGE_NAME):cuda-amd64 \
		-t $(REGISTRY)/$(IMAGE_NAME):$(VERSION)-cuda-amd64 \
		-t $(REGISTRY)/$(IMAGE_NAME):cuda-latest .
```

#### 3.2 Application Layer Triggers
- **Code changes**: Every commit to main branch
- **App dependencies**: When `requirements/app.txt` changes
- **Pull requests**: Build for testing (without publishing)

## GitHub Actions Workflow Strategy

### Workflow 1: Base Layer Maintenance
```yaml
name: Build Base Layers
on:
  schedule:
    - cron: '0 6 * * 1'  # Weekly Monday 6 AM UTC
  workflow_dispatch:     # Manual trigger
  push:
    paths:
      - 'docker/*/Dockerfile.base'
      - 'docker/base/**'

jobs:
  build-base-layers:
    strategy:
      matrix:
        target: [cpu-base-layered, cuda-base-layered]
    steps:
      - name: Build and publish ${{ matrix.target }}
        run: make publish-${{ matrix.target }}
```

### Workflow 2: ML Layer Updates  
```yaml
name: Build ML Layers
on:
  push:
    paths:
      - 'requirements/base-ml.txt'
      - 'requirements/cpu-*.txt'  
      - 'requirements/cuda.txt'
      - 'docker/*/Dockerfile.ml'
  workflow_dispatch:

jobs:
  build-ml-layers:
    needs: [ensure-base-layers]  # Ensure base layers exist
    strategy:
      matrix:
        target: [cpu-ml-layered, cuda-ml-layered]
    steps:
      - name: Build and publish ${{ matrix.target }}
        run: make publish-${{ matrix.target }}
```

### Workflow 3: Application CI/CD (Main)
```yaml
name: Build and Deploy Application
on:
  push:
    branches: [main]
    paths-ignore:
      - 'docker/*/Dockerfile.base'
      - 'requirements/base-ml.txt'
      - 'requirements/cpu-*.txt'
      - 'requirements/cuda.txt'
      - 'docker/*/Dockerfile.ml'

jobs:
  build-app:
    needs: [ensure-ml-layers]  # Ensure ML layers exist
    strategy:
      matrix:
        target: [cpu-layered, cuda-layered]
    steps:
      - name: Build and publish ${{ matrix.target }}
        run: make publish-${{ matrix.target }}
```

## Build Time Optimization Matrix

| Change Type | Layers Rebuilt | Build Time | Frequency |
|-------------|----------------|------------|-----------|
| **Code only** | App | ~1-2 min | Daily |
| **App deps** | ML + App | ~4-5 min | Weekly |
| **ML deps** | ML + App | ~6-8 min | Monthly |
| **System deps** | Base + ML + App | ~8-10 min | Quarterly |
| **Clean build** | Base + ML + App | ~8-10 min | Rare |

## Cache Strategy

### Registry-Based Layer Caching
```bash
# Pull base layers for local development
docker pull ghcr.io/user/mcp-ragex:cpu-base-amd64-latest
docker pull ghcr.io/user/mcp-ragex:cpu-base-arm64-latest
docker pull ghcr.io/user/mcp-ragex:cuda-base-latest

# Pull ML layers for incremental builds  
docker pull ghcr.io/user/mcp-ragex:cpu-ml-amd64-latest
docker pull ghcr.io/user/mcp-ragex:cpu-ml-arm64-latest
docker pull ghcr.io/user/mcp-ragex:cuda-ml-latest
```

### CI/CD Cache Optimization
- **Base layers**: 1-week TTL, rebuilt weekly or on system changes
- **ML layers**: 2-day TTL, rebuilt on ML dependency changes
- **App layers**: No caching needed, built fresh each time

## Implementation Timeline

### Phase 0: Complete CUDA Layering (Week 1)
**Objective**: Bring CUDA build to same layered standard as CPU builds

#### Prerequisites Analysis
Current CUDA build uses monolithic multi-stage approach:
- ✅ `docker/cuda/Dockerfile.base` exists (system layer)
- ❌ Missing `docker/cuda/Dockerfile.ml` (ML layer)
- ❌ `docker/cuda/Dockerfile` is monolithic multi-stage
- ❌ CUDA Makefile targets not using layered approach

#### CUDA Layering Tasks
- [ ] **Create `docker/cuda/Dockerfile.ml`** 
  - Inherit from CUDA base layer
  - Install CUDA PyTorch + ML dependencies
  - Pre-download tree-sitter parsers
- [ ] **Update CUDA Makefile targets**
  - Convert `cuda` target to use layered builds (base → ML → app)
  - Update `cuda-cicd` to use layered approach
  - Ensure CUDA uses same 3-layer pattern as CPU
- [ ] **Test CUDA layered builds**
  - Verify build time improvements
  - Test against monolithic fallback
  - Validate CUDA functionality

#### Expected CUDA Layer Sizes
- **CUDA Base**: ~2GB (NVIDIA runtime + Python + ripgrep)
- **CUDA ML**: ~6GB total (Base + CUDA PyTorch + transformers)  
- **CUDA App**: ~6GB total (ML layer + application code)

#### CUDA Build Time Targets
- **Current monolithic**: 8+ minutes (multi-stage)
- **Target layered**: 
  - Code changes: 1-2 min (app layer only)
  - ML changes: 4-5 min (ML + app layers)
  - System changes: 8-10 min (all layers, rare)

### Phase 1: Makefile Updates (Week 2)
- [ ] Add layered publishing targets for all architectures
- [ ] Update existing CI/CD targets to use layered builds
- [ ] Test layered publishing to GHCR for CPU AMD64, ARM64, and CUDA

### Phase 2: GitHub Actions Migration (Week 3)
- [ ] Create base layer workflow (CPU AMD64, ARM64, CUDA)
- [ ] Create ML layer workflow (CPU AMD64, ARM64, CUDA)
- [ ] Update main CI/CD workflow
- [ ] Add workflow dependencies and triggering

### Phase 3: Testing and Optimization (Week 4)
- [ ] Test full CI/CD pipeline with different change types across all architectures
- [ ] Optimize build times and caching
- [ ] Validate multi-architecture coordination
- [ ] Document new CI/CD processes

### Phase 4: Rollout and Monitoring (Week 5)
- [ ] Deploy to production CI/CD
- [ ] Monitor build times and cache hit rates
- [ ] Update documentation and team processes
- [ ] Performance benchmarking across all architectures

## Success Metrics

### Build Time Improvements (All Architectures)
- **Code changes**: 8+ min → 1-2 min (75% improvement)
- **Dependency changes**: 8+ min → 4-5 min (50% improvement)  
- **Clean builds**: Maintain 8-10 min but with better caching

#### Architecture-Specific Targets
| Architecture | Current | Code Changes | ML Changes | Clean Build |
|--------------|---------|--------------|------------|-------------|
| **CPU AMD64** | 8.5 min | 1-2 min | 4-5 min | 8-10 min |
| **CPU ARM64** | ~10 min | 1-2 min | 5-6 min | 9-11 min |
| **CUDA** | 8+ min | 1-2 min | 4-5 min | 8-10 min |

### Cache Efficiency
- **Base layer reuse**: >95% (rebuild weekly)
- **ML layer reuse**: >80% (rebuild on ML changes)
- **Registry bandwidth**: Reduced by 60% through layer reuse

### Developer Experience
- **Local builds**: Faster with pre-built base layers
- **CI feedback**: Faster feedback loops for code changes
- **Multi-arch support**: Seamless ARM64 and AMD64 builds

## Risk Mitigation

### Fallback Strategy
- Keep existing monolithic targets as backup
- Gradual migration with parallel CI/CD pipelines
- Easy rollback to monolithic builds if needed

### Dependency Management
- Pin base image versions for reproducibility
- Monitor upstream image updates
- Automated security scanning of all layers

### Build Reliability
- Layer availability checks before dependent builds
- Graceful fallback to rebuilding missing layers
- Comprehensive integration testing

## Conclusion

This layered CI/CD approach will:
1. **Reduce build times** by 50-75% for most changes
2. **Improve caching efficiency** through strategic layer management
3. **Enable faster development cycles** with incremental builds
4. **Maintain full multi-architecture support** 
5. **Preserve build reliability** with fallback mechanisms

The implementation focuses on maximizing the benefits of the existing layered architecture while maintaining compatibility and reliability.