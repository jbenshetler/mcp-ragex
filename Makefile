# Variables
REGISTRY := ghcr.io/jbenshetler
IMAGE_NAME := mcp-ragex
BASE_IMAGE_NAME := mcp-ragex-base
# Version management - git tag based
VERSION := $(shell git describe --tags --exact-match 2>/dev/null)
CURRENT_VERSION := $(shell git tag --sort=-version:refname | head -1)
NEXT_PATCH := $(shell git tag --sort=-version:refname | head -1 | sed 's/v//' | awk -F. '{print "v" $$1 "." $$2 "." $$3+1}')
NEXT_MINOR := $(shell git tag --sort=-version:refname | head -1 | sed 's/v//' | awk -F. '{print "v" $$1 "." $$2+1 ".0"}')
BUILD_VERSION := $(shell git describe --tags --dirty 2>/dev/null || echo "dev")
PLATFORMS_CPU := linux/amd64,linux/arm64
PLATFORMS_GPU := linux/amd64

# Architecture support - defaults to amd64
ARCH ?= amd64

# Dependency checking helper
check-base-exists = @docker image inspect $(1) >/dev/null 2>&1 || \
	(echo "❌ Required base image missing: $(1)"; \
	 echo "   Run: make $(2)"; exit 1)

.DEFAULT_GOAL := help

## Base image builds (layered architecture)
cpu-base:      ## Build CPU system base image (ARCH=amd64|arm64)
	docker build \
		-f docker/cpu/Dockerfile.base \
		-t $(IMAGE_NAME):cpu-base \
		-t $(IMAGE_NAME):cpu-$(ARCH)-base \
		. \
		$(NO_CACHE)

arm64-base:    ## Build ARM64 system base image and push to GHCR
	docker buildx build --platform linux/arm64 \
		-f docker/arm64/Dockerfile.base \
		-t $(REGISTRY)/$(IMAGE_NAME):arm64-base-temp \
		--push . \
		$(NO_CACHE)

cpu-ml:        ## Build CPU ML layer (ARCH=amd64|arm64) - requires cpu-base
	$(call check-base-exists,$(IMAGE_NAME):cpu-$(ARCH)-base,cpu-base)
	docker build \
		-f docker/cpu/Dockerfile.ml \
		--build-arg BASE_IMAGE=$(IMAGE_NAME):cpu-$(ARCH)-base \
		-t $(IMAGE_NAME):cpu-ml \
		-t $(IMAGE_NAME):cpu-$(ARCH)-ml \
		. \
		$(NO_CACHE)

arm64-ml:      ## Build ARM64 ML layer (pull base from GHCR, push ML to GHCR)
	docker buildx build --platform linux/arm64 \
		-f docker/arm64/Dockerfile.ml \
		--build-arg BASE_IMAGE=$(REGISTRY)/$(IMAGE_NAME):arm64-base-temp \
		-t $(REGISTRY)/$(IMAGE_NAME):arm64-ml-temp \
		--push . \
		$(NO_CACHE)

cuda-base:     ## Build CUDA system base image
	docker buildx build --platform linux/amd64 \
		-f docker/cuda/Dockerfile.base \
		-t $(IMAGE_NAME):cuda-base \
		-t $(IMAGE_NAME):cuda-amd64-base \
		--load . \
		$(NO_CACHE)

cuda-ml:       ## Build CUDA ML layer - requires cuda-base
	$(call check-base-exists,$(IMAGE_NAME):cuda-base,cuda-base)
	docker build \
		-f docker/cuda/Dockerfile.ml \
		--build-arg BASE_IMAGE=$(IMAGE_NAME):cuda-base \
		-t $(IMAGE_NAME):cuda-ml \
		-t $(IMAGE_NAME):cuda-amd64-ml \
		. \
		$(NO_CACHE)

