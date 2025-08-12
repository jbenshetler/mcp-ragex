# RAGex Environment Variables Reference

This document provides a comprehensive reference for all environment variables used in RAGex, including the new parallel processing variables.

## Core Configuration

### Project and Data Management

| Variable | Default | Description | Example |
|----------|---------|-------------|---------|
| `RAGEX_PROJECT_DATA_DIR` | `/data/projects/<project_id>` | Project-specific data directory | `/data/projects/ragex_1000_abc123` |
| `RAGEX_CHROMA_PERSIST_DIR` | `$RAGEX_PROJECT_DATA_DIR/chroma_db` | ChromaDB storage directory | `/data/projects/ragex_1000_abc123/chroma_db` |
| `RAGEX_CHROMA_COLLECTION` | `code_embeddings` | ChromaDB collection name | `my_project_symbols` |
| `WORKSPACE_PATH` | - | Host workspace path (set by wrapper) | `/home/user/project` |
| `PROJECT_NAME` | auto-generated | Project identifier | `ragex_1000_abc123` |

### Model and Embedding Configuration

| Variable | Default | Description | Example |
|----------|---------|-------------|---------|
| `RAGEX_EMBEDDING_MODEL` | `fast` | Embedding model preset | `fast`, `balanced`, `accurate` |
| `TRANSFORMERS_CACHE` | `/data/models` | HuggingFace model cache directory | `/data/models` |
| `SENTENCE_TRANSFORMERS_HOME` | `/data/models` | Sentence transformers cache | `/data/models` |

## Parallel Processing Configuration

### Core Parallel Settings

| Variable | Default | Description | Impact |
|----------|---------|-------------|---------|
| `RAGEX_USE_PARALLEL` | `true` | Enable/disable parallel processing | Performance: 4-8x speedup |
| `RAGEX_MAX_WORKERS` | auto-detect | Maximum worker processes | CPU utilization |
| `RAGEX_ENABLE_SHARED_PARSERS` | `true` | Enable shared parser optimization | Memory efficiency |

### Batch Processing Tuning

| Variable | Default | Description | Tuning Guide |
|----------|---------|-------------|--------------|
| `RAGEX_MIN_BATCH_SIZE` | auto-detect | Minimum files per batch | Increase for high-latency systems |
| `RAGEX_MAX_BATCH_SIZE` | auto-detect | Maximum files per batch | Decrease for memory constraints |
| `RAGEX_TARGET_BATCH_TIME` | auto-detect | Target processing time per batch (seconds) | Lower for responsive systems |

### Memory Management

| Variable | Default | Description | Memory Impact |
|----------|---------|-------------|---------------|
| `RAGEX_MEMORY_LIMIT_MB` | auto-detect | Total memory limit in MB | System stability |
| `RAGEX_WORKER_MEMORY_LIMIT_MB` | auto-detect | Per-worker memory limit in MB | Worker isolation |
| `RAGEX_CPU_THRESHOLD` | auto-detect | CPU usage threshold (0.0-1.0) | System responsiveness |

### Advanced Parallel Settings

| Variable | Default | Description | Use Case |
|----------|---------|-------------|----------|
| `RAGEX_PROCESS_TIMEOUT_SECONDS` | `300` | Worker process timeout | Large file handling |

## Logging and Debugging

### Log Level Configuration

| Variable | Default | Description | Output Level |
|----------|---------|-------------|--------------|
| `RAGEX_LOG_LEVEL` | `INFO` | Primary log level | `TRACE`, `DEBUG`, `INFO`, `WARN`, `ERROR` |
| `LOG_LEVEL` | `INFO` | Fallback log level | Used if `RAGEX_LOG_LEVEL` not set |

**Log Level Details:**
- **TRACE**: Very detailed debugging (file operations, ignore decisions)
- **DEBUG**: Detailed debugging (embeddings, scores, processing)
- **INFO**: General operation info (search queries, progress) 
- **WARN**: Warnings and potential issues
- **ERROR**: Error messages only

### Log Rotation

| Variable | Default | Description | Storage Impact |
|----------|---------|-------------|----------------|
| `RAGEX_LOG_MAX_SIZE` | `50m` | Maximum log file size | Disk usage control |
| `RAGEX_LOG_MAX_FILES` | `3` | Maximum number of log files | Total log storage |

## File Exclusion and Patterns

### Ignore File Configuration

| Variable | Default | Description | Effect |
|----------|---------|-------------|--------|
| `RAGEX_IGNOREFILE_WARNING` | `true` | Show warning when no .gitignore exists | User guidance |

## Docker and Container Settings

### Container Environment

| Variable | Default | Description | Purpose |
|----------|---------|-------------|---------|
| `DOCKER_CONTAINER` | `false` | Indicates running in container | Behavior adaptation |
| `DOCKER_USER_ID` | - | User ID for Docker operations | Permission handling |

### Resource Configuration

| Variable | Description | Docker Usage |
|----------|-------------|--------------|
| `RAGEX_DATA_DIR` | Data directory override | Volume mounting |
| `WORKSPACE_PATH` | Host workspace path | Path mapping |

## Auto-Detection Variables

