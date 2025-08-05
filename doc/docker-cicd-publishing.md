# Docker CI/CD Publishing Guide

This document describes the CI/CD setup for publishing Docker images to GitHub Container Registry (GHCR), including required credentials, workflows, and best practices.

## Overview

MCP-Ragex publishes Docker images to GitHub Container Registry (GHCR) with the following naming convention:

- **Application Images**: `ghcr.io/jbenshetler/mcp-ragex:{version}-{platform}`
- **Base Images**: `ghcr.io/jbenshetler/mcp-ragex-base:{platform}-{version}`

### Image Tags

#### Application Images
```
ghcr.io/jbenshetler/mcp-ragex:latest-cpu      # Latest CPU version
ghcr.io/jbenshetler/mcp-ragex:latest-cuda     # Latest CUDA version
ghcr.io/jbenshetler/mcp-ragex:v1.0.0-cpu     # Specific CPU version
ghcr.io/jbenshetler/mcp-ragex:v1.0.0-cuda    # Specific CUDA version
```

#### Base Images
```
ghcr.io/jbenshetler/mcp-ragex-base:cpu-latest   # Latest CPU base
ghcr.io/jbenshetler/mcp-ragex-base:cuda-latest  # Latest CUDA base
ghcr.io/jbenshetler/mcp-ragex-base:cpu-v1.0.0   # Specific CPU base
ghcr.io/jbenshetler/mcp-ragex-base:cuda-v1.0.0  # Specific CUDA base
```

## Required Credentials and Tokens

### GitHub Container Registry (GHCR) Authentication

#### Personal Access Token (Classic)
Create a Personal Access Token with the following scopes:
- `write:packages` - Upload packages to GHCR
- `read:packages` - Download packages from GHCR  
- `delete:packages` - Delete packages (optional, for cleanup)

**Steps to create:**
1. Go to GitHub Settings → Developer settings → Personal access tokens → Tokens (classic)
2. Click "Generate new token (classic)"
3. Select scopes: `write:packages`, `read:packages`
4. Set expiration as needed
5. Copy the token (save securely)

#### Fine-grained Personal Access Token (Recommended)
Create a fine-grained token with repository-specific permissions:
- **Repository access**: Select `jbenshetler/mcp-ragex`
- **Permissions**: 
  - Contents: Read (for source code access)
  - Metadata: Read (for repository metadata)
  - Packages: Write (for publishing images)

### GitHub Actions Secrets

Set the following secrets in your repository:

#### Required Secrets
```
GHCR_TOKEN=ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

**How to add secrets:**
1. Go to repository Settings → Secrets and variables → Actions
2. Click "New repository secret"
3. Name: `GHCR_TOKEN`
4. Value: Your personal access token
5. Click "Add secret"

#### Optional Secrets
```
DOCKER_BUILDKIT=1                    # Enable BuildKit features
BUILDX_NO_DEFAULT_ATTESTATIONS=1     # Disable attestations for smaller images
```

## CI/CD Workflows

### Current Workflow (CPU Only)

The current CI/CD workflow focuses on CPU builds for reliability and speed. Create `.github/workflows/docker-publish.yml` with:

- **Triggers**: Push to main, tags, and pull requests
- **Permissions**: Contents read, packages write
- **Steps**: Checkout, setup buildx, login to GHCR, build, and publish
- **Makefile integration**: Uses `make cpu-cicd` and `make publish-cpu`

### Future Workflow (CPU + GPU)

When GPU CI/CD is ready, add a second job that:
- Runs after CPU build succeeds
- Only on push events (not PRs due to build time)
- Uses `make cuda-cicd` and `make publish-cuda`

## Local Publishing Setup

### Configure Docker for GHCR

```bash
# Login to GHCR
echo $GHCR_TOKEN | docker login ghcr.io -u jbenshetler --password-stdin

# Verify login
docker info | grep -A 1 "Registry:"
```

### Local Publishing Commands

```bash
# Build and publish CPU images
make cpu-cicd
make publish-cpu

# Build and publish base images
make cpu-base
make publish-cpu-base

