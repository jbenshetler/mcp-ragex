# Docker Migration Plan for RAGex MCP Server

## Overview

This document outlines the migration plan to containerize the RAGex MCP Server for open-source distribution. The primary goal is to eliminate environment-related issues and provide a consistent, reproducible setup for all users.

## Motivation

- **Environment Conflicts**: UV creates `.venv` in each directory, leading to VIRTUAL_ENV conflicts
- **Dependency Hell**: Tree-sitter version mismatches (0.23.x vs 0.24.x) cause indexing failures
- **Support Burden**: "Works on my machine" issues are difficult to debug remotely
- **Installation Complexity**: Users need correct Python version, system dependencies, and package managers

## Phase 1: Analysis & Design (2-3 hours)

### 1.1 Current Architecture Review

**Components to Containerize:**
- MCP server (`src/server.py`)
- Indexing script (`scripts/build_semantic_index.py`)
- Search functionality (`ragex_search.py`)
- Tree-sitter language parsers
- Embedding models (sentence-transformers)

**Data Persistence Requirements:**
- ChromaDB vector database (`./chroma_db`)
- Downloaded embedding models
- User configuration files

**Configuration:**
- Environment variables (RAGEX_*)
- `.mcpignore` patterns
- MCP protocol settings

### 1.2 Docker Architecture Design

```
Container Structure:
/app/                     # Application code (immutable)
├── src/                  # Source code
├── scripts/              # Utility scripts
├── requirements.txt      # Python dependencies
└── entrypoint.sh        # Container entrypoint

/data/                    # Persistent data (volume)
├── chroma_db/           # Vector database
└── models/              # Cached embedding models

/workspace/              # User's code (volume, read-only)
└── [user's project]     # Code to be indexed
```

**Design Decisions:**
- Multi-stage build for smaller image size
- Non-root user for security
- Pre-downloaded language parsers to avoid runtime downloads
- Flexible entrypoint for multiple commands
- **Logging to stderr only** to prevent MCP protocol conflicts
- **JSON structured logging** for container log aggregation

## Phase 2: Core Docker Implementation (4-5 hours)

### 2.1 Multi-Stage Dockerfile

```dockerfile
# Stage 1: Builder
FROM python:3.10-slim as builder

# Install build dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build

# Copy dependency files
COPY requirements.txt pyproject.toml ./

# Install Python dependencies
RUN pip install --user --no-cache-dir -r requirements.txt

# Stage 2: Runtime
FROM python:3.10-slim

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    git \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN useradd -m -u 1000 ragex

WORKDIR /app

# Copy dependencies from builder
COPY --from=builder /root/.local /home/ragex/.local
ENV PATH=/home/ragex/.local/bin:$PATH

# Copy application code
COPY --chown=ragex:ragex src/ ./src/
COPY --chown=ragex:ragex scripts/ ./scripts/
COPY --chown=ragex:ragex pyproject.toml ./

# Pre-download tree-sitter language parsers
RUN python -c "import tree_sitter_python, tree_sitter_javascript, tree_sitter_typescript"

# Create data directories
RUN mkdir -p /data/chroma_db /data/models && \
    chown -R ragex:ragex /data

# Switch to non-root user
USER ragex

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV RAGEX_DATA_DIR=/data
ENV TRANSFORMERS_CACHE=/data/models
ENV SENTENCE_TRANSFORMERS_HOME=/data/models
ENV DOCKER_CONTAINER=true
ENV LOG_LEVEL=INFO

# Copy and set entrypoint
COPY --chown=ragex:ragex docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh
ENTRYPOINT ["/entrypoint.sh"]
```

### 2.2 Entrypoint Script

```bash
#!/bin/bash
# entrypoint.sh
set -e

# Function to check if workspace is mounted
check_workspace() {
    if [ ! -d "/workspace" ] || [ -z "$(ls -A /workspace 2>/dev/null)" ]; then
        echo "❌ Error: No workspace mounted. Mount your project directory to /workspace"
        echo "   Example: docker run -v \$(pwd):/workspace:ro ..."
        exit 1
    fi
}

# Handle different commands
case "$1" in
    "index")
        check_workspace
        shift
        exec python scripts/build_semantic_index.py "$@"
        ;;
    "serve"|"server")
        exec python -m src.server
        ;;
    "search")
        shift
        exec python ragex_search.py "$@"
        ;;
    "bash"|"sh")
        exec "$@"
        ;;
    *)
        # Default to MCP server
        exec python -m src.server "$@"
        ;;
esac
```

