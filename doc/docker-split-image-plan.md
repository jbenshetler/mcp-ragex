# Docker Split Image Architecture Plan

## Executive Summary

This plan outlines the migration from a single Docker image to a two-image architecture that separates slow-building dependencies from frequently-changing application code. This will reduce build times from 5-7 minutes to under 1 minute for most development changes.

## Current State

- Single `Dockerfile` builds everything from scratch
- Every code change triggers a full rebuild
- Build time: 5-7 minutes
- Heavy dependencies (PyTorch, tree-sitter) reinstalled every time

## Proposed Architecture

### Two-Image System

1. **Base Image** (`mcp-ragex-base`)
   - Contains all system dependencies
   - Contains all Python dependencies
   - Pre-downloaded models
   - Built weekly or on dependency changes
   - Published to: `ghcr.io/jbenshetler/mcp-ragex-base`

2. **Application Image** (`mcp-ragex`)
   - Built FROM base image
   - Contains only application code
   - Built on every code change
   - Build time: ~30-60 seconds
   - Published to: `ghcr.io/jbenshetler/mcp-ragex`

## Implementation Plan

### Phase 1: Create Base Image (Week 1)

#### 1.1 Create Base Dockerfile
```
Path: docker/base.Dockerfile
```

**Contents:**
- Python 3.10 slim base
- System packages: gcc, g++, git, ripgrep
- All requirements.txt dependencies
- Pre-download sentence transformer models
- Pre-compile tree-sitter languages
- Create ragex user and directories

**Estimated time:** 2 hours

#### 1.2 Create Base Image Workflow
```
Path: .github/workflows/docker-build-base.yml
```

**Triggers:**
- Manual dispatch
- Weekly schedule (Sundays at midnight)
- Changes to requirements.txt
- Changes to base.Dockerfile

**Estimated time:** 1 hour

#### 1.3 Build and Publish Initial Base Image
- Run workflow manually
- Verify image builds correctly
- Test image locally
- Publish to GHCR

**Estimated time:** 1 hour

### Phase 2: Create Application Image (Week 1)

#### 2.1 Create Application Dockerfile
```
Path: docker/app.Dockerfile
```

**Contents:**
- FROM base image (with ARG for version)
- Copy application code only
- Set up environment variables
- Define entrypoint

**Estimated time:** 1 hour

#### 2.2 Update Existing Workflows
Modify these workflows to use app.Dockerfile:
- `.github/workflows/docker-publish-ghcr.yml`
- `.github/workflows/docker-release.yml`
- `.github/workflows/docker-build-test.yml`

**Changes:**
- Add `file: docker/app.Dockerfile`
- Add `build-args: BASE_IMAGE=...`

**Estimated time:** 2 hours

### Phase 3: Development Tooling (Week 2)

#### 3.1 Update Docker Compose Files
Modify for split images:
- `docker-compose.yml`
- `docker-compose.dev.yml`
- `docker-compose.prod.yml`

**Changes:**
- Reference app.Dockerfile
- Add BASE_IMAGE build arg
- Add source code volume mounts for dev

**Estimated time:** 1 hour

#### 3.2 Create Development Scripts
```
Path: scripts/docker-dev.sh
```

**Features:**
- Pull or build base image
- Quick rebuild app image
- Run with proper mounts

**Estimated time:** 1 hour

### Phase 4: Documentation and Migration (Week 2)

#### 4.1 Update Documentation
- Update docker/README.md
- Update main README.md Docker section
- Create docker/DEVELOPMENT.md

**Estimated time:** 2 hours

#### 4.2 Migration Steps
1. Merge base image code to main
2. Build and publish base image
3. Update all workflows
4. Test complete pipeline
5. Archive old Dockerfile

**Estimated time:** 2 hours

## Technical Specifications

### Base Image Contents
```
Size estimate: ~1.5GB
- Python 3.10: 150MB
- System packages: 100MB
- Python dependencies: 1.2GB
  - PyTorch: 800MB
  - Sentence transformers: 200MB
  - Other deps: 200MB
- Pre-downloaded models: 50MB
```

### Application Image Contents
```
Size estimate: ~50MB additional
- Source code: 5MB
- Scripts: 1MB
- Configuration: 1MB
```

### Build Time Estimates

| Stage | Current | With Split |
|-------|---------|------------|
| System packages | 30s | 0s (in base) |
| Python deps | 4min | 0s (in base) |
| Code copy | 10s | 10s |
| Other | 30s | 20s |
| **Total** | **5-7min** | **30-60s** |

## Version Management Strategy

### Base Image Versioning
- `latest`: Always latest stable
- `YYYY.MM.DD`: Date-based tags
- `sha-XXXXXXX`: Git SHA based

### Dependency Updates
1. Automated weekly rebuilds
2. Security patches applied automatically
3. Major updates require manual approval

### Pinning Strategy
- Development: Use `latest` base
- Production: Pin to specific date tag
- Hotfixes: Can update app without base

## Rollback Plan

If issues arise:
1. Keep current Dockerfile as `Dockerfile.legacy`
2. Workflows can be reverted via Git
3. Base image failures don't block app builds
4. Can quickly switch back to monolithic build

## Success Metrics

### Primary Goals
- ✅ Reduce build time to <1 minute for code changes
- ✅ Maintain all current functionality
- ✅ No increase in operational complexity

### Measurable Outcomes
- Build time reduction: 80-90%
- Developer iteration speed: 5-10x faster
- CI/CD pipeline time: 70% reduction
- Registry storage: More efficient with layering

## Risk Assessment

### Low Risk
- Base image build failures (weekly, monitored)
- Slightly larger total image size
- Additional workflow complexity

### Mitigations
- Fallback to previous base image
- Health checks in workflows
- Comprehensive testing before migration

## Timeline

### Week 1
- Days 1-2: Create base image and workflow
- Days 3-4: Create app image and update workflows
- Day 5: Testing and initial deployment

### Week 2
- Days 1-2: Update development tooling
- Days 3-4: Documentation
- Day 5: Final migration and cleanup

### Total Effort: ~15 hours over 2 weeks

## Next Steps

1. Review and approve plan
2. Create tracking issue in GitHub
3. Begin Phase 1 implementation
4. Schedule weekly check-ins

## Appendix: File Structure

```
mcp-ragex/
├── docker/
│   ├── base.Dockerfile        # New: Base image
│   ├── app.Dockerfile         # New: Application image
│   ├── README.md              # Updated: Docker documentation
│   └── DEVELOPMENT.md         # New: Dev workflow guide
├── .github/workflows/
│   ├── docker-build-base.yml  # New: Base image builder
│   ├── docker-publish-ghcr.yml # Modified: Use app.Dockerfile
│   ├── docker-release.yml     # Modified: Use app.Dockerfile
│   └── docker-build-test.yml  # Modified: Use app.Dockerfile
├── scripts/
│   └── docker-dev.sh          # New: Development helper
├── docker-compose.yml         # Modified: Use split images
├── docker-compose.dev.yml     # Modified: Add dev mounts
├── docker-compose.prod.yml    # Modified: Pin base version
└── Dockerfile.legacy          # Renamed: Current Dockerfile
```