# Docker CI/CD Guide

This guide explains the GitHub Actions workflows for Docker CI/CD and how to configure them for the new multi-platform Docker architecture (CPU/GPU).

## Overview

The repository uses a structured Docker architecture with separate CPU and GPU builds:

1. **Current Implementation**: CPU-only builds for reliability and speed
2. **Future Implementation**: GPU builds when CI/CD workflow is stable
3. **Makefile Integration**: Uses `make cpu-cicd` and `make publish-cpu` commands
4. **Multi-platform Support**: CPU images support AMD64 and ARM64

## Docker Architecture Integration

### Current Structure
The CI/CD workflows integrate with the new Docker architecture:

- **CPU Builds**: Use `docker/cpu/Dockerfile` 
- **Base Images**: Can build `docker/cpu/Dockerfile.base` for reuse
- **Requirements**: Use `requirements/cpu.txt` for CPU-only PyTorch
- **Makefile Commands**: Workflows call `make cpu-cicd` and `make publish-cpu`

### Future GPU Support
When GPU CI/CD is enabled:

- **CUDA Builds**: Will use `docker/cuda/Dockerfile`
- **GPU Requirements**: Will use `requirements/cuda.txt` 
- **Makefile Commands**: Will call `make cuda-cicd` and `make publish-cuda`
- **Platform Limitations**: GPU images are AMD64 only

## Configuration Steps

### 1. For GitHub Container Registry (GHCR)

#### Required Secrets
Add `GHCR_TOKEN` to repository secrets:

1. Create Personal Access Token (classic) with scopes:
   - `write:packages` - Upload packages to GHCR
   - `read:packages` - Download packages from GHCR
2. Go to repository Settings → Secrets and variables → Actions
3. Add secret `GHCR_TOKEN` with your token value

#### Alternative: Fine-grained Token (Recommended)
Create fine-grained token with repository-specific permissions:
- **Repository access**: Select your repository
- **Permissions**: Contents (Read), Metadata (Read), Packages (Write)

### 2. CI/CD Workflow Setup

#### Current Workflow (CPU Only)
Create `.github/workflows/docker-publish.yml` that:
- Triggers on push to main and tags
- Uses `make cpu-cicd` for building
- Uses `make publish-cpu` for publishing
- Supports multi-platform (AMD64, ARM64)

#### Sample Workflow Steps
```bash
# In GitHub Actions workflow
- name: Build CPU image
  run: make cpu-cicd

- name: Publish CPU image  
  run: make publish-cpu
```

## Workflow Features

### Build and Test Workflow
- ✅ Runs Python tests
- ✅ Builds Docker image
- ✅ Security scanning with Trivy
- ✅ Code coverage reporting
- ✅ Runs on PRs and main branch

### Publish Workflows
- ✅ Multi-architecture builds (amd64, arm64)
- ✅ Semantic versioning
- ✅ Automatic tagging
- ✅ Build caching for speed
- ✅ SBOM generation
- ✅ Security scanning

### Release Pipeline
- ✅ Version validation
- ✅ Full test suite
- ✅ Multi-arch manifest
- ✅ GitHub release creation
- ✅ Release notes generation

## Image Tagging Strategy

The new architecture uses platform-specific tags:

| Event | CPU Tags | GPU Tags (Future) |
|-------|----------|-------------------|
| Push to main | `latest-cpu` | `latest-cuda` |
| Tag v1.2.3 | `v1.2.3-cpu`, `latest-cpu` | `v1.2.3-cuda`, `latest-cuda` |
| Development | `dev-cpu` | `dev-cuda` |

### Registry Locations
- **Application Images**: `ghcr.io/jbenshetler/mcp-ragex:{version}-{platform}`
- **Base Images**: `ghcr.io/jbenshetler/mcp-ragex-base:{platform}-{version}`

## Costs and Limits

### GitHub Container Registry (GHCR)
- **Public repos**: Free, unlimited
- **Private repos**: Free up to storage limits
  - 500MB storage included
  - 1GB bandwidth/month included
- **Recommended for**: Open source projects

### Docker Hub
- **Public repos**: Free, unlimited
- **Private repos**: 1 free private repo
- **Rate limits**: 100 pulls/6 hours (anonymous), 200 pulls/6 hours (authenticated)
- **Recommended for**: Maximum visibility

### Build Minutes
- **Public repos**: Unlimited free Actions minutes
- **Private repos**: 2,000 minutes/month free, then paid

## Security Considerations

1. **Never commit secrets** - Use GitHub Secrets
2. **Use access tokens** - Not passwords
3. **Scan images** - Workflows include Trivy scanning
4. **SBOM generation** - For supply chain security
5. **Minimal images** - Multi-stage builds reduce attack surface

## Going Open Source Checklist

When ready to open source:

- [ ] Set up GHCR_TOKEN secret in repository settings
- [ ] Create `.github/workflows/docker-publish.yml` workflow file
- [ ] Tag a release version: `git tag v1.0.0 && git push origin v1.0.0`
- [ ] Make repository public
- [ ] Verify CPU workflow runs correctly
- [ ] Plan GPU workflow rollout (future)

## Testing Workflows Locally

Test workflows locally with [act](https://github.com/nektos/act):

```bash
# Install act
brew install act  # macOS
# or
curl https://raw.githubusercontent.com/nektos/act/master/install.sh | sudo bash

# Test build workflow
act -W .github/workflows/docker-build-test.yml

# Test with secrets
act -W .github/workflows/docker-publish-ghcr.yml -s GITHUB_TOKEN=$GITHUB_TOKEN
```

## Customization Options

### Different Base Images
Edit the appropriate Dockerfile:
- CPU: `docker/cpu/Dockerfile` or `docker/cpu/Dockerfile.base`
- GPU: `docker/cuda/Dockerfile` or `docker/cuda/Dockerfile.base`

### Additional Platforms
CPU images support multiple platforms. GPU images are AMD64 only due to CUDA limitations.

Modify `Makefile` platform variables:
```makefile
PLATFORMS_CPU := linux/amd64,linux/arm64,linux/arm/v7
PLATFORMS_GPU := linux/amd64  # CUDA limitation
```

### Custom Registry
Change registry in `Makefile`:
```makefile
REGISTRY := my-registry.com/username
```

### Requirements Customization
Modify platform-specific requirements:
- `requirements/base.txt` - Common dependencies
- `requirements/cpu.txt` - CPU-specific PyTorch
- `requirements/cuda.txt` - CUDA-specific PyTorch

## Troubleshooting

### Build Failures
- Check the build logs in Actions tab
- Ensure Dockerfile builds locally
- Verify all dependencies are specified

### Push Failures
- Check authentication credentials
- Verify repository permissions
- Ensure image names are valid

### Multi-arch Issues
- QEMU must be set up (workflows handle this)
- Some dependencies may not support all architectures
- Test each platform separately if needed

## Fine-Grained PAT Permissions

If creating a fine-grained Personal Access Token for CI/CD:

**Repository Permissions:**
- ✅ **Actions**: Read
- ✅ **Contents**: Read (Write for releases)
- ✅ **Metadata**: Read (always required)
- ✅ **Packages**: Write
- ✅ **Pull requests**: Read
- ✅ **Code scanning alerts**: Write

**Note**: In the GitHub UI, these appear exactly as:
- "Packages" (for container registry access)
- "Code scanning alerts" (for security scan uploads)

## Next Steps

1. **While Private**: Use the build-test workflow to validate changes
2. **When Ready**: Tag a release to trigger publishing
3. **After Open Source**: Enable Docker Hub workflow if desired
4. **Monitor**: Check security alerts and update dependencies