## Development builds (layered)
cpu:           ## Build CPU image for local development (defaults to AMD64, use ARCH=arm64 for ARM64) - uses layered builds
	@if [ "$(ARCH)" = "arm64" ]; then \
		echo "Routing ARM64 build to dedicated cross-compilation target..."; \
		$(MAKE) arm64; \
	else \
		echo "Building layered CPU image for $(ARCH) (default: AMD64)..."; \
		$(MAKE) cpu-base ARCH=$(ARCH); \
		$(MAKE) cpu-ml ARCH=$(ARCH); \
		docker build \
			-f docker/app/Dockerfile \
			--build-arg BASE_IMAGE=$(IMAGE_NAME):cpu-$(ARCH)-ml \
			-t $(IMAGE_NAME):cpu-dev \
			-t $(IMAGE_NAME):cpu-$(ARCH)-dev \
			-t $(IMAGE_NAME):$(ARCH)-dev \
			. \
			$(NO_CACHE); \
	fi

amd64:         ## Build AMD64 CPU image for local development - uses layered builds
	@echo "Building layered AMD64 CPU image..."
	$(MAKE) cpu-base ARCH=amd64
	$(MAKE) cpu-ml ARCH=amd64
	docker build \
		-f docker/app/Dockerfile \
		--build-arg BASE_IMAGE=$(IMAGE_NAME):cpu-amd64-ml \
		-t $(IMAGE_NAME):cpu-dev \
		-t $(IMAGE_NAME):cpu-amd64-dev \
		-t $(IMAGE_NAME):amd64-dev \
		. \
		$(NO_CACHE)

arm64:         ## Build ARM64 CPU image for local development (registry-based)
	@echo "Building layered ARM64 image via registry..."
	$(MAKE) arm64-base
	$(MAKE) arm64-ml
	docker buildx build --platform linux/arm64 \
		-f docker/app/Dockerfile \
		--build-arg BASE_IMAGE=$(REGISTRY)/$(IMAGE_NAME):arm64-ml-temp \
		-t $(IMAGE_NAME):cpu-dev \
		-t $(IMAGE_NAME):cpu-arm64-dev \
		-t $(IMAGE_NAME):arm64-dev \
		--output type=docker . \
		$(NO_CACHE)

cuda:          ## Build CUDA image for local development (AMD64 only) - uses layered builds
	@echo "Building layered CUDA image for AMD64..."
	$(MAKE) cuda-base
	$(MAKE) cuda-ml
	docker build \
		-f docker/app/Dockerfile \
		--build-arg BASE_IMAGE=$(IMAGE_NAME):cuda-ml \
		-t $(IMAGE_NAME):cuda-dev \
		-t $(IMAGE_NAME):cuda-amd64-dev \
		-t $(IMAGE_NAME):amd64-cuda-dev \
		. \
		$(NO_CACHE)


## Version Management
version-show:    ## Show current version information
	@echo "📊 Version Information:"
	@echo "  Current Version: $(CURRENT_VERSION)"
	@if [ -n "$(VERSION)" ]; then \
		echo "  Tagged Commit:   $(VERSION) ✅"; \
	else \
		echo "  Tagged Commit:   None (use 'make version-patch' or 'make version-minor')"; \
	fi
	@echo "  Next Patch:      $(NEXT_PATCH)"
	@echo "  Next Minor:      $(NEXT_MINOR)"
	@echo "  Build Version:   $(BUILD_VERSION)"
	@echo ""
	@echo "🏷️  Recent Tags:"
	@git tag --sort=-version:refname | head -5

version-patch:   ## Auto-increment patch version (0.3.0 → 0.3.1)
	@if [ -n "$(VERSION)" ]; then \
		echo "❌ Current commit already has version tag: $(VERSION)"; \
		echo "   Cannot create new version on tagged commit"; \
		exit 1; \
	fi
	@git diff --exit-code || (echo "❌ Working tree has uncommitted changes"; exit 1)
	@echo "🏷️  Creating new patch version: $(NEXT_PATCH)"
	git tag $(NEXT_PATCH)
	git push origin $(NEXT_PATCH)
	@echo "✅ Version $(NEXT_PATCH) created and pushed"

version-minor:   ## Auto-increment minor version (0.3.0 → 0.4.0)
	@if [ -n "$(VERSION)" ]; then \
		echo "❌ Current commit already has version tag: $(VERSION)"; \
		echo "   Cannot create new version on tagged commit"; \
		exit 1; \
	fi
	@git diff --exit-code || (echo "❌ Working tree has uncommitted changes"; exit 1)
	@echo "🏷️  Creating new minor version: $(NEXT_MINOR)"
	git tag $(NEXT_MINOR)
	git push origin $(NEXT_MINOR)
	@echo "✅ Version $(NEXT_MINOR) created and pushed"

