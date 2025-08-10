# RAGex Installation Guide

This guide provides comprehensive installation instructions for RAGex, including one-line installation, configuration options, and platform-specific considerations.

## Quick Start (One-Line Installation)

### Basic Installation (Auto-Detection)
```bash
curl -fsSL https://raw.githubusercontent.com/jbenshetler/mcp-ragex/refs/heads/main/install.sh | bash
```

This will:
- Auto-detect your platform (AMD64, ARM64, or CUDA)
- Install with secure defaults (no network access for containers)
- Use the pre-bundled fast embedding model

### Installation with Options
```bash
# Install with network access enabled and balanced model as default
curl -fsSL https://raw.githubusercontent.com/jbenshetler/mcp-ragex/refs/heads/main/install.sh | bash -s -- --network --model balanced

# Force CPU version (smaller image) with network access
curl -fsSL https://raw.githubusercontent.com/jbenshetler/mcp-ragex/refs/heads/main/install.sh | bash -s -- --cpu --network --model accurate

# Force CUDA version (requires NVIDIA GPU)
curl -fsSL https://raw.githubusercontent.com/jbenshetler/mcp-ragex/refs/heads/main/install.sh | bash -s -- --cuda --model balanced
```

## Installation Parameters

### Platform Selection
- **Auto-detection** (default): Automatically detects platform and CUDA support
- `--cpu`: Force CPU-only version (works on AMD64 and ARM64)
- `--cuda`: Force CUDA version (AMD64 only, requires NVIDIA GPU + nvidia-docker)

### Network Configuration
- **No flag** (default): Secure mode - containers run without network access
- `--network`: Enable network access for containers (allows downloading additional models)

### Default Embedding Model
- **No flag** (default): Uses 'fast' model (pre-bundled in all images)
- `--model <name>`: Sets default model for new projects
  - Valid options: `fast`, `balanced`, `accurate`, `multilingual`

## Platform Auto-Detection

### AMD64 (x86_64)
- **With NVIDIA GPU + Docker Support**: Auto-selects CUDA version
- **Without NVIDIA**: Auto-selects CPU version

### ARM64 (Apple Silicon, etc.)
- **Always**: Uses CPU version (CUDA not supported on ARM64)

### Unsupported Architectures
Installation will fail with clear error message for unsupported platforms.

## Docker Image Sizes

| Platform | Image Size | Use Case |
|----------|------------|----------|
| **AMD64 CPU** | ~3.2 GiB | General use, smaller download |
| **ARM64 CPU** | ~2.2 GiB | Apple Silicon Macs, ARM servers |
| **CUDA** | ~13.1 GiB | NVIDIA GPU acceleration |

### Size Considerations
- **CUDA images are ~4x larger** than CPU images due to CUDA libraries
- Most users prefer CPU images for faster download and installation
- GPU acceleration primarily benefits initial indexing; search performance is similar
- Use `--cpu` to override CUDA auto-detection for smaller images

## Embedding Models

### Model Comparison

| Model | Size | Speed | Quality | Use Case |
|-------|------|-------|---------|----------|
| **fast** | ~90 MB | Fastest | Good | Quick prototyping, smaller codebases |
| **balanced** | ~435 MB | Moderate | Better | Production use, balanced performance |
| **accurate** | ~1.3 GB | Slower | Best | Large codebases, maximum quality |
| **multilingual** | ~435 MB | Moderate | Good | Multi-language projects |

### Model Availability
- **fast**: Pre-bundled in all images, works without network access
- **balanced**, **accurate**, **multilingual**: Downloaded on first use (requires network access)

## Security Modes

### Secure Mode (Default)
```bash
curl -fsSL https://raw.githubusercontent.com/jbenshetler/mcp-ragex/refs/heads/main/install.sh | bash
```
- Containers run with `--network none`
- No external network access from containers
- Only pre-bundled fast model available
- Suitable for air-gapped environments

### Network-Enabled Mode
```bash
curl -fsSL https://raw.githubusercontent.com/jbenshetler/mcp-ragex/refs/heads/main/install.sh | bash -s -- --network
```
- Containers can access external networks
- Can download additional embedding models on demand
- Required for using balanced, accurate, or multilingual models

## Post-Installation

### Verify Installation
```bash
ragex --help
ragex info
```

### Quick Start
```bash
cd your-project
ragex index .          # Index current directory
ragex search "query"   # Search your code
```

### Configuration
```bash
ragex configure        # Show current configuration
ragex ls              # List indexed projects
```

## Manual Installation (Alternative)

If you prefer to download and inspect the script first:

```bash
# Download the installer
curl -fsSL https://raw.githubusercontent.com/jbenshetler/mcp-ragex/refs/heads/main/install.sh -o ragex-install.sh

# Review the script
cat ragex-install.sh

# Run with desired options
chmod +x ragex-install.sh
./ragex-install.sh --network --model balanced
```

## Troubleshooting

### Docker Not Found
```
❌ Docker not found. Please install Docker first.
```
**Solution**: Install Docker from https://docs.docker.com/get-docker/

### Docker Daemon Not Running
```
❌ Docker daemon not running. Please start Docker.
```
**Solution**: Start Docker Desktop or run `sudo systemctl start docker`

### Unsupported Architecture
```
❌ Unsupported architecture: s390x
```
**Solution**: RAGex currently supports AMD64 and ARM64 only

### Invalid Model Name
```
❌ Invalid model: typo
   Available models: fast, balanced, accurate, multilingual
```
**Solution**: Use one of the valid model names listed

### NVIDIA GPU Not Detected
If you have an NVIDIA GPU but the installer selects CPU:
- Verify `nvidia-smi` works: `nvidia-smi`
- Check Docker NVIDIA support: `docker info | grep nvidia`
- Install nvidia-docker if missing: https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html

## Uninstallation

To completely remove RAGex:

```bash
# Stop and remove all ragex containers
docker ps -a -f "name=ragex_" -q | xargs -r docker stop
docker ps -a -f "name=ragex_" -q | xargs -r docker rm

# Remove Docker images
docker images "*ragex*" -q | xargs -r docker rmi

# Remove user volumes (WARNING: This deletes all indexed data)
docker volume ls -f "name=ragex_user_" -q | xargs -r docker volume rm

# Remove configuration and binaries
rm -rf ~/.config/ragex
rm -f ~/.local/bin/ragex ~/.local/bin/ragex-mcp
```

## Advanced Configuration

### Custom Docker Registry
Set the `RAGEX_IMAGE` environment variable before installation:
```bash
export RAGEX_IMAGE="my-registry.com/ragex:custom-tag"
curl -fsSL https://raw.githubusercontent.com/jbenshetler/mcp-ragex/refs/heads/main/install.sh | bash
```

### Development Installation
For development with local images:
```bash
export RAGEX_IMAGE="mcp-ragex:cuda-dev"  # Use local dev image
./install.sh --cuda --network
```

## Integration with Claude Code

After installation, register RAGex with Claude Code:

```bash
# Get the registration command
ragex register claude

# Run the output command (example):
claude mcp add ragex ~/.local/bin/ragex-mcp --scope project
```

This enables RAGex as an MCP server for Claude Code, providing intelligent code search capabilities directly in your Claude conversations.