These variables are automatically set by the system but can be overridden:

### System Detection

| Variable | Auto-Detected From | Override Purpose |
|----------|-------------------|------------------|
| `RAGEX_MAX_WORKERS` | CPU core count | Performance tuning |
| `RAGEX_MEMORY_LIMIT_MB` | Available RAM | Memory constraints |
| `RAGEX_CPU_THRESHOLD` | Current CPU usage | Load balancing |

### Container Detection

| Variable | Detection Method | Impact |
|----------|-----------------|--------|
| `RAGEX_IS_CONTAINERIZED` | File system checks | Resource scaling |
| `RAGEX_CONTAINER_MEMORY` | cgroup limits | Memory adaptation |

## Configuration Examples

### High-Performance Setup
```bash
# Maximize parallel processing
export RAGEX_MAX_WORKERS=16
export RAGEX_MAX_BATCH_SIZE=20
export RAGEX_TARGET_BATCH_TIME=2.0
export RAGEX_MEMORY_LIMIT_MB=8192
export RAGEX_LOG_LEVEL=INFO
```

### Memory-Constrained Environment
```bash
# Optimize for limited memory
export RAGEX_MAX_WORKERS=2
export RAGEX_MAX_BATCH_SIZE=3
export RAGEX_WORKER_MEMORY_LIMIT_MB=256
export RAGEX_MEMORY_LIMIT_MB=512
export RAGEX_TARGET_BATCH_TIME=0.5
```

### Debug Configuration
```bash
# Maximum debugging information
export RAGEX_LOG_LEVEL=TRACE
export RAGEX_LOG_MAX_SIZE=100m
export RAGEX_LOG_MAX_FILES=5
```

### Production Docker Setup
```bash
# Stable production settings
export RAGEX_MAX_WORKERS=8
export RAGEX_MEMORY_LIMIT_MB=4096
export RAGEX_LOG_LEVEL=WARN
export RAGEX_LOG_MAX_SIZE=50m
export RAGEX_PROCESS_TIMEOUT_SECONDS=600
```

### Disable Parallel Processing
```bash
# Force sequential processing
export RAGEX_USE_PARALLEL=false
export RAGEX_LOG_LEVEL=DEBUG  # Debug why parallel is disabled
```

## Variable Precedence

Variables are resolved in this order:

1. **Explicit Environment Variables** - Directly set values
2. **Auto-Detection** - System capability detection
3. **Configuration Defaults** - Built-in fallback values

### Override Examples

```bash
# Override auto-detected worker count
export RAGEX_MAX_WORKERS=4  # Even on 16-core system

# Override memory detection
export RAGEX_MEMORY_LIMIT_MB=1024  # Limit to 1GB

# Override batch sizing
export RAGEX_MIN_BATCH_SIZE=1
export RAGEX_MAX_BATCH_SIZE=5
```

## Validation and Limits

### Automatic Validation

The system automatically validates and constrains:

- **RAGEX_MAX_WORKERS**: 1-16 (reasonable bounds)
- **RAGEX_MEMORY_LIMIT_MB**: Minimum 256MB
- **RAGEX_TARGET_BATCH_TIME**: 0.1-10.0 seconds
- **RAGEX_CPU_THRESHOLD**: 0.1-1.0 range

### Size Suffixes

Memory variables support size suffixes:
- `k`, `kb`: Kilobytes (`RAGEX_LOG_MAX_SIZE=500k`)
- `m`, `mb`: Megabytes (`RAGEX_MEMORY_LIMIT_MB=1024m`)
- `g`, `gb`: Gigabytes (`RAGEX_MEMORY_LIMIT_MB=2g`)

## Troubleshooting Variables

### Performance Issues

```bash
# Reduce parallelism
export RAGEX_MAX_WORKERS=2
export RAGEX_TARGET_BATCH_TIME=0.5

# Increase logging
export RAGEX_LOG_LEVEL=DEBUG
```

### Memory Issues

```bash
# Strict memory limits
export RAGEX_WORKER_MEMORY_LIMIT_MB=128
export RAGEX_MEMORY_LIMIT_MB=512
export RAGEX_MAX_BATCH_SIZE=3
```

### Timeout Issues

```bash
# Increase timeouts for large files
export RAGEX_PROCESS_TIMEOUT_SECONDS=900
export RAGEX_TARGET_BATCH_TIME=5.0
```

## Environment Variable Checking

Use these commands to check current configuration:

```bash
# Show all RAGEX variables
env | grep RAGEX

# Show current parallel configuration
ragex configure

# Test with debug logging
RAGEX_LOG_LEVEL=DEBUG ragex index .
```

## Migration from Previous Versions

### Renamed Variables

| Old Variable | New Variable | Notes |
|--------------|--------------|-------|
| `LOG_LEVEL` | `RAGEX_LOG_LEVEL` | Still supported as fallback |

### New Variables

All parallel processing variables are new in this version:
- `RAGEX_USE_PARALLEL`
- `RAGEX_MAX_WORKERS`
- `RAGEX_*_BATCH_*`
- `RAGEX_*_MEMORY_*`

### Deprecated Variables

None currently deprecated, all previous variables continue to work.