check-version:   ## Verify clean state and version exists
	@if [ -z "$(VERSION)" ]; then \
		echo "❌ No version tag found on current commit"; \
		echo "   Create one with 'make version-patch' or 'make version-minor'"; \
		exit 1; \
	fi
	@git diff --exit-code || (echo "❌ Working tree has uncommitted changes"; exit 1)
	@if [ "$(FORCE)" != "true" ] && docker manifest inspect $(REGISTRY)/$(IMAGE_NAME):$(VERSION)-cpu >/dev/null 2>&1; then \
		echo "❌ Version $(VERSION) already exists in registry!"; \
		echo "   Use 'make version-patch' to create new version"; \
		echo "   Or use 'make publish-all FORCE=true' to force republish"; \
		exit 1; \
	fi
	@echo "✅ Version $(VERSION) is ready to publish"

## Build All Targets
build-all:       ## Build all platform images locally
	$(MAKE) amd64
	$(MAKE) arm64
	$(MAKE) cuda

## Publishing targets (using 3-layer architecture with cached models)
# Cache control: Set NO_CACHE=true to disable build cache
CACHE_FLAG := $(if $(filter true,$(NO_CACHE)),--no-cache,)

publish-cpu: check-version ## Build and publish CPU images (3-layer: base → ml → app) [NO_CACHE=true to disable cache]
	@echo "🚀 Publishing CPU images for version $(VERSION)..."
	$(if $(filter true,$(NO_CACHE)),@echo "🚫 Build cache disabled",@echo "📦 Using build cache")
	# Build and push CPU base image
	docker build $(CACHE_FLAG) -f docker/cpu/Dockerfile.base \
		-t $(REGISTRY)/$(IMAGE_NAME):$(VERSION)-cpu-base \
		-t $(REGISTRY)/$(IMAGE_NAME):cpu-base-latest .
	docker push $(REGISTRY)/$(IMAGE_NAME):$(VERSION)-cpu-base
	docker push $(REGISTRY)/$(IMAGE_NAME):cpu-base-latest
	# Build and push CPU ML image (with cached models)
	docker build $(CACHE_FLAG) -f docker/cpu/Dockerfile.ml \
		--build-arg BASE_IMAGE=$(REGISTRY)/$(IMAGE_NAME):$(VERSION)-cpu-base \
		-t $(REGISTRY)/$(IMAGE_NAME):$(VERSION)-cpu-ml \
		-t $(REGISTRY)/$(IMAGE_NAME):cpu-ml-latest .
	docker push $(REGISTRY)/$(IMAGE_NAME):$(VERSION)-cpu-ml
	docker push $(REGISTRY)/$(IMAGE_NAME):cpu-ml-latest
	# Build and push CPU application image
	docker build $(CACHE_FLAG) -f docker/app/Dockerfile \
		--build-arg BASE_IMAGE=$(REGISTRY)/$(IMAGE_NAME):$(VERSION)-cpu-ml \
		-t $(REGISTRY)/$(IMAGE_NAME):$(VERSION)-cpu \
		-t $(REGISTRY)/$(IMAGE_NAME):cpu-latest .
	docker push $(REGISTRY)/$(IMAGE_NAME):$(VERSION)-cpu
	docker push $(REGISTRY)/$(IMAGE_NAME):cpu-latest
	@echo "✅ CPU images published for version $(VERSION)"

