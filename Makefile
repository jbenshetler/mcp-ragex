# Variables
REGISTRY := ghcr.io/jbenshetler
IMAGE_NAME := mcp-ragex
BASE_IMAGE_NAME := mcp-ragex-base
VERSION := $(shell git describe --tags --dirty 2>/dev/null || echo "dev")
PLATFORMS_CPU := linux/amd64,linux/arm64
PLATFORMS_GPU := linux/amd64

# Architecture support - defaults to amd64
ARCH ?= amd64

.DEFAULT_GOAL := help

## Base image builds (layered architecture)
cpu-base:      ## Build CPU system base image (ARCH=amd64|arm64)
	docker build \
		-f docker/cpu/Dockerfile.base \
		-t $(IMAGE_NAME):cpu-base \
		-t $(IMAGE_NAME):cpu-$(ARCH)-base \
		. \
		$(NO_CACHE)

arm64-base:    ## Build ARM64 system base image
	docker buildx build --platform linux/arm64 \
		-f docker/arm64/Dockerfile.base \
		-t $(IMAGE_NAME):arm64-base \
		--output type=docker . \
		$(NO_CACHE)

cpu-ml:        ## Build CPU ML layer (ARCH=amd64|arm64)
	docker build \
		-f docker/cpu/Dockerfile.ml \
		--build-arg BASE_IMAGE=$(IMAGE_NAME):cpu-$(ARCH)-base \
		-t $(IMAGE_NAME):cpu-ml \
		-t $(IMAGE_NAME):cpu-$(ARCH)-ml \
		. \
		$(NO_CACHE)

arm64-ml:      ## Build ARM64 ML layer (cross-compiled)
	docker buildx build --platform linux/arm64 \
		-f docker/arm64/Dockerfile.ml \
		--build-arg BASE_IMAGE=$(IMAGE_NAME):arm64-base \
		-t $(IMAGE_NAME):arm64-ml \
		--output type=docker . \
		$(NO_CACHE)

cuda-base:     ## Build CUDA system base image
	docker buildx build --platform linux/amd64 \
		-f docker/cuda/Dockerfile.base \
		-t $(IMAGE_NAME):cuda-base \
		-t $(IMAGE_NAME):cuda-amd64-base \
		--load . \
		$(NO_CACHE)

cuda-ml:       ## Build CUDA ML layer
	docker build \
		-f docker/cuda/Dockerfile.ml \
		--build-arg BASE_IMAGE=$(IMAGE_NAME):cuda-base \
		-t $(IMAGE_NAME):cuda-ml \
		-t $(IMAGE_NAME):cuda-amd64-ml \
		. \
		$(NO_CACHE)

## Development builds (layered)
cpu:           ## Build CPU image for local development (ARCH=amd64|arm64) - uses layered builds
	@if [ "$(ARCH)" = "arm64" ]; then \
		echo "Routing ARM64 build to dedicated cross-compilation target..."; \
		$(MAKE) arm64; \
	else \
		echo "Building layered CPU image for $(ARCH)..."; \
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

arm64:         ## Build ARM64 image for local development (cross-compiled)
	@echo "Building layered ARM64 image (cross-compiled)..."
	$(MAKE) arm64-base
	$(MAKE) arm64-ml
	docker buildx build --platform linux/arm64 \
		-f docker/app/Dockerfile \
		--build-arg BASE_IMAGE=$(IMAGE_NAME):arm64-ml \
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

## CI/CD builds  
cpu-cicd:      ## Build CPU image optimized for CI/CD (multi-platform)
	docker buildx build --platform $(PLATFORMS_CPU) \
		-f docker/cpu/Dockerfile.conditional \
		-t $(REGISTRY)/$(IMAGE_NAME):$(VERSION)-cpu \
		-t $(REGISTRY)/$(IMAGE_NAME):latest-cpu .

cpu-multiarch: ## Build CPU image for multiple architectures locally
	docker buildx build --platform $(PLATFORMS_CPU) \
		-f docker/cpu/Dockerfile.conditional \
		-t $(IMAGE_NAME):cpu-multiarch \
		--load .

cuda-cicd:     ## Build CUDA image optimized for CI/CD
	docker buildx build --platform $(PLATFORMS_GPU) \
		-f docker/cuda/Dockerfile \
		-t $(REGISTRY)/$(IMAGE_NAME):$(VERSION)-cuda \
		-t $(REGISTRY)/$(IMAGE_NAME):latest-cuda .

## Publishing targets
publish-cpu-base:  ## Build and publish CPU base image
	docker buildx build --push --platform $(PLATFORMS_CPU) \
		-f docker/cpu/Dockerfile.base \
		-t $(REGISTRY)/$(BASE_IMAGE_NAME):cpu-$(VERSION) \
		-t $(REGISTRY)/$(BASE_IMAGE_NAME):cpu-latest .

