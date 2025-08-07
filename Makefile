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

## Base image builds
cpu-base:      ## Build CPU base image
	docker build -f docker/cpu/Dockerfile.base \
		-t $(REGISTRY)/$(BASE_IMAGE_NAME):cpu-$(VERSION) \
		-t $(REGISTRY)/$(BASE_IMAGE_NAME):cpu-latest . \
		$(NO_CACHE)

cuda-base:     ## Build CUDA base image  
	docker build -f docker/cuda/Dockerfile.base \
		-t $(REGISTRY)/$(BASE_IMAGE_NAME):cuda-$(VERSION) \
		-t $(REGISTRY)/$(BASE_IMAGE_NAME):cuda-latest . \
		$(NO_CACHE)

## Development builds
cpu:           ## Build CPU image for local development (ARCH=amd64|arm64)
	docker buildx build --platform linux/$(ARCH) \
		-f docker/cpu/Dockerfile.conditional \
		-t $(IMAGE_NAME):cpu-dev \
		--load . \
		$(NO_CACHE)

cuda:          ## Build CUDA image for local development
	docker build -f docker/cuda/Dockerfile \
		-t $(IMAGE_NAME):cuda-dev .

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

publish-cpu:   ## Build and publish CPU image (multi-platform)
	docker buildx build --push --platform $(PLATFORMS_CPU) \
		-f docker/cpu/Dockerfile.conditional \
		-t $(REGISTRY)/$(IMAGE_NAME):$(VERSION)-cpu \
		-t $(REGISTRY)/$(IMAGE_NAME):latest-cpu .

publish-cuda:  ## Build and publish CUDA image
	docker buildx build --push --platform $(PLATFORMS_GPU) \
		-f docker/cuda/Dockerfile \
		-t $(REGISTRY)/$(IMAGE_NAME):$(VERSION)-cuda \
		-t $(REGISTRY)/$(IMAGE_NAME):latest-cuda .

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
	@echo "Architecture Support:"
	@echo "  ARCH=amd64    Build for AMD64 (default, ~1.6GiB with CPU-only PyTorch)"
	@echo "  ARCH=arm64    Build for ARM64 (~4GiB with regular PyTorch)"
	@echo ""
	@echo "Usage Examples:"
	@echo "  make cpu              # Build for AMD64"
	@echo "  make cpu ARCH=arm64   # Build for ARM64"
	@echo "  make cpu-multiarch    # Build for both architectures"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

.PHONY: cpu-base cuda-base cpu cuda cpu-cicd cpu-multiarch cuda-cicd publish-cpu-base publish-cuda-base publish-cpu publish-cuda install-cpu install-cuda clean help