### 2.3 .dockerignore

```
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
.venv/
venv/
ENV/

# IDEs
.vscode/
.idea/
*.swp
*.swo

# OS
.DS_Store
Thumbs.db

# Project specific
chroma_db/
.mcpignore
*.log
.git/
tests/
docs/
*.md
!README.md
```

## Phase 3: Docker Compose Setup (2-3 hours)

### 3.1 Development Configuration

```yaml
# docker-compose.yml
version: '3.8'

services:
  ragex:
    build:
      context: .
      dockerfile: Dockerfile
    image: ragex/mcp-server:dev
    volumes:
      - .:/workspace:ro                    # Current directory (read-only)
      - ragex-data:/data                # Persistent data
    environment:
      - LOG_LEVEL=${LOG_LEVEL:-INFO}
      - DOCKER_CONTAINER=true
      - RAGEX_EMBEDDING_MODEL=${RAGEX_EMBEDDING_MODEL:-fast}
      - RAGEX_PERSIST_DIR=/data/chroma_db
    command: serve
    stdin_open: true
    tty: true
    ports:
      - "3000:3000"  # If needed for debugging

  # Development indexer
  indexer:
    image: ragex/mcp-server:dev
    volumes:
      - .:/workspace:ro
      - ragex-data:/data
    environment:
      - LOG_LEVEL=DEBUG
      - DOCKER_CONTAINER=true
    command: index /workspace --force
    profiles: ["index"]

volumes:
  ragex-data:
    driver: local
```

### 3.2 Production Configuration

```yaml
# docker-compose.prod.yml
version: '3.8'

services:
  ragex-mcp:
    image: ragex/mcp-server:latest
    volumes:
      - ${WORKSPACE:-$PWD}:/workspace:ro
      - ragex-index:/data
    environment:
      - LOG_LEVEL=WARNING
      - DOCKER_CONTAINER=true
    command: serve
    stdin_open: true
    tty: true
    restart: unless-stopped
    mem_limit: 2g
    cpus: 1.0

volumes:
  ragex-index:
    driver: local
```

### 3.3 MCP Configuration Example

```json
{
  "mcpServers": {
    "ragex": {
      "command": "docker",
      "args": [
        "run",
        "-i",
        "--rm",
        "-v", "${PWD}:/workspace:ro",
        "-v", "ragex-data:/data",
        "ragex/mcp-server:latest",
        "serve"
      ],
      "env": {
        "LOG_LEVEL": "INFO",
        "DOCKER_CONTAINER": "true"
      }
    }
  }
}
```

### 3.4 Logging Configuration

Since MCP servers communicate via stdout, all logging must go to stderr to prevent protocol corruption. The logging system adapts based on environment:

#### Logging Strategy

```python
# src/utils/logging_setup.py
import sys
import logging
import json
import os
from datetime import datetime

class DockerFormatter(logging.Formatter):
    """JSON formatter optimized for container logs"""
    def format(self, record):
        return json.dumps({
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'level': record.levelname,
            'component': record.name,
            'message': record.getMessage(),
            'pid': os.getpid(),
            **getattr(record, 'extra', {})
        })

def configure_logging():
    """Configure logging based on environment"""
    # ALWAYS use stderr to avoid MCP protocol conflicts
    handler = logging.StreamHandler(sys.stderr)
    
    # Detect Docker environment
    in_docker = os.path.exists('/.dockerenv') or os.environ.get('DOCKER_CONTAINER')
    
    if in_docker:
        # JSON format for container environments
        handler.setFormatter(DockerFormatter())
    else:
        # Human-readable for local development
        handler.setFormatter(logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        ))
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.handlers = []  # Clear existing handlers
    root_logger.addHandler(handler)
    root_logger.setLevel(os.environ.get('LOG_LEVEL', 'INFO'))
    
    # Quiet noisy libraries
    for lib in ['sentence_transformers', 'chromadb', 'urllib3']:
        logging.getLogger(lib).setLevel(logging.WARNING)
```

#### Docker Compose Logging