publish-cuda-base: ## Build and publish CUDA base image  
	docker buildx build --push --platform $(PLATFORMS_GPU) \
		-f docker/cuda/Dockerfile.base \
		-t $(REGISTRY)/$(BASE_IMAGE_NAME):cuda-$(VERSION) \
		-t $(REGISTRY)/$(BASE_IMAGE_NAME):cuda-latest .

publish-cpu:   ## Build and publish CPU images (multi-platform)
	# AMD64 build with multiple tags
	docker buildx build --push --platform linux/amd64 \
		-f docker/cpu/Dockerfile.conditional \
		-t $(REGISTRY)/$(IMAGE_NAME):latest-cpu-amd64 \
		-t $(REGISTRY)/$(IMAGE_NAME):$(VERSION)-cpu-amd64 .
	# ARM64 build with multiple tags
	docker buildx build --push --platform linux/arm64 \
		-f docker/cpu/Dockerfile.conditional \
		-t $(REGISTRY)/$(IMAGE_NAME):latest-cpu-arm64 \
		-t $(REGISTRY)/$(IMAGE_NAME):$(VERSION)-cpu-arm64 .
	# Create multi-platform manifest
	docker manifest create $(REGISTRY)/$(IMAGE_NAME):latest-cpu \
		$(REGISTRY)/$(IMAGE_NAME):latest-cpu-amd64 \
		$(REGISTRY)/$(IMAGE_NAME):latest-cpu-arm64
	docker manifest push $(REGISTRY)/$(IMAGE_NAME):latest-cpu

publish-cuda:  ## Build and publish CUDA image (AMD64 only)
	docker buildx build --push --platform linux/amd64 \
		-f docker/cuda/Dockerfile \
		-t $(REGISTRY)/$(IMAGE_NAME):cuda-amd64 \
		-t $(REGISTRY)/$(IMAGE_NAME):$(VERSION)-cuda-amd64 \
		-t $(REGISTRY)/$(IMAGE_NAME):cuda-latest .

## Installation helpers
install-cpu:   ## Build and install CPU image locally
	$(MAKE) cpu
	RAGEX_IMAGE=$(IMAGE_NAME):cpu-dev ./install.sh

install-cuda:  ## Build and install CUDA image locally
	$(MAKE) cuda
	RAGEX_IMAGE=$(IMAGE_NAME):cuda-dev ./install.sh

## Utility targets
clean:         ## Clean up build artifacts
	docker system prune -f
	docker buildx prune -f

help:          ## Show this help
	@echo "Layered Multi-Tag Docker Build System"
	@echo ""
	@echo "Architecture Support:"
	@echo "  ARCH=amd64    Build for AMD64 (default, ~1.6GiB with CPU-only PyTorch)"
	@echo "  ARCH=arm64    Build for ARM64 (~4GiB with regular PyTorch)"
	@echo ""
	@echo "Layered Build Process:"
	@echo "  1. System Base Layer  # Python, system deps (fast rebuild)"
	@echo "  2. ML Layer          # PyTorch, transformers (slow, cached)"
	@echo "  3. Application Layer # Your code (fastest rebuild)"
	@echo ""
	@echo "Development Build Tags (each build creates multiple tags):"
	@echo "  make cpu              # Creates: cpu-dev, cpu-amd64-dev, amd64-dev"
	@echo "  make arm64            # Creates: cpu-dev, cpu-arm64-dev, arm64-dev"
	@echo "  make cuda             # Creates: cuda-dev, cuda-amd64-dev, amd64-cuda-dev"
	@echo ""
	@echo "Individual Layers (for debugging/testing):"
	@echo "  make cpu-base         # Build system base only"
	@echo "  make cpu-ml           # Build ML layer (requires base)"
	@echo ""
	@echo "Usage Examples:"
	@echo "  docker run mcp-ragex:cpu-dev          # Latest built (backward compatible)"
	@echo "  docker run mcp-ragex:cpu-amd64-dev    # Specifically AMD64 CPU"
	@echo "  docker run mcp-ragex:cpu-arm64-dev    # Specifically ARM64 CPU"
	@echo "  docker run mcp-ragex:cuda-amd64-dev   # CUDA build"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

.PHONY: cpu-base arm64-base cpu-ml arm64-ml cuda-base cuda-ml cpu arm64 cuda cpu-cicd cpu-multiarch cuda-cicd publish-cpu-base publish-cuda-base publish-cpu publish-cuda install-cpu install-cuda clean help