publish-cuda: check-version ## Build and publish CUDA images (3-layer: base → ml → app) [NO_CACHE=true to disable cache]
	@echo "🚀 Publishing CUDA images for version $(VERSION)..."
	$(if $(filter true,$(NO_CACHE)),@echo "🚫 Build cache disabled",@echo "📦 Using build cache")
	# Build and push CUDA base image
	docker build $(CACHE_FLAG) -f docker/cuda/Dockerfile.base \
		-t $(REGISTRY)/$(IMAGE_NAME):$(VERSION)-cuda-base \
		-t $(REGISTRY)/$(IMAGE_NAME):cuda-base-latest .
	docker push $(REGISTRY)/$(IMAGE_NAME):$(VERSION)-cuda-base
	docker push $(REGISTRY)/$(IMAGE_NAME):cuda-base-latest
	# Build and push CUDA ML image (with cached models)
	docker build $(CACHE_FLAG) -f docker/cuda/Dockerfile.ml \
		--build-arg BASE_IMAGE=$(REGISTRY)/$(IMAGE_NAME):$(VERSION)-cuda-base \
		-t $(REGISTRY)/$(IMAGE_NAME):$(VERSION)-cuda-ml \
		-t $(REGISTRY)/$(IMAGE_NAME):cuda-ml-latest .
	docker push $(REGISTRY)/$(IMAGE_NAME):$(VERSION)-cuda-ml
	docker push $(REGISTRY)/$(IMAGE_NAME):cuda-ml-latest
	# Build and push CUDA application image
	docker build $(CACHE_FLAG) -f docker/app/Dockerfile \
		--build-arg BASE_IMAGE=$(REGISTRY)/$(IMAGE_NAME):$(VERSION)-cuda-ml \
		-t $(REGISTRY)/$(IMAGE_NAME):$(VERSION)-cuda \
		-t $(REGISTRY)/$(IMAGE_NAME):cuda-latest .
	docker push $(REGISTRY)/$(IMAGE_NAME):$(VERSION)-cuda
	docker push $(REGISTRY)/$(IMAGE_NAME):cuda-latest
	@echo "✅ CUDA images published for version $(VERSION)"

publish-arm64: check-version ## Build and publish ARM64-only CPU images (3-layer: base → ml → app) [NO_CACHE=true to disable cache]
	@echo "🚀 Publishing ARM64 CPU images for version $(VERSION)..."
	$(if $(filter true,$(NO_CACHE)),@echo "🚫 Build cache disabled",@echo "📦 Using build cache")
	# Build and push ARM64 CPU base image
	docker buildx build --push --platform linux/arm64 $(CACHE_FLAG) \
		-f docker/cpu/Dockerfile.base \
		-t $(REGISTRY)/$(IMAGE_NAME):$(VERSION)-arm64-base \
		-t $(REGISTRY)/$(IMAGE_NAME):arm64-base-latest .
	# Build and push ARM64 CPU ML image (with cached models)
	docker buildx build --push --platform linux/arm64 $(CACHE_FLAG) \
		-f docker/cpu/Dockerfile.ml \
		--build-arg BASE_IMAGE=$(REGISTRY)/$(IMAGE_NAME):$(VERSION)-arm64-base \
		-t $(REGISTRY)/$(IMAGE_NAME):$(VERSION)-arm64-ml \
		-t $(REGISTRY)/$(IMAGE_NAME):arm64-ml-latest .
	# Build and push ARM64 application image
	docker buildx build --push --platform linux/arm64 $(CACHE_FLAG) \
		-f docker/app/Dockerfile \
		--build-arg BASE_IMAGE=$(REGISTRY)/$(IMAGE_NAME):$(VERSION)-arm64-ml \
		-t $(REGISTRY)/$(IMAGE_NAME):$(VERSION)-arm64 \
		-t $(REGISTRY)/$(IMAGE_NAME):arm64-latest .
	@echo "✅ ARM64 images published for version $(VERSION)"

publish-all: check-version ## Build and publish all platform images [FORCE=true, NO_CACHE=true]
	@echo "🚀 Publishing all images for version $(VERSION)..."
	$(MAKE) publish-cpu FORCE=$(FORCE) NO_CACHE=$(NO_CACHE)
	$(MAKE) publish-cuda FORCE=$(FORCE) NO_CACHE=$(NO_CACHE)
	$(MAKE) publish-arm64 FORCE=$(FORCE) NO_CACHE=$(NO_CACHE)
	@echo "✅ All images published for version $(VERSION)"

release:         ## Complete release workflow (check + build + publish)
	@echo "🎯 Starting release workflow for version $(VERSION)..."
	$(MAKE) check-version
	$(MAKE) build-all
	$(MAKE) publish-all
	@echo "🎉 Release $(VERSION) completed successfully!"
	@echo "📦 Published images:"
	@echo "   - $(REGISTRY)/$(IMAGE_NAME):$(VERSION)-cpu (multi-arch)"
	@echo "   - $(REGISTRY)/$(IMAGE_NAME):$(VERSION)-cuda (amd64)"
	@echo "   - $(REGISTRY)/$(IMAGE_NAME):cpu-latest"
	@echo "   - $(REGISTRY)/$(IMAGE_NAME):cuda-latest"

