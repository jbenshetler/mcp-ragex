# Docker CI/CD Guide

This guide explains the GitHub Actions workflows for Docker CI/CD and how to configure them for your needs.

## Overview

The repository includes several GitHub Actions workflows for different stages:

1. **Build and Test** (`docker-build-test.yml`) - Runs on every PR
2. **Publish to GHCR** (`docker-publish-ghcr.yml`) - Publishes to GitHub Container Registry
3. **Publish to Docker Hub** (`docker-publish-dockerhub.yml`) - Optional Docker Hub publishing
4. **Release Pipeline** (`docker-release.yml`) - Full release workflow with multi-arch builds

## Pre-Open Source Setup (Private Development)

While developing privately, you can:

### Option 1: Use GitHub Container Registry (Recommended)
- No additional setup needed
- Images are private by default for private repos
- Free for your use
- Automatically becomes public when repo goes public

### Option 2: Disable Publishing
Simply don't run the publish workflows until ready.

### Option 3: Use a Private Registry
Modify the workflows to use your private registry:
```yaml
env:
  REGISTRY: your-registry.com
  IMAGE_NAME: mcp-ragex
```

## Configuration Steps

### 1. For GitHub Container Registry (GHCR)
**No configuration needed!** The workflows use the built-in `GITHUB_TOKEN`.

When you're ready to publish:
```bash
git tag v0.1.0
git push origin v0.1.0
```

### 2. For Docker Hub (Optional)

1. Create a Docker Hub account
2. Generate an access token at https://hub.docker.com/settings/security
3. Add secrets to your GitHub repository:
   - Go to Settings → Secrets and variables → Actions
   - Add `DOCKERHUB_USERNAME` (your Docker Hub username)
   - Add `DOCKERHUB_TOKEN` (the access token, NOT your password)
4. Add variable `ENABLE_DOCKERHUB` = `true`

### 3. For Private Registry

Add these secrets:
- `REGISTRY_URL`: Your registry URL
- `REGISTRY_USERNAME`: Your username
- `REGISTRY_PASSWORD`: Your password

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

Tags are automatically generated based on:

| Event | Tags Generated |
|-------|----------------|
| Push to main | `latest`, `main` |
| Push to develop | `develop` |
| Tag v1.2.3 | `v1.2.3`, `1.2.3`, `1.2`, `1`, `latest` |
| PR #45 | `pr-45` |
| Manual | Whatever you specify |

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

- [ ] Clean sensitive data from git history
- [ ] Review .gitignore and .dockerignore
- [ ] Update image names if needed
- [ ] Set up Docker Hub account (optional)
- [ ] Update README with public install instructions
- [ ] Tag a release version
- [ ] Make repository public
- [ ] Verify workflows run correctly

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
Edit the Dockerfile:
```dockerfile
FROM python:3.10-slim  # Change this
```

### Additional Platforms
Add to the platforms list:
```yaml
platforms: linux/amd64,linux/arm64,linux/arm/v7
```

### Custom Registry
Change the registry URL:
```yaml
env:
  REGISTRY: my-registry.com
```

### Build Arguments
Add build args for versioning:
```yaml
build-args: |
  VERSION=${{ github.ref_name }}
  BUILD_DATE=$(date -u +%Y-%m-%dT%H:%M:%SZ)
```

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