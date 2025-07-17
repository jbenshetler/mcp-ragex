# Embedding Configuration Guide

This guide explains how to configure the embedding models used by CodeRAG MCP's semantic search system.

## Overview

The embedding configuration system provides:
- Multiple pre-configured model presets with different speed/quality trade-offs
- Environment variable support for easy deployment configuration
- Custom model support for advanced users
- Centralized configuration management across all components

## Configuration Methods

### 1. Using Presets (Recommended)

The easiest way to configure embeddings is using one of the predefined presets:

```bash
# When building the index
uv run scripts/build_semantic_index.py . --preset fast      # Default
uv run scripts/build_semantic_index.py . --preset balanced   # Better quality
uv run scripts/build_semantic_index.py . --preset accurate   # Best quality
```

### 2. Environment Variables

Set environment variables to override defaults:

```bash
# Use a preset name
export RAGEX_EMBEDDING_MODEL=balanced

# Or specify a custom model
export RAGEX_EMBEDDING_MODEL=sentence-transformers/multi-qa-MiniLM-L6-cos-v1

# Configure ChromaDB settings
export RAGEX_CHROMA_PERSIST_DIR=/custom/path/to/db
export RAGEX_CHROMA_COLLECTION=my_custom_collection

# Configure HNSW index parameters for performance tuning
export RAGEX_HNSW_CONSTRUCTION_EF=100  # Lower = faster indexing (default: 100)
export RAGEX_HNSW_SEARCH_EF=50        # Lower = faster search (default: 50)
export RAGEX_HNSW_M=16               # Lower = less memory, faster (default: 16)
```

### 3. Programmatic Configuration

When using the API directly:

```python
from embedding_config import EmbeddingConfig

# Use a preset
config = EmbeddingConfig(preset="balanced")

# Or create a custom configuration
from embedding_config import ModelConfig

custom_config = ModelConfig(
    model_name="sentence-transformers/all-MiniLM-L12-v2",
    dimensions=384,
    max_seq_length=256,
    batch_size=32,
    normalize_embeddings=True
)
config = EmbeddingConfig(custom_model=custom_config)
```

## Available Presets

### Fast (Default)
- **Model**: `sentence-transformers/all-MiniLM-L6-v2`
- **Dimensions**: 384
- **Max sequence length**: 256
- **Batch size**: 64
- **Size**: ~80MB
- **Use case**: Quick prototyping, smaller codebases, CI/CD environments
- **Performance**: Fastest encoding speed, good quality

### Balanced
- **Model**: `sentence-transformers/all-mpnet-base-v2`
- **Dimensions**: 768
- **Max sequence length**: 384
- **Batch size**: 32
- **Size**: ~420MB
- **Use case**: Production environments, medium to large codebases
- **Performance**: Good balance of speed and quality

### Accurate
- **Model**: `sentence-transformers/all-roberta-large-v1`
- **Dimensions**: 1024
- **Max sequence length**: 512
- **Batch size**: 16
- **Size**: ~1.3GB
- **Use case**: Large codebases, when quality matters most
- **Performance**: Best quality, slower encoding

### Code-Small
- **Model**: `sentence-transformers/all-MiniLM-L6-v2` (fallback)
- **Dimensions**: 384
- **Max sequence length**: 256
- **Batch size**: 64
- **Size**: ~80MB
- **Use case**: Code-specific tasks (future: will use CodeBERT)
- **Note**: Currently uses general model, planned upgrade to code-specific

### Multilingual
- **Model**: `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`
- **Dimensions**: 384
- **Max sequence length**: 128
- **Batch size**: 32
- **Size**: ~470MB
- **Use case**: Codebases with multiple natural languages in comments/docs

## Choosing the Right Model

Consider these factors:

1. **Codebase size**:
   - Small (<1000 files): `fast`
   - Medium (1000-10000 files): `balanced`
   - Large (>10000 files): `accurate` or `balanced`

2. **Hardware constraints**:
   - Limited memory: `fast`
   - Good GPU/CPU: `balanced` or `accurate`

3. **Use case**:
   - Quick searches during development: `fast`
   - Production code intelligence: `balanced`
   - Critical code analysis: `accurate`

4. **Query types**:
   - Simple symbol lookups: `fast` is sufficient
   - Complex semantic queries: `balanced` or `accurate`
   - Cross-language documentation: `multilingual`

## Custom Models

You can use any sentence-transformers compatible model:

