# Parallel Symbol Extraction in RAGex

This document describes the parallel symbol extraction system implemented in RAGex for high-performance code indexing using tree-sitter parsers with true multiprocessing.

## Overview

The parallel symbol extraction system provides significant performance improvements for large codebases by utilizing multiple CPU cores to process files concurrently. The system bypasses Python's Global Interpreter Lock (GIL) using `ProcessPoolExecutor` and implements intelligent batching, shared parser optimization, and automatic system tuning.

## Architecture

### Core Components

```
┌─────────────────────────────────────────────────────────────┐
│                    RAGex Indexer                            │
│  ┌─────────────────┐    ┌─────────────────────────────────┐ │
│  │   Auto-detect   │────│   Parallel Symbol Extractor    │ │
│  │   Sequential    │    │                                 │ │
│  │   Fallback      │    │  ┌─────────────────────────────┐ │ │
│  └─────────────────┘    │  │    ProcessPoolExecutor     │ │ │
│                         │  │                             │ │ │
│                         │  │  Worker 1   Worker 2  ...  │ │ │
│                         │  │     │         │             │ │ │
│                         │  │     ▼         ▼             │ │ │
│                         │  │ TreeSitter TreeSitter       │ │ │
│                         │  └─────────────────────────────┘ │ │
│                         │                                 │ │
│                         │  ┌─────────────────────────────┐ │ │
│                         │  │   Shared Parser Pool       │ │ │
│                         │  │   • Language Objects       │ │ │
│                         │  │   • Query Patterns         │ │ │
│                         │  │   • Parser Instances       │ │ │
│                         │  └─────────────────────────────┘ │ │
│                         │                                 │ │
│                         │  ┌─────────────────────────────┐ │ │
│                         │  │   Batch Processing          │ │ │
│                         │  │   • Language Grouping      │ │ │
│                         │  │   • Dynamic Sizing         │ │ │
│                         │  │   • Load Balancing         │ │ │
│                         │  └─────────────────────────────┘ │ │
│                         └─────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

### Key Files

- **`src/parallel_symbol_extractor.py`** - Main parallel extraction engine
- **`src/shared_parser_pool.py`** - Optimized parser management and sharing
- **`src/parallel_config.py`** - Auto-detection and configuration management  
- **`src/indexer.py`** - Updated to use parallel extraction automatically

## Performance Characteristics

### Expected Speedups

| System Type | Cores | Expected Speedup | Memory Usage |
|-------------|-------|------------------|--------------|
| Laptop      | 4-8   | 2-4x            | 1-2GB        |
| Workstation | 8-16  | 4-8x            | 2-4GB        |
| Server      | 16+   | 6-12x           | 4-8GB        |
| Container   | 2-4   | 1.5-3x          | 0.5-1GB      |

### Scaling Factors

- **File Count**: Most effective with 10+ files
- **File Size**: Better performance with medium-sized files (1KB-100KB)
- **Language Mix**: Improved efficiency when files share languages
- **System Resources**: Scales with available CPU cores and memory

## Configuration

### Automatic Configuration

The system automatically detects optimal settings based on:

- **CPU Cores**: Available processor count
- **Memory**: Available RAM and per-process limits
- **Containerization**: Docker/container environment detection
- **System Load**: Current CPU utilization
- **File Count**: Number of files to process

### Environment Variables

#### Core Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `RAGEX_USE_PARALLEL` | `true` | Enable/disable parallel processing |
| `RAGEX_MAX_WORKERS` | auto-detect | Maximum number of worker processes |

#### Batch Processing

| Variable | Default | Description |
|----------|---------|-------------|
| `RAGEX_MIN_BATCH_SIZE` | auto-detect | Minimum files per batch |
| `RAGEX_MAX_BATCH_SIZE` | auto-detect | Maximum files per batch |
| `RAGEX_TARGET_BATCH_TIME` | auto-detect | Target processing time per batch (seconds) |

#### Memory Management

| Variable | Default | Description |
|----------|---------|-------------|
| `RAGEX_MEMORY_LIMIT_MB` | auto-detect | Total memory limit in MB |
| `RAGEX_WORKER_MEMORY_LIMIT_MB` | auto-detect | Per-worker memory limit in MB |
| `RAGEX_CPU_THRESHOLD` | auto-detect | CPU usage threshold for scaling |

#### Advanced Options

| Variable | Default | Description |
|----------|---------|-------------|
| `RAGEX_ENABLE_SHARED_PARSERS` | `true` | Enable shared parser optimization |
| `RAGEX_PROCESS_TIMEOUT_SECONDS` | `300` | Worker process timeout |

### Configuration Examples

#### High-Performance Server
```bash
export RAGEX_MAX_WORKERS=12
export RAGEX_MAX_BATCH_SIZE=15
export RAGEX_TARGET_BATCH_TIME=2.0
export RAGEX_MEMORY_LIMIT_MB=4096
```

#### Resource-Constrained Environment
```bash
export RAGEX_MAX_WORKERS=2
export RAGEX_MAX_BATCH_SIZE=5
export RAGEX_TARGET_BATCH_TIME=0.5
export RAGEX_MEMORY_LIMIT_MB=512
```

#### Disable Parallel Processing
```bash
export RAGEX_USE_PARALLEL=false
```

## Implementation Details

### Worker Process Architecture

Each worker process:

1. **Initializes** its own tree-sitter parser pool
2. **Receives** a batch of files to process
3. **Extracts** symbols using tree-sitter
4. **Returns** results to the main process
5. **Handles** errors gracefully without affecting other workers

### Batch Processing Strategy

The system creates optimal batches by:

1. **Grouping** files by programming language
2. **Sorting** by file size (largest first)
3. **Estimating** processing time per file
4. **Creating** batches that target a specific processing time
5. **Balancing** load across available workers

### Shared Memory Optimization

Parser optimization includes:

- **Language Objects**: Shared tree-sitter language instances
- **Query Patterns**: Pre-compiled query patterns for symbol extraction
- **Parser Instances**: Reusable parser objects per language
- **Process-Local Caching**: File content and AST caching within workers

### Error Handling and Recovery

The system provides robust error handling:

- **Process Isolation**: Worker failures don't affect other workers
- **Graceful Degradation**: Falls back to sequential processing on failure
- **Timeout Protection**: Prevents hanging on problematic files
- **Resource Monitoring**: Tracks memory and CPU usage

## Performance Monitoring

### Built-in Metrics

The parallel extractor tracks:

- **Processing Time**: Total and per-file timing
- **Worker Utilization**: How effectively workers are used
- **Batch Efficiency**: Time per batch and load balancing
- **Success Rate**: Files processed successfully vs failed
- **Memory Usage**: Peak memory consumption per worker

### Progress Reporting

Real-time progress includes:

- **Files Processed**: Current count and total
- **Processing Rate**: Files per second
- **Estimated Time**: Remaining processing time
- **Worker Status**: Active workers and current tasks

### Example Output

```
🔍 Using parallel extraction for 1,247 files
📊 Configuration: 8 workers, batch size 2-12, target 1.5s
⚡ Processing rate: 23.4 files/second
📈 Progress: 1,247/1,247 files (100%) - ETA: 0m 0s
✅ Completed: 1,238 successful, 9 failed in 53.2s (23.4x speedup)
```

## Integration with RAGex

### Automatic Integration

The parallel extractor integrates seamlessly:

1. **Auto-Detection**: Automatically used when available
2. **Fallback**: Falls back to sequential processing if needed
3. **API Compatibility**: Maintains existing TreeSitterEnhancer API
4. **Configuration**: Uses existing RAGex configuration patterns

### Docker Integration

In Docker environments:

- **Resource Detection**: Adapts to container resource limits
- **Shared Volumes**: Efficiently handles mounted code directories
- **Memory Management**: Respects container memory constraints
- **Process Limits**: Works within container process restrictions

### MCP Server Integration

The parallel extractor works with:

- **Claude Code**: Provides faster symbol extraction for AI assistants
- **Search Operations**: Accelerates semantic search index building
- **Real-time Updates**: Efficiently processes file changes
- **Background Indexing**: Non-blocking parallel processing

## Best Practices

### When to Use Parallel Processing

**Ideal Scenarios:**
- Large codebases (100+ files)
- Multi-core systems
- Batch indexing operations
- Initial project setup

**Less Effective:**
- Small projects (<10 files)
- Single-core systems
- Memory-constrained environments
- Real-time file watching

### Optimization Tips

1. **File Organization**: Keep similar files together
2. **Resource Allocation**: Allow 200-500MB RAM per worker
3. **Batch Sizing**: Let auto-detection choose optimal sizes
4. **Language Support**: Works best with Python, JavaScript, TypeScript
5. **Monitoring**: Use verbose logging to tune performance

### Troubleshooting

#### Common Issues

**High Memory Usage:**
```bash
export RAGEX_MAX_WORKERS=4
export RAGEX_WORKER_MEMORY_LIMIT_MB=256
```

**Slow Performance:**
```bash
export RAGEX_TARGET_BATCH_TIME=0.5
export RAGEX_MAX_BATCH_SIZE=5
```

**Process Timeouts:**
```bash
export RAGEX_PROCESS_TIMEOUT_SECONDS=600
```

#### Debugging

Enable verbose logging:
```bash
export RAGEX_LOG_LEVEL=DEBUG
```

Check system resources:
```bash
ragex configure  # Shows current configuration
```

## Migration and Compatibility

### Backward Compatibility

The parallel system maintains full compatibility:

- **Existing APIs**: All existing methods work unchanged  
- **Configuration**: Previous settings continue to work
- **Fallback**: Automatically falls back to sequential processing
- **Results**: Identical symbol extraction results

### Migration Path

No migration required - the system:

1. **Detects** availability automatically
2. **Configures** optimal settings
3. **Falls back** gracefully if needed
4. **Maintains** existing behavior

## Future Enhancements

### Planned Improvements

- **GPU Acceleration**: CUDA support for semantic processing
- **Distributed Processing**: Multi-machine parallel processing
- **Streaming Results**: Real-time result streaming
- **Advanced Caching**: Cross-session parser caching
- **Language Models**: Integration with code-specific language models

### Performance Targets

- **20x Speedup**: On high-end multi-core systems
- **Memory Efficiency**: <100MB per worker process
- **Scalability**: Support for 10,000+ file codebases
- **Real-time Processing**: Sub-second incremental updates