## Legacy publishing targets (kept for compatibility)
publish-cpu-base:  ## Build and publish CPU base image
	docker buildx build --push --platform $(PLATFORMS_CPU) \
		-f docker/cpu/Dockerfile.base \
		-t $(REGISTRY)/$(BASE_IMAGE_NAME):cpu-$(BUILD_VERSION) \
		-t $(REGISTRY)/$(BASE_IMAGE_NAME):cpu-latest .

publish-cuda-base: ## Build and publish CUDA base image  
	docker buildx build --push --platform $(PLATFORMS_GPU) \
		-f docker/cuda/Dockerfile.base \
		-t $(REGISTRY)/$(BASE_IMAGE_NAME):cuda-$(BUILD_VERSION) \
		-t $(REGISTRY)/$(BASE_IMAGE_NAME):cuda-latest .

## Installation helpers
install:       ## Build and install locally with auto-detection (recommended)
	@echo "🚀 Auto-detecting best build target and installing..."
	@ARCH=$$(uname -m); \
	if [[ "$$ARCH" == "x86_64" ]]; then \
		if command -v nvidia-smi &> /dev/null && docker info | grep -q nvidia; then \
			echo "🔍 Auto-detected: CUDA capability"; \
			$(MAKE) install-cuda; \
		else \
			echo "🔍 Auto-detected: AMD64 CPU"; \
			$(MAKE) install-amd64; \
		fi \
	elif [[ "$$ARCH" == "aarch64" ]] || [[ "$$ARCH" == "arm64" ]]; then \
		echo "🔍 Auto-detected: ARM64 CPU"; \
		$(MAKE) install-arm64; \
	else \
		echo "❌ Unsupported architecture: $$ARCH"; \
		exit 1; \
	fi

install-amd64: ## Build and install AMD64 CPU image locally
	$(MAKE) amd64
	RAGEX_IMAGE=$(IMAGE_NAME):cpu-amd64-dev ./install.sh --cpu $(INSTALL_FLAGS)

install-arm64: ## Build and install ARM64 CPU image locally
	$(MAKE) arm64
	RAGEX_IMAGE=$(IMAGE_NAME):cpu-arm64-dev ./install.sh --cpu $(INSTALL_FLAGS)

install-cpu:   ## Build and install CPU image locally (forces CPU-only, useful for testing)
	@echo "🔧 Forcing CPU-only installation (ignoring GPU availability)..."
	@ARCH=$$(uname -m); \
	if [[ "$$ARCH" == "x86_64" ]]; then \
		$(MAKE) install-amd64; \
	elif [[ "$$ARCH" == "aarch64" ]] || [[ "$$ARCH" == "arm64" ]]; then \
		$(MAKE) install-arm64; \
	else \
		echo "❌ Unsupported architecture: $$ARCH"; \
		exit 1; \
	fi

install-cuda:  ## Build and install CUDA image locally (forces CUDA)
	$(MAKE) cuda
	RAGEX_IMAGE=$(IMAGE_NAME):cuda-dev ./install.sh --cuda $(INSTALL_FLAGS)

## Registry Management
registry-stats:  ## Show registry storage usage and recent versions
	@echo "📊 Registry Statistics:"
	@gh api repos/jbenshetler/mcp-ragex/packages/container/mcp-ragex \
		--jq '{name, visibility, updated_at, download_count}'
	@echo ""
	@echo "📋 Recent Versions (last 10):"
	@gh api repos/jbenshetler/mcp-ragex/packages/container/mcp-ragex/versions \
		--jq '.[:10] | .[] | {name, created_at, size_bytes}'

list-registry:   ## List all published versions
	@echo "📦 All Published Versions:"
	@gh api repos/jbenshetler/mcp-ragex/packages/container/mcp-ragex/versions \
		--jq '.[] | {name, created_at}' | head -20