```yaml
# docker-compose.yml
services:
  ragex:
    image: ragex/mcp-server:latest
    environment:
      - LOG_LEVEL=${LOG_LEVEL:-INFO}
      - DOCKER_CONTAINER=true
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
        labels: "service=mcp-ragex"
```

#### Key Logging Principles

1. **No stdout logging**: All logs to stderr to preserve MCP protocol
2. **No file logging in containers**: Let Docker handle log management
3. **Structured JSON logs**: Easy parsing for log aggregation tools
4. **Environment-based configuration**: Control via LOG_LEVEL env var
5. **Library noise reduction**: Suppress verbose third-party logs

## Phase 4: Testing & Validation (3-4 hours)

### 4.1 Test Matrix

| Test Case | Description | Expected Result |
|-----------|-------------|-----------------|
| Basic Index | Index small Python project | Completes < 30s |
| Large Index | Index 1000+ files | Completes < 5min |
| Persistence | Restart container | Index preserved |
| MCP Protocol | Connect from Claude | Commands work |
| Memory Limit | Index with 1GB limit | Graceful handling |
| Concurrent | Multiple searches | No conflicts |
| Logging | Check stderr output | JSON format in Docker |
| Log Isolation | Verify stdout clean | No log contamination |

### 4.2 Performance Benchmarks

```bash
#!/bin/bash
# benchmark.sh

# Test indexing performance
time docker run --rm \
    -v $(pwd):/workspace:ro \
    -v ragex-test:/data \
    ragex/mcp-server:latest \
    index /workspace --force

# Test search performance
time docker run --rm \
    -v ragex-test:/data \
    ragex/mcp-server:latest \
    search "function definition"

# Measure image size
docker images ragex/mcp-server:latest
```

### 4.3 Integration Tests

```python
# test_docker_integration.py
import subprocess
import json

def test_mcp_protocol():
    """Test MCP protocol through Docker"""
    result = subprocess.run([
        "docker", "run", "--rm",
        "-v", f"{os.getcwd()}:/workspace:ro",
        "ragex/mcp-server:latest",
        "serve"
    ], input=b'{"method": "search", "params": {"query": "test"}}',
       capture_output=True)
    
    assert result.returncode == 0
    response = json.loads(result.stdout)
    assert "results" in response
```

## Phase 5: Documentation & Distribution (2-3 hours)

### 5.1 Installation Script

```bash
#!/bin/bash
# install.sh
set -e

echo "🚀 Installing RAGex MCP Server..."

# Check Docker
if ! command -v docker &> /dev/null; then
    echo "❌ Docker not found. Please install Docker first."
    echo "   Visit: https://docs.docker.com/get-docker/"
    exit 1
fi

# Check Docker daemon
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker daemon not running. Please start Docker."
    exit 1
fi

# Pull latest image
echo "📦 Pulling latest image..."
docker pull ragex/mcp-server:latest

# Create volume for persistent data
echo "💾 Creating data volume..."
docker volume create ragex-data

# Create helper script
INSTALL_DIR="${HOME}/.local/bin"
mkdir -p "$INSTALL_DIR"

cat > "${INSTALL_DIR}/ragex" << 'EOF'
#!/bin/bash
# RAGex CLI wrapper

# Default to current directory for workspace
WORKSPACE="${WORKSPACE:-$(pwd)}"

# Run Docker container
docker run -it --rm \
  -v "${WORKSPACE}:/workspace:ro" \
  -v "ragex-data:/data" \
  -e "RAGEX_LOG_LEVEL=${RAGEX_LOG_LEVEL:-INFO}" \
  ragex/mcp-server:latest "$@"
EOF

chmod +x "${INSTALL_DIR}/ragex"

# Check if directory is in PATH
if [[ ":$PATH:" != *":$INSTALL_DIR:"* ]]; then
    echo ""
    echo "⚠️  Add $INSTALL_DIR to your PATH:"
    echo "   export PATH=\"\$PATH:$INSTALL_DIR\""
fi

echo ""
echo "✅ Installation complete!"
echo ""
echo "Quick start:"
echo "  1. cd your-project"
echo "  2. ragex index ."
echo "  3. Configure Claude with MCP settings"
echo ""
echo "For more info: https://github.com/user/ragex-mcp"
```