# Build and publish CUDA images (future)
make cuda-cicd  
make publish-cuda
```

## Makefile Integration

The Makefile automatically handles:

### Version Detection
- Uses `git describe --tags` for version tagging
- Falls back to "dev" for untagged commits
- Supports dirty working tree indication

### Registry Configuration
- Centralized registry and image name configuration
- Consistent tagging across all build targets
- Platform-specific suffixes (-cpu, -cuda)

### Multi-platform Builds
- CPU images: `linux/amd64`, `linux/arm64`
- GPU images: `linux/amd64` only (CUDA limitation)
- Uses `docker buildx` for efficient multi-platform builds

### Publishing Targets
- `make publish-cpu` - Build and push CPU application image
- `make publish-cuda` - Build and push CUDA application image  
- `make publish-cpu-base` - Build and push CPU base image
- `make publish-cuda-base` - Build and push CUDA base image

## Image Verification

### Verify Published Images

```bash
# Pull and test CPU image
docker pull ghcr.io/jbenshetler/mcp-ragex:latest-cpu
docker run --rm ghcr.io/jbenshetler/mcp-ragex:latest-cpu --version

# Pull and test CUDA image
docker pull ghcr.io/jbenshetler/mcp-ragex:latest-cuda
docker run --rm --gpus all ghcr.io/jbenshetler/mcp-ragex:latest-cuda --version
```

### Image Inspection

```bash
# Inspect image details
docker inspect ghcr.io/jbenshetler/mcp-ragex:latest-cpu

# Check image size and layers
docker images ghcr.io/jbenshetler/mcp-ragex
docker history ghcr.io/jbenshetler/mcp-ragex:latest-cpu
```

## Security Best Practices

### Token Management
- **Rotation**: Rotate GHCR tokens regularly (every 6-12 months)
- **Scope limitation**: Use minimal required scopes
- **Environment isolation**: Separate tokens for prod/staging if needed

### Image Security
- **Vulnerability scanning**: Enable GitHub's security features
- **Base image updates**: Regular security updates
- **Minimal privileges**: Non-root containers

### Access Control
- **Repository permissions**: Limit who can modify secrets
- **Branch protection**: Require reviews for main branch
- **Audit logging**: Monitor package access

## Troubleshooting

### Authentication Issues

```bash
# Test GHCR login
echo $GHCR_TOKEN | docker login ghcr.io -u jbenshetler --password-stdin

# Check token permissions
curl -H "Authorization: token $GHCR_TOKEN" https://api.github.com/user
```

### Build Failures

```bash
# Clear build cache
make clean

# Enable verbose build output
make cpu-cicd DOCKER_BUILDKIT_PROGRESS=plain
```

### Push Failures

```bash
# Test registry connectivity
docker pull hello-world
docker tag hello-world ghcr.io/jbenshetler/test:latest
docker push ghcr.io/jbenshetler/test:latest
docker rmi ghcr.io/jbenshetler/test:latest
```

### Rate Limiting

GHCR has the following limits:
- **Bandwidth**: 1GB/hour for anonymous users, 10GB/hour for authenticated
- **Requests**: 1000/hour for anonymous, 15000/hour for authenticated
- **Storage**: Unlimited for public packages

## Monitoring and Maintenance

### Package Management

View and manage published packages at:
- GitHub profile → Packages tab
- Repository → Packages section
- Individual package settings for version management

### Automated Cleanup

Create `.github/workflows/cleanup-images.yml` to:
- Run weekly via cron schedule
- Delete old untagged versions
- Keep minimum number of recent versions
- Reduce storage usage

### Cost Monitoring

Monitor usage for:
- **Storage**: Package storage usage
- **Bandwidth**: Download metrics  
- **Build minutes**: CI/CD usage

## Migration and Rollback

### Registry Migration

If switching registries:
1. **Parallel publishing**: Publish to both registries during transition
2. **Update references**: Change image references in deployments
3. **Deprecation notice**: Notify users of old registry deprecation
4. **Cleanup**: Remove old images after migration period

### Version Rollback

```bash
# Rollback to previous version
docker pull ghcr.io/jbenshetler/mcp-ragex:v1.0.0-cpu
docker tag ghcr.io/jbenshetler/mcp-ragex:v1.0.0-cpu ghcr.io/jbenshetler/mcp-ragex:latest-cpu
docker push ghcr.io/jbenshetler/mcp-ragex:latest-cpu
```

## Future Enhancements

### Planned Features
- **Multi-architecture GPU**: ARM64 CUDA support when available
- **Attestation**: Image provenance and SBOM
- **Signing**: Cosign integration for image verification
- **Helm charts**: Kubernetes deployment automation

### Monitoring Integration
- **Prometheus**: Image download metrics
- **Grafana**: Usage dashboards  
- **Alerting**: Build failure notifications