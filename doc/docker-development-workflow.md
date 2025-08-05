# Docker Development Workflow Guide

This document describes the development workflow for MCP-Ragex using Docker, following the designed container architecture with proper installation and daemon usage.

## Overview

MCP-Ragex follows a structured development workflow:

1. **Build** Docker images (CPU or GPU)
2. **Install** the image using `install.sh`
3. **Start** daemon with `ragex start` or `ragex index <path>`
4. **Develop** using `ragex` commands

This ensures consistency between development and production usage.

## Quick Start

### CPU Development (Recommended)
```bash
make cpu                                    # Build CPU image
RAGEX_IMAGE=mcp-ragex:cpu-dev ./install.sh  # Install image
ragex start                                 # Index current directory and start daemon
ragex search "query"                        # Search your code
```

### NVIDIA GPU Development
```bash
make cuda                                   # Build CUDA image
RAGEX_IMAGE=mcp-ragex:cuda-dev ./install.sh # Install image
ragex start                                 # Index current directory and start daemon
ragex search "query"                        # Search with GPU acceleration
```

## Development Workflow

### Step 1: Build Docker Image

#### CPU Development
```bash
make cpu                    # Build mcp-ragex:cpu-dev
```

#### GPU Development (NVIDIA)
```bash
make cuda                   # Build mcp-ragex:cuda-dev
```

### Step 2: Install Image

Install the locally built image:
```bash
# CPU installation
RAGEX_IMAGE=mcp-ragex:cpu-dev ./install.sh

# GPU installation  
RAGEX_IMAGE=mcp-ragex:cuda-dev ./install.sh
```

**What this does:**
- Creates user-specific data volume
- Installs `ragex` and `ragex-mcp` wrappers in `~/.local/bin`
- Configures the image for your user

### Step 3: Start Development Environment

#### Index Current Project
```bash
ragex start                 # Alias for 'ragex index .'
# or
ragex index .               # Explicit current directory
# or  
ragex index /path/to/code   # Index specific directory
```

**What this does:**
- Starts daemon container for your project
- Builds semantic index of your code
- Sets up file watching for live updates
- Creates project-specific data storage

### Step 4: Develop

#### Search Your Code
```bash
ragex search "authentication"     # Semantic search
ragex search "def login" --regex   # Regex search
ragex search "handleSubmit" --symbol # Symbol search
```

#### Project Management
```bash
ragex info                  # Show project information
ragex ls                    # List all your projects
ragex stop                  # Stop current project daemon
ragex status                # Check daemon status
```

#### MCP Integration  
```bash
ragex register claude       # Register with Claude Code
ragex --mcp                 # Run as MCP server
```

## Convenience Targets

For faster development iterations:

### `make install-cpu`
Combines build + install:
```bash
make install-cpu            # Equivalent to:
                           # make cpu && RAGEX_IMAGE=mcp-ragex:cpu-dev ./install.sh
```

### `make install-cuda`  
Combines build + install for GPU:
```bash
make install-cuda           # Equivalent to:
                           # make cuda && RAGEX_IMAGE=mcp-ragex:cuda-dev ./install.sh
```

## Development Best Practices

### Project Isolation

Each project gets its own:
- **Daemon container**: `ragex_daemon_{project_id}`
- **Data directory**: Based on project path hash
- **Index storage**: Persistent across rebuilds
- **File watching**: Automatic re-indexing on changes

### User Data Management

```bash
# View your data volume
docker volume inspect ragex_user_$(id -u)

# Backup project data
ragex ls -l                 # Find project IDs
# Manual backup via Docker volume

# Clean up old projects
ragex ls                    # List projects
ragex rm "old-project-*"    # Remove by glob pattern
```

### Container Lifecycle

#### Active Development
```bash
ragex status                # Check if daemon is running
ragex start                 # Start if not running
ragex search "query"        # Use normally
```

#### After Code Changes
The daemon automatically:
- **Watches files**: Detects changes as you save
- **Re-indexes**: Updates search index incrementally  
- **Stays current**: No manual re-indexing needed

#### Stopping/Starting
```bash
ragex stop                  # Stop daemon (data persists)
ragex start                 # Restart daemon (reloads data)
```

## GPU Development Considerations

### Prerequisites
- NVIDIA GPU with CUDA support
- `nvidia-docker` runtime installed
- Docker configured for GPU access

### Verification
```bash
# Test GPU access
docker run --rm --gpus all nvidia/cuda:12.1-runtime-ubuntu22.04 nvidia-smi

# Check ragex GPU usage (after starting daemon)
ragex start
docker exec ragex_daemon_$(ragex info | grep "Project ID" | cut -d: -f2 | tr -d ' ') nvidia-smi
```

### Performance Benefits
- **Faster indexing**: GPU-accelerated embeddings
- **Better search**: More sophisticated semantic understanding
- **Larger projects**: Handle bigger codebases efficiently

## Troubleshooting

### Build Issues
```bash
make clean                  # Clear Docker build cache
make cpu                    # Rebuild from scratch
```

### Installation Issues
```bash
# Check Docker access
docker ps

# Verify image exists
docker images | grep mcp-ragex

# Check PATH
echo $PATH | grep ~/.local/bin
```

### Daemon Issues
```bash
ragex status                # Check daemon status
ragex log                   # View daemon logs
ragex stop && ragex start   # Restart daemon
```

### Permission Issues
```bash
# Check volume permissions
docker volume inspect ragex_user_$(id -u)

# Recreate volume if needed
docker volume rm ragex_user_$(id -u)
make install-cpu
```

### GPU Issues
```bash
# Verify nvidia-docker
docker run --rm --gpus all nvidia/cuda:12.1-runtime-ubuntu22.04 nvidia-smi

# Check GPU in ragex
ragex start
# Check logs for CUDA initialization
ragex log
```

## Integration with IDEs

### VS Code
1. Install Docker extension
2. Use `ragex register claude` for Claude Code integration
3. Access daemon logs via `ragex log`

### Command Line Development
```bash
ragex start                 # Start daemon
ragex search "function"     # Find code quickly
# Edit code in your preferred editor
# ragex automatically re-indexes on save
ragex search "new code"     # Search updated index
```

## Production vs Development

### Development Images
- **Built locally**: `make cpu` or `make cuda`
- **Tagged as**: `mcp-ragex:cpu-dev`, `mcp-ragex:cuda-dev`
- **Include**: Development tools, faster rebuild times
- **Purpose**: Local testing and development

### Production Images  
- **Built for CI/CD**: `make cpu-cicd`, `make cuda-cicd`
- **Tagged with version**: `ghcr.io/jbenshetler/mcp-ragex:v1.0.0-cpu`
- **Optimized**: Smaller size, multi-platform
- **Purpose**: Publishing and deployment

### Testing Production Images
```bash
# Pull published image
docker pull ghcr.io/jbenshetler/mcp-ragex:latest-cpu

# Install for testing  
RAGEX_IMAGE=ghcr.io/jbenshetler/mcp-ragex:latest-cpu ./install.sh

# Use normally
ragex start
```

This development workflow ensures consistency with the designed container architecture while providing a smooth development experience.