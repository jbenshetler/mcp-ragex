# Makefile for MCP-RageX Docker development

# Default image name for local builds
IMAGE_NAME := ragex:local

# Default target
.PHONY: all
all: image install

# Build the Docker image locally
.PHONY: image
image:
	@echo "🔨 Building Docker image: $(IMAGE_NAME)"
	docker build -f docker/app.Dockerfile -t $(IMAGE_NAME) .
	@echo "✅ Image built successfully: $(IMAGE_NAME)"

# Install ragex using the local image
.PHONY: install
install:
	@echo "📦 Installing ragex with image: $(IMAGE_NAME)"
	@echo "🧹 Stopping and removing any existing ragex daemon containers..."
	@docker ps -a -q -f "name=ragex_daemon_" | xargs -r docker stop 2>/dev/null || true
	@docker ps -a -q -f "name=ragex_daemon_" | xargs -r docker rm 2>/dev/null || true
	RAGEX_IMAGE=$(IMAGE_NAME) ./install.sh
	@echo "✅ Installation complete"

# Clean up Docker resources
.PHONY: clean
clean:
	@echo "🧹 Cleaning up Docker resources"
	docker rmi $(IMAGE_NAME) || true
	@echo "✅ Cleanup complete"

# Test the installation
.PHONY: test
test:
	@echo "🧪 Testing ragex installation"
	@mkdir -p test-ragex-temp
	@cd test-ragex-temp && echo "# Test" > README.md && echo "def test(): pass" > test.py
	@cd test-ragex-temp && ragex init && ragex index . --force
	@rm -rf test-ragex-temp
	@echo "✅ Test complete"

# Show help
.PHONY: help
help:
	@echo "MCP-RageX Docker Development Makefile"
	@echo ""
	@echo "Targets:"
	@echo "  all      - Build image and install (default)"
	@echo "  image    - Build the Docker image"
	@echo "  install  - Install ragex using the local image"
	@echo "  clean    - Remove the local Docker image"
	@echo "  test     - Test the ragex installation"
	@echo "  help     - Show this help message"
	@echo ""
	@echo "Examples:"
	@echo "  make              # Build and install"
	@echo "  make image        # Just build the image"
	@echo "  make install      # Just install (assumes image exists)"
	@echo "  make test         # Test the installation"