### 5.2 README Updates

```markdown
# RAGex MCP Server

## Quick Start (Docker)

```bash
# Install
curl -sSL https://raw.githubusercontent.com/user/ragex-mcp/main/install.sh | bash

# Index your project
cd your-project
ragex index .

# Configure Claude
Add to Claude's MCP settings (see below)
```

## Commands

- `ragex index [path]` - Build search index
- `ragex serve` - Start MCP server
- `ragex search "query"` - Search codebase

## MCP Configuration

Add to your Claude MCP settings:

```json
{
  "mcpServers": {
    "ragex": {
      "command": "docker",
      "args": [
        "run", "-i", "--rm",
        "-v", "${PWD}:/workspace:ro",
        "-v", "ragex-data:/data",
        "ragex/mcp-server:latest"
      ]
    }
  }
}
```
```

## Phase 6: CI/CD Pipeline (2-3 hours)

### 6.1 GitHub Actions Workflow

```yaml
# .github/workflows/docker-publish.yml
name: Docker Build and Publish

on:
  push:
    branches: [main]
    tags: ['v*']
  pull_request:
    branches: [main]

env:
  REGISTRY: ghcr.io
  IMAGE_NAME: ${{ github.repository }}

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.10'
      
      - name: Run tests
        run: |
          pip install -r requirements.txt
          python -m pytest tests/

  build:
    needs: test
    runs-on: ubuntu-latest
    permissions:
      contents: read
      packages: write
      
    steps:
      - uses: actions/checkout@v3
      
      - name: Log in to Container Registry
        uses: docker/login-action@v2
        with:
          registry: ${{ env.REGISTRY }}
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}
      
      - name: Extract metadata
        id: meta
        uses: docker/metadata-action@v4
        with:
          images: ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}
          tags: |
            type=ref,event=branch
            type=ref,event=pr
            type=semver,pattern={{version}}
            type=semver,pattern={{major}}.{{minor}}
            type=sha
      
      - name: Build and push
        uses: docker/build-push-action@v4
        with:
          context: .
          push: ${{ github.event_name != 'pull_request' }}
          tags: ${{ steps.meta.outputs.tags }}
          labels: ${{ steps.meta.outputs.labels }}
          cache-from: type=gha
          cache-to: type=gha,mode=max
```

### 6.2 Release Process

```yaml
# .github/workflows/release.yml
name: Release

on:
  push:
    tags:
      - 'v*'

jobs:
  release:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Create Release
        uses: actions/create-release@v1
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        with:
          tag_name: ${{ github.ref }}
          release_name: Release ${{ github.ref }}
          body: |
            Docker image: `ghcr.io/${{ github.repository }}:${{ github.ref_name }}`
            
            ## Installation
            ```bash
            docker pull ghcr.io/${{ github.repository }}:${{ github.ref_name }}
            ```
          draft: false
          prerelease: false
```

## Timeline & Milestones

### Week 1: Core Implementation
- [ ] Day 1-2: Dockerfile and build process
- [ ] Day 3-4: Entrypoint and command handling
- [ ] Day 5: Docker Compose configurations

### Week 2: Testing & Polish
- [ ] Day 1-2: Integration testing
- [ ] Day 3-4: Documentation
- [ ] Day 5: CI/CD setup

### Week 3: Release Preparation
- [ ] Day 1-2: Performance optimization
- [ ] Day 3-4: Security audit
- [ ] Day 5: Public release

## Success Metrics

1. **Image Size**: < 500MB
2. **Startup Time**: < 5 seconds
3. **Index Performance**: > 100 files/second
4. **Memory Usage**: < 1GB for typical projects
5. **User Adoption**: 50+ stars in first month

## Risk Mitigation

| Risk | Impact | Mitigation |
|------|--------|------------|
| Large image size | Slow downloads | Multi-stage build, minimal base image |
| Model downloads | First-run delay | Pre-download in image, volume caching |
| Windows compatibility | Limited audience | WSL2 documentation, native Windows build |
| MCP protocol changes | Breaking changes | Version pinning, compatibility layer |

## Conclusion

Docker containerization will significantly reduce support burden while providing a consistent, reliable experience for all users. The investment in proper containerization will pay dividends in reduced support tickets and increased adoption.