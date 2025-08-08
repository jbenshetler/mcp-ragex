#!/bin/bash
# Development helper script for Docker split image architecture
# This script helps developers work with the base/app image split

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
BASE_IMAGE="ghcr.io/jbenshetler/mcp-ragex-base:latest"
LOCAL_BASE="mcp-ragex-base:local"
APP_IMAGE="mcp-ragex:dev"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Helper functions
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if base image exists locally
check_base_image() {
    if docker images | grep -q "$LOCAL_BASE"; then
        return 0
    else
        return 1
    fi
}

# Build base image locally
build_base() {
    log_info "Building base image locally..."
    docker build -f "$PROJECT_ROOT/docker/base.Dockerfile" -t "$LOCAL_BASE" "$PROJECT_ROOT"
    if [ $? -eq 0 ]; then
        log_info "Base image built successfully: $LOCAL_BASE"
    else
        log_error "Failed to build base image"
        exit 1
    fi
}

# Pull base image from registry
pull_base() {
    log_info "Pulling base image from registry..."
    docker pull "$BASE_IMAGE"
    if [ $? -eq 0 ]; then
        docker tag "$BASE_IMAGE" "$LOCAL_BASE"
        log_info "Base image pulled and tagged as: $LOCAL_BASE"
    else
        log_error "Failed to pull base image"
        exit 1
    fi
}

# Build application image
build_app() {
    if ! check_base_image; then
        log_warn "Base image not found locally"
        echo "Would you like to:"
        echo "1) Pull from registry (faster)"
        echo "2) Build locally"
        echo "3) Exit"
        read -p "Choice [1/2/3]: " choice
        
        case $choice in
            1) pull_base ;;
            2) build_base ;;
            3) exit 0 ;;
            *) log_error "Invalid choice"; exit 1 ;;
        esac
    fi
    
    log_info "Building application image..."
    docker build \
        -f "$PROJECT_ROOT/docker/app.Dockerfile" \
        --build-arg BASE_IMAGE="$LOCAL_BASE" \
        -t "$APP_IMAGE" \
        "$PROJECT_ROOT"
        
    if [ $? -eq 0 ]; then
        log_info "Application image built successfully: $APP_IMAGE"
    else
        log_error "Failed to build application image"
        exit 1
    fi
}

# Run development container
run_dev() {
    log_info "Starting development container..."
    docker run -it --rm \
        -v "$PROJECT_ROOT/src:/app/src:ro" \
        -v "$PROJECT_ROOT/tests:/app/tests:ro" \
        -v "$PWD:/workspace:ro" \
        -v "ragex-dev-data:/data" \
        -e LOG_LEVEL=DEBUG \
        -e DOCKER_CONTAINER=true \
        -e RAGEX_ENABLE_WATCHDOG=true \
        "$APP_IMAGE" \
        "${@:-serve}"
}

# Run tests in container
run_tests() {
    log_info "Running tests in container..."
    docker run -it --rm \
        -v "$PROJECT_ROOT/src:/app/src:ro" \
        -v "$PROJECT_ROOT/tests:/app/tests:ro" \
        "$APP_IMAGE" \
        bash -c "cd /app && python -m pytest tests/ -v"
}

# Clean up images
clean() {
    log_warn "This will remove local Docker images and volumes"
    read -p "Are you sure? [y/N]: " confirm
    
    if [[ $confirm =~ ^[Yy]$ ]]; then
        log_info "Removing application image..."
        docker rmi "$APP_IMAGE" 2>/dev/null || true
        
        log_info "Removing local base image..."
        docker rmi "$LOCAL_BASE" 2>/dev/null || true
        
        log_info "Removing development volumes..."
        docker volume rm ragex-dev-data 2>/dev/null || true
        
        log_info "Cleanup complete"
    else
        log_info "Cleanup cancelled"
    fi
}

# Show help
show_help() {
    cat << EOF
Docker Development Helper for MCP-RAGex

Usage: $0 [command] [options]

Commands:
  build-base    Build the base image locally
  pull-base     Pull the base image from registry
  build         Build the application image (default)
  run           Run development container
  test          Run tests in container
  clean         Remove local images and volumes
  help          Show this help message

Examples:
  $0                    # Build app image (prompts for base if needed)
  $0 build              # Same as above
  $0 run                # Run the development server
  $0 run ragex search   # Run a specific command
  $0 test               # Run test suite

Environment Variables:
  BASE_IMAGE    Override base image (default: $BASE_IMAGE)
  APP_IMAGE     Override app image name (default: $APP_IMAGE)

EOF
}

# Main script logic
case "${1:-build}" in
    build-base)
        build_base
        ;;
    pull-base)
        pull_base
        ;;
    build)
        build_app
        ;;
    run)
        shift
        build_app
        run_dev "$@"
        ;;
    test)
        build_app
        run_tests
        ;;
    clean)
        clean
        ;;
    help|--help|-h)
        show_help
        ;;
    *)
        log_error "Unknown command: $1"
        show_help
        exit 1
        ;;
esac