```bash
# Examples of other good models
export RAGEX_EMBEDDING_MODEL=sentence-transformers/multi-qa-mpnet-base-cos-v1
export RAGEX_EMBEDDING_MODEL=sentence-transformers/all-distilroberta-v1
export RAGEX_EMBEDDING_MODEL=sentence-transformers/msmarco-distilbert-base-v4
```

**Note**: When using custom models, the system will use default dimension values that may not match the actual model. The system will detect and log any mismatches but will continue using the actual model dimensions.

## HNSW Index Parameters

ChromaDB uses the HNSW (Hierarchical Navigable Small World) algorithm for efficient similarity search. You can tune these parameters for your specific performance needs:

### Parameters

1. **construction_ef** (default: 100)
   - Controls index build quality vs speed
   - Range: 10-500
   - Lower values = faster indexing but potentially lower search quality
   - Higher values = slower indexing but better search quality
   - Recommended: 50-100 for fast indexing, 200+ for quality

2. **search_ef** (default: 50)
   - Controls search quality vs speed
   - Range: 10-500
   - Must be >= number of results requested (k)
   - Lower values = faster search but potentially miss some results
   - Higher values = slower search but better recall
   - Recommended: 20-50 for fast search, 100+ for quality

3. **M** (default: 16)
   - Number of bi-directional links per node
   - Range: 2-100
   - Lower values = less memory usage and faster operations
   - Higher values = better recall but more memory and slower
   - Recommended: 8-16 for performance, 32+ for quality

### Performance Tuning Examples

#### Fast Search Configuration
```bash
# Optimize for speed over quality
export RAGEX_HNSW_CONSTRUCTION_EF=50
export RAGEX_HNSW_SEARCH_EF=20
export RAGEX_HNSW_M=8
```

#### Balanced Configuration (Default)
```bash
# Good balance of speed and quality
export RAGEX_HNSW_CONSTRUCTION_EF=100
export RAGEX_HNSW_SEARCH_EF=50
export RAGEX_HNSW_M=16
```

#### High Quality Configuration
```bash
# Optimize for quality over speed
export RAGEX_HNSW_CONSTRUCTION_EF=200
export RAGEX_HNSW_SEARCH_EF=100
export RAGEX_HNSW_M=32
```

### Programmatic HNSW Configuration

```python
from embedding_config import EmbeddingConfig, HNSWConfig

# Create custom HNSW configuration
hnsw_config = HNSWConfig(
    construction_ef=100,
    search_ef=50,
    M=16
)

# Use with embedding configuration
config = EmbeddingConfig(
    preset="fast",
    hnsw_config=hnsw_config
)
```

## Performance Considerations

### Indexing Time

Approximate indexing speeds (on a modern CPU):
- `fast`: ~1000 symbols/second
- `balanced`: ~400 symbols/second
- `accurate`: ~100 symbols/second

### Memory Usage

During indexing:
- `fast`: ~500MB RAM
- `balanced`: ~1GB RAM
- `accurate`: ~2GB RAM

### Search Performance

Query response times depend on both the model and HNSW parameters:
- Base latency: <100ms (embeddings are pre-computed)
- HNSW impact:
  - Low search_ef (20-50): +0-10ms
  - Medium search_ef (50-100): +10-30ms
  - High search_ef (100-200): +30-100ms
- Memory usage scales with M parameter:
  - M=8: ~50% less memory than M=16
  - M=16: baseline (default)
  - M=32: ~2x more memory than M=16

## Migration Between Models

To switch to a different model:

1. **Clear the existing index**:
   ```bash
   rm -rf ./chroma_db
   ```

2. **Rebuild with new model**:
   ```bash
   uv run scripts/build_semantic_index.py . --preset balanced --force
   ```

The system stores model information in the index metadata to prevent accidental mixing of embeddings from different models.

## Troubleshooting

### Model dimension mismatch
If you see warnings about dimension mismatches, the system will automatically use the actual model dimensions. This typically happens with custom models.

### Out of memory errors
Try:
1. Using a smaller model preset (`fast`)
2. Reducing batch size via custom configuration
3. Processing fewer files at once

### Slow indexing
Consider:
1. Using the `fast` preset for initial development
2. Building index on a more powerful machine and copying the `chroma_db` directory
3. Excluding unnecessary files via `.mcpignore`

## Future Enhancements

- **Code-specific models**: Integration with CodeBERT or similar models
- **Fine-tuning support**: Train models on your specific codebase
- **Hybrid models**: Combine multiple models for better results
- **Incremental updates**: Update embeddings only for changed files