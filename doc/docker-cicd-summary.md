# Docker CI/CD Summary

This document summarizes the GitHub Actions Docker CI/CD setup for MCP-RageX.

## What Was Created

### 1. Build & Test Workflow (`.github/workflows/docker-build-test.yml`)
- Runs on every PR and push
- Tests code and builds Docker image
- Security scanning with Trivy

### 2. GHCR Publish Workflow (`.github/workflows/docker-publish-ghcr.yml`)
- Publishes to GitHub Container Registry
- No configuration needed - uses built-in token
- Multi-architecture builds (amd64 + arm64)

### 3. Docker Hub Workflow (`.github/workflows/docker-publish-dockerhub.yml`)
- Optional - disabled by default
- For maximum visibility when open source

### 4. Release Pipeline (`.github/workflows/docker-release.yml`)
- Complete release automation
- Version validation
- Multi-arch manifests
- GitHub release creation

## Resources You Need to Provide

### For GitHub Container Registry (Recommended)
- ✅ Nothing! Uses built-in `GITHUB_TOKEN`
- ✅ Free for public repos
- ✅ Images are private while repo is private

### For Docker Hub (Optional)
- `DOCKERHUB_USERNAME` secret
- `DOCKERHUB_TOKEN` secret (access token)
- Set `ENABLE_DOCKERHUB` variable to `true`

### For Private Registry
- `REGISTRY_URL`, `REGISTRY_USERNAME`, `REGISTRY_PASSWORD` secrets

## Image Publishing Locations

### 1. GitHub Container Registry (Default)
- Path: `ghcr.io/YOUR_USERNAME/mcp-ragex`
- Best for GitHub-hosted projects
- Seamless integration

### 2. Docker Hub (Optional)
- Path: `YOUR_DOCKERHUB_USERNAME/mcp-ragex`
- Best for discoverability
- Most popular registry

### 3. Private Registry (Pre-open source)
- Path: `your-registry.com/mcp-ragex`
- Full control over access

## Costs

### While Private
- GitHub Actions: 2,000 minutes/month free
- GHCR Storage: 500MB free
- Docker builds: ~5-10 minutes each

### When Open Source
- Everything is FREE for public repos!
- Unlimited Actions minutes
- Unlimited GHCR storage

## Usage

```bash
# Tag a release to trigger publishing
git tag v1.0.0
git push origin v1.0.0

# Or manually trigger
# Go to Actions → Docker Publish → Run workflow
```

## Security Features
- Container vulnerability scanning
- SBOM (Software Bill of Materials) generation
- No secrets in images
- Minimal attack surface

## GitHub Token Permissions

The workflows use the built-in `GITHUB_TOKEN` which needs these permissions:

### For Basic Build & Test
```yaml
permissions:
  contents: read        # Read repository code
  security-events: write # Upload security scan results
```

### For Publishing to GHCR
```yaml
permissions:
  contents: read        # Read repository code
  packages: write       # Push images to ghcr.io
```

### For Release Pipeline
```yaml
permissions:
  contents: write       # Create releases and tags
  packages: write       # Push images to ghcr.io
  security-events: write # Upload security scan results
```

### Fine-Grained Personal Access Token (PAT)

If you need to create a Personal Access Token instead of using the automatic `GITHUB_TOKEN`, grant these permissions:

**Repository Permissions:**
- ✅ Actions: Read (to view workflow runs)
- ✅ Contents: Read (to clone repository)
- ✅ Metadata: Read (always required)
- ✅ Packages: Write (to push container images) 
- ✅ Pull requests: Read (for PR workflows)
- ✅ Code scanning alerts: Write (for uploading Trivy scan results)

**Account Permissions:**
- None required for public registries

For releases, also add:
- ✅ Contents: Write (to create releases and tags)

**Note**: The exact permission names in GitHub UI are:
- "Packages" (not "Registry" or "Container registry")
- "Code scanning alerts" (not "Security events")
- These are under Repository permissions when creating the token

### Workflow-Level Permissions

Each workflow declares its required permissions explicitly:

```yaml
jobs:
  build:
    permissions:
      contents: read
      packages: write
      security-events: write
```

This follows the principle of least privilege - workflows only get the permissions they need.

## Next Steps

The workflows are ready to use and will work immediately with GitHub Container Registry. When you're ready to go open source, just make the repo public and optionally enable Docker Hub publishing for wider reach!