registry-cleanup: ## Delete versions older than 3 months (protects latest-* tags)
	@echo "🧹 Deleting registry versions older than 3 months..."
	@echo "   (Protecting latest-cpu, latest-cuda, cpu-latest, cuda-latest tags)"
	@gh api repos/jbenshetler/mcp-ragex/packages/container/mcp-ragex/versions \
		--jq '.[] | select(.created_at < "'$(shell date -d '3 months ago' -I)'" and (.name | test("^v[0-9]+\\.[0-9]+\\.[0-9]+") ) and (.name | test("latest") | not)) | .id' | \
		xargs -I {} sh -c 'echo "Deleting version ID: {}"; gh api -X DELETE repos/jbenshetler/mcp-ragex/packages/container/mcp-ragex/versions/{}' || true
	@echo "✅ Registry cleanup completed"

## Utility targets
clean:         ## Clean up build artifacts
	docker system prune -f
	docker buildx prune -f

clean-registry:  ## Clean local registry cache and build artifacts
	@echo "🧹 Cleaning local Docker cache..."
	docker system df
	docker buildx prune -f
	docker builder prune -f
	docker system prune -f

clean-arm64-temp: ## Clean up temporary ARM64 registry tags
	@echo "Cleaning up temporary ARM64 registry tags..."
	@docker manifest inspect $(REGISTRY)/$(IMAGE_NAME):arm64-base-temp > /dev/null 2>&1 && \
		echo "Removing $(REGISTRY)/$(IMAGE_NAME):arm64-base-temp..." || \
		echo "Tag arm64-base-temp not found"
	@docker manifest inspect $(REGISTRY)/$(IMAGE_NAME):arm64-ml-temp > /dev/null 2>&1 && \
		echo "Removing $(REGISTRY)/$(IMAGE_NAME):arm64-ml-temp..." || \
		echo "Tag arm64-ml-temp not found"
	@echo "Note: Use 'gh api repos/OWNER/REPO/packages/container/PACKAGE/versions' to list and delete via GitHub API"

help:          ## Show this help
	@echo "🚀 MCP-RAGex Docker Build System"
	@echo ""
	@echo "🏷️  Version Management:"
	@echo "  make version-patch    # Auto-increment patch (0.3.0 → 0.3.1)"
	@echo "  make version-minor    # Auto-increment minor (0.3.0 → 0.4.0)"
	@echo "  make check-version    # Verify version ready for publishing"
	@echo ""
	@echo "🏗️  Building:"
	@echo "  make amd64            # Build AMD64 CPU image locally"
	@echo "  make arm64            # Build ARM64 CPU image locally"  
	@echo "  make cuda             # Build CUDA image locally"
	@echo "  make cpu              # Build CPU image (defaults to AMD64)"
	@echo "  make build-all        # Build all platform images"
	@echo ""
	@echo "📦 Publishing:"
	@echo "  make release          # Complete release workflow (recommended)"
	@echo "  make publish-all      # Publish all images to GHCR"
	@echo ""
	@echo "🗂️  Registry Management:"
	@echo "  make registry-stats   # Show storage usage"
	@echo "  make list-registry    # List published versions"
	@echo "  make registry-cleanup # Delete old versions (3+ months)"
	@echo ""
	@echo "🛠️  Installation:"
	@echo "  make install          # Auto-detect and install (recommended)"
	@echo "  make install-amd64    # Install AMD64 CPU build"
	@echo "  make install-arm64    # Install ARM64 CPU build"
	@echo "  make install-cpu      # Force CPU-only (ignore GPU)"
	@echo "  make install-cuda     # Force CUDA installation"
	@echo ""
	@echo "🧹 Maintenance:"
	@echo "  make clean            # Clean build artifacts"
	@echo "  make clean-registry   # Clean local Docker cache"
	@echo ""
	@echo "Current Version: $(CURRENT_VERSION) (next patch: $(NEXT_PATCH), next minor: $(NEXT_MINOR))"
	@echo ""
	@echo "📋 All Available Targets:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

.PHONY: version-show version-patch version-minor check-version build-all publish-all release registry-stats list-registry registry-cleanup clean-registry cpu-base arm64-base cpu-ml arm64-ml cuda-base cuda-ml cpu amd64 arm64 cuda publish-cpu-base publish-cuda-base install install-amd64 install-arm64 install-cpu install-cuda clean clean-arm64-temp help