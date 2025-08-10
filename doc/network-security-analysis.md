# Network Security Analysis for RAGex

This document analyzes RAGex's network requirements and compatibility with restricted network environments, including air-gapped and host-only network scenarios.

## Network Requirements Analysis

### Primary Network Dependencies

RAGex has **one primary network dependency**:

#### Embedding Model Downloads (HuggingFace/Sentence Transformers)
- **Source**: `huggingface.co` 
- **Purpose**: Download sentence-transformer models for semantic search
- **Frequency**: One-time download per model, cached locally
- **Size**: Varies by model preset:
  - **Fast** (`all-MiniLM-L6-v2`): ~80MB
  - **Balanced** (`all-mpnet-base-v2`): ~420MB  
  - **Accurate** (`all-roberta-large-v1`): ~1.3GB

#### What RAGex Does NOT Require
- ✅ No external API calls
- ✅ No telemetry or analytics
- ✅ No license verification
- ✅ No update checks
- ✅ No external database connections
- ✅ No cloud services

## Air-Gapped / No Network Access Scenario

### Status: ✅ **FULLY COMPATIBLE**

RAGex can operate completely offline once embedding models are pre-cached.

#### Pre-Setup Requirements

**1. Pre-populate Model Cache**
```bash
# During container build or initial setup (with network access)
export TRANSFORMERS_CACHE=/data/models
export SENTENCE_TRANSFORMERS_HOME=/data/models

# Download all embedding models
python3 << EOF
from sentence_transformers import SentenceTransformer
print("Downloading fast model...")
SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')
print("Downloading balanced model...")  
SentenceTransformer('sentence-transformers/all-mpnet-base-v2')
print("Downloading accurate model...")
SentenceTransformer('sentence-transformers/all-roberta-large-v1')
print("All models cached successfully!")
EOF
```

**2. Docker Implementation**
```dockerfile
# Multi-stage build for offline-capable image
FROM python:3.10-slim as model-downloader

# Install dependencies and download models
RUN pip install sentence-transformers torch
ENV TRANSFORMERS_CACHE=/models
ENV SENTENCE_TRANSFORMERS_HOME=/models

RUN python3 -c "
from sentence_transformers import SentenceTransformer
SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')
SentenceTransformer('sentence-transformers/all-mpnet-base-v2') 
SentenceTransformer('sentence-transformers/all-roberta-large-v1')
"

# Final stage with models included
FROM ragex/base:latest
COPY --from=model-downloader /models /data/models
```

**3. Persistent Volume Setup**
```bash
# Create persistent volume for model cache
docker volume create ragex_models

# Mount volume to preserve models across container restarts
docker run -v ragex_models:/data/models ragex/mcp-server
```

#### Offline Functionality

**✅ What Works Without Network:**
- **Code Search**: Full ripgrep-based regex search functionality
- **Tree-sitter Parsing**: Symbol extraction from all supported languages
- **Semantic Search**: Complete semantic search once models are cached
- **Parallel Processing**: Full parallel symbol extraction capabilities
- **File Indexing**: ChromaDB vector database operations
- **MCP Server**: Complete Model Context Protocol functionality
- **Progress Tracking**: Real-time indexing and search progress
- **File Watching**: Automatic re-indexing on file changes

**❌ What Requires Network (One-Time Setup Only):**
- Initial embedding model downloads (if not pre-cached)

#### Environment Configuration for Offline Operation

```bash
# Force offline mode to prevent network attempts
export HF_HUB_OFFLINE=1
export TRANSFORMERS_OFFLINE=1

# Specify local model cache locations
export TRANSFORMERS_CACHE=/data/models
export SENTENCE_TRANSFORMERS_HOME=/data/models

# Optional: Disable model update checks
export HF_HUB_DISABLE_PROGRESS_BARS=1
```

## Host-Only Network Access Scenario

### Status: ✅ **IDEAL SETUP**

This is actually the **recommended production configuration** for security-sensitive environments.

#### What This Enables
- **On-Demand Model Downloads**: Models download automatically when needed
- **Flexible Model Selection**: Can switch between model presets dynamically
- **Automatic Updates**: Models can be updated if desired (though not required)
- **Reduced Image Size**: No need to pre-bundle models in container image

#### Network Traffic Analysis

**Outbound Connections:**
- **Destination**: `huggingface.co` (HTTPS port 443)
- **Frequency**: Only during initial model download or manual updates
- **Data Transfer**: 80MB - 1.3GB per model (one-time)
- **Protocol**: HTTPS (TLS encrypted)

**No Inbound Connections Required:**
- RAGex operates as a service, not a server
- MCP communication via stdin/stdout pipes
- No exposed ports or listening services

#### Firewall Configuration

**Restrictive Firewall (Allow Only Model Downloads):**
```bash
# Allow HTTPS to HuggingFace for model downloads
iptables -A OUTPUT -d huggingface.co -p tcp --dport 443 -j ACCEPT
iptables -A OUTPUT -d cdn-lfs.huggingface.co -p tcp --dport 443 -j ACCEPT

# Block all other outbound traffic
iptables -A OUTPUT -p tcp --dport 80 -j DROP
iptables -A OUTPUT -p tcp --dport 443 -j DROP
```

**DNS Requirements:**
```bash
# Allow DNS resolution for HuggingFace domains
iptables -A OUTPUT -p udp --dport 53 -j ACCEPT
```

#### Container Network Configuration

```bash
# Run with host networking (most secure for local-only access)
docker run --network host ragex/mcp-server

# Or with bridge network (no external exposure)
docker run --network bridge ragex/mcp-server
```

## Security Benefits

### Enhanced Security Posture

**1. Minimal Attack Surface**
- No exposed network services
- No listening ports
- Communication only via file system and stdin/stdout

**2. Data Privacy Protection**
- Code never transmitted over network
- All processing performed locally
- No cloud dependencies or data sharing

**3. Air-Gap Compatibility**
- Complete functionality without internet access
- Suitable for classified or sensitive environments
- No risk of data exfiltration

**4. Container Isolation**
- No network bridges required
- No port forwarding needed
- Minimal container permissions required

### Compliance Considerations

**Suitable For:**
- Government/military environments
- Financial services with strict data policies
- Healthcare with HIPAA requirements
- Corporate environments with data loss prevention policies
- Development environments with sensitive intellectual property

## Implementation Strategies

### Strategy 1: Pre-Built Offline Image

**Use Case**: Maximum security, no network access allowed

```dockerfile
FROM ragex/base:latest

# Pre-download all models during build
ENV TRANSFORMERS_CACHE=/data/models
ENV SENTENCE_TRANSFORMERS_HOME=/data/models
RUN python3 -c "
from sentence_transformers import SentenceTransformer
for model in ['all-MiniLM-L6-v2', 'all-mpnet-base-v2', 'all-roberta-large-v1']:
    SentenceTransformer(f'sentence-transformers/{model}')
"

# Configure for offline operation
ENV HF_HUB_OFFLINE=1
ENV TRANSFORMERS_OFFLINE=1
```

### Strategy 2: Lazy Loading with Host Network

**Use Case**: Balanced security and flexibility

```bash
# Allow host network access for model downloads
docker run --network host \
  -v ragex_models:/data/models \
  ragex/mcp-server
```

### Strategy 3: Init Container Pattern

**Use Case**: Kubernetes deployments with network policies

```yaml
apiVersion: v1
kind: Pod
spec:
  initContainers:
  - name: model-downloader
    image: ragex/model-downloader
    volumeMounts:
    - name: models
      mountPath: /data/models
  containers:
  - name: ragex
    image: ragex/mcp-server
    volumeMounts:
    - name: models
      mountPath: /data/models
    env:
    - name: HF_HUB_OFFLINE
      value: "1"
  volumes:
  - name: models
    emptyDir: {}
```

## Performance Considerations

### Model Loading Performance

**Cold Start (First Use):**
- **With Network**: 10-30 seconds (download + load)
- **Pre-cached**: 2-5 seconds (load only)

**Warm Start (Model in Memory):**
- **Any Configuration**: <1 second

## Docker Image Size Impact

When including pre-cached embedding models in Docker images, the size impact varies significantly by model choice:

### Model Size Breakdown

| Model Preset | Model Name | Model Files | Total Cache | Use Case |
|-------------|------------|-------------|-------------|----------|
| **fast** | all-MiniLM-L6-v2 | ~80MB | ~90MB | Quick prototyping, smaller codebases |
| **balanced** | all-mpnet-base-v2 | ~420MB | ~435MB | Production ready, good speed/quality balance |
| **accurate** | all-roberta-large-v1 | ~1300MB | ~1330MB | High quality, slower processing |
| **multilingual** | paraphrase-multilingual-MiniLM-L12-v2 | ~420MB | ~435MB | Multiple programming languages |

### Docker Image Size Impact

- **Base RAGex image**: ~500MB (no models)
- **+ Fast model** (`all-MiniLM-L6-v2`): +90MB → ~590MB total
- **+ Balanced model** (`all-mpnet-base-v2`): +435MB → ~935MB total  
- **+ Accurate model** (`all-roberta-large-v1`): +1.3GB → ~1.8GB total
- **+ All models**: +1.9GB → ~2.4GB total

### Recommendations by Deployment Scenario

- **Air-gapped baseline**: Pre-bundle fast model (+90MB)
- **Air-gapped production**: Pre-bundle balanced model (+435MB)
- **Air-gapped high-quality**: Pre-bundle accurate model (+1.3GB)
- **Maximum air-gapped flexibility**: Pre-bundle all models (+1.9GB)

### Host-Only Network Strategy

- Use base image without models (500MB)
- Models download on first use (80MB - 1.3GB per model)
- Persistent volume recommended for model caching to avoid re-downloads

### Storage Requirements

**Model Cache Storage:**
- **Fast Model Only**: ~150MB total
- **Balanced Model Only**: ~500MB total  
- **Accurate Model Only**: ~1.4GB total
- **All Models**: ~2GB total

### Memory Usage

**Runtime Memory:**
- **Base RAGex**: ~100MB
- **+ Fast Model**: +200MB (~300MB total)
- **+ Balanced Model**: +400MB (~500MB total)
- **+ Accurate Model**: +800MB (~900MB total)

## Verification and Testing

### Testing Offline Functionality

```bash
# Test 1: Verify models are cached
docker run --rm -v ragex_models:/data/models \
  ragex/mcp-server python3 -c "
import os
from sentence_transformers import SentenceTransformer
print('Model cache:', os.listdir('/data/models'))
model = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')
print('Model loaded successfully:', model.get_sentence_embedding_dimension())
"

# Test 2: Verify offline operation
docker run --rm --network none \
  -v ragex_models:/data/models \
  ragex/mcp-server ragex search "test function"
```

### Network Traffic Monitoring

```bash
# Monitor network connections during operation
netstat -an | grep :443  # Should show connections to huggingface.co only during model download
tcpdump -i any host huggingface.co  # Monitor HuggingFace traffic
```

## Troubleshooting

### Common Issues

**1. Models Not Found in Offline Mode**
```bash
# Verify model cache location
ls -la /data/models/
export TRANSFORMERS_CACHE=/data/models
export SENTENCE_TRANSFORMERS_HOME=/data/models
```

**2. Network Timeouts During Model Download**
```bash
# Increase timeout for slow connections
export HF_HUB_DOWNLOAD_TIMEOUT=300
```

**3. Insufficient Disk Space**
```bash
# Check available space for model cache
df -h /data/models
# Clean old models if needed
ragex clean-models --keep-current
```

## Recommendations

### Production Deployment

**For Maximum Security (Air-Gapped):**
1. Use pre-built images with embedded models
2. Set `HF_HUB_OFFLINE=1` 
3. Use `--network none` Docker flag
4. Mount code directories read-only

**For Balanced Security (Host-Only Network):**
1. Use lazy-loading with persistent volume
2. Configure restrictive firewall rules
3. Use `--network host` Docker flag
4. Monitor network connections

**For Development:**
1. Allow full internet access initially
2. Cache models in persistent volume
3. Switch to offline mode for testing
4. Verify functionality without network

### Model Selection Strategy

**Choose Based on Requirements:**
- **Fast Model**: Quick setup, minimal storage, good for development
- **Balanced Model**: Production-ready, good quality/size tradeoff
- **Accurate Model**: Best quality, suitable for large codebases

**Multiple Model Strategy:**
- Pre-cache all models for maximum flexibility
- Switch models based on project size and quality requirements
- Use fast model for initial indexing, upgrade for production

## Conclusion

RAGex is exceptionally well-suited for restricted network environments:

✅ **Air-Gapped Environments**: Complete functionality with pre-cached models
✅ **Host-Only Networks**: Ideal balance of security and flexibility  
✅ **Container Security**: No exposed ports or services required
✅ **Data Privacy**: All processing performed locally
✅ **Compliance Ready**: Suitable for highly regulated environments

The architecture's local-first design makes it naturally compatible with high-security deployments while maintaining full functionality and performance.