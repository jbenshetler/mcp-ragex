# RAGex MCP Project Capabilities Matrix

*Generated from comprehensive codebase analysis - Last updated: 2025-08-08*

## 🔍 **Core Search Capabilities**

| **Feature** | **Implementation** | **Configuration** | **Files** |
|-------------|-------------------|------------------|-----------|
| **Semantic Search** | RAG + LLM re-ranking via ChromaDB + sentence-transformers | EmbeddingConfig with 3 presets (fast/balanced/accurate) | `src/ragex_core/semantic_searcher.py`, `src/ragex_core/embedding_config.py` |
| **Regex Search** | Ripgrep-based pattern matching | File type filtering, case sensitivity, multiline support | `src/ragex_core/regex_searcher.py`, `src/ragex_core/ripgrep_searcher.py` |
| **Symbol Extraction** | Tree-sitter AST parsing | Language-specific parsers (Python, JS, TS) for indexing only | `src/tree_sitter_enhancer.py` |
| **Auto-detection** | Query analysis heuristics | Environment/import/natural language patterns | `src/server.py:475-551` |

> **⚠️ Note**: Symbol search was removed. Tree-sitter is used only for symbol **extraction** during indexing. Semantic search queries the indexed symbols via ChromaDB.

## 🏗️ **Architecture & Infrastructure**

| **Component** | **Technology** | **Purpose** | **Key Files** |
|---------------|----------------|-------------|---------------|
| **MCP Server** | Official MCP Python SDK | LLM tool integration with 4 tools | `src/server.py` (1266 lines) |
| **Code Indexer** | Tree-sitter + embeddings | Symbol extraction & vectorization | `src/indexer.py` (430 lines) |
| **Vector Store** | ChromaDB with HNSW | Semantic similarity search | `src/ragex_core/vector_store.py` |
| **Pattern Matching** | Multi-level .rgignore system | File exclusion/inclusion with hot reload | `src/ragex_core/ignore/*.py` (9 files) |
| **Container Runtime** | Docker with project isolation | Secure execution environment | `docker/` (3 base images) |

## 🐳 **Docker & Deployment**

| **Image Type** | **Base** | **Purpose** | **Platforms** | **Size** |
|----------------|----------|-------------|---------------|----------|
| **CPU AMD64** | python:3.10 | Full development image | linux/amd64 | 2.4GB |
| **CPU ARM64** | python:3.10 | Full development image | linux/arm64 | 1.6GB |
| **CUDA AMD64** | nvidia/cuda:12.1-devel-ubuntu22.04 | GPU-accelerated inference | linux/amd64 only | 12.3GB |

**Build System**: 
- Makefile with layered builds
- Multi-arch support via buildx
- GHCR registry integration (`ghcr.io/jbenshetler/mcp-ragex`)
- Development targets: `make cpu`, `make cuda`, `make arm64`

## 🔧 **Configuration Systems**

| **System** | **Method** | **Environment Variables** | **Files** |
|------------|------------|--------------------------|-----------|
| **Logging** | Centralized with custom TRACE level | `RAGEX_LOG_LEVEL` (TRACE/DEBUG/INFO/WARN) | `src/utils/logging_setup.py` |
| **Embeddings** | 3 presets + custom models | `RAGEX_EMBEDDING_MODEL` (fast/balanced/accurate) | `src/ragex_core/embedding_config.py` |
| **Projects** | SHA256-based isolation (Developer-only) | `RAGEX_PROJECT_NAME`, `RAGEX_DATA_DIR` | `docker/common/entrypoint.sh` |
| **Ignore Files** | Multi-level .rgignore (Developer-only) | `RAGEX_IGNOREFILE_WARNING`, `RAGEX_ENABLE_WATCHDOG` | `src/ragex_core/ignore/manager.py` |
| **MCP Mode** | Path translation (Developer-only) | `RAGEX_MCP_WORKSPACE` | `src/server.py:239-277` |

### **Embedding Model Presets**

| **Preset** | **Model** | **Dimensions** | **Use Case** | **Speed (i9-7900X)** |
|------------|-----------|----------------|--------------|---------------------|
| **fast** | all-MiniLM-L6-v2 | 384 | Quick prototyping | ~64 batch/32GB |
| **balanced** | all-mpnet-base-v2 | 768 | Production use | ~32 batch/32GB |
| **accurate** | all-MiniLM-L12-v2 | 384 | High precision | ~32 batch/32GB |

> **End User Configuration**: Primarily configure `RAGEX_LOG_LEVEL` and `RAGEX_EMBEDDING_MODEL`. Settings marked "(Developer-only)" are for project maintainers and should not be modified by end users.

## 📱 **CLI & Interface**

| **Tool** | **Type** | **Purpose** | **Key Features** |
|----------|----------|-------------|------------------|
| **ragex** | Python CLI (2.0.0) | Main user interface | Project detection, daemon management, MCP mode |
| **MCP Tools** | JSON-RPC | LLM integration | 4 tools: `search_code`, `get_search_capabilities`, `search_code_simple`, `get_watchdog_status` |
| **Docker Commands** | Container exec | Isolated execution | `index`, `search`, `serve`, `ls`, `register`, `unregister`, `rm` |
| **Admin CLI** | Python module | Project management | List projects, cleanup, daemon status |

### **MCP Tool Schema**
This is a sample of the schema, not how it is actually implemented. 
```json
{
  "search_mode": ["auto", "semantic", "regex"],  // NO symbol mode
  "file_types": ["py", "js", "ts", "java", "cpp", "go", "rust"],
  "similarity_threshold": "0.0-1.0",
  "limit": "1-200"
}
```

## 🔐 **Security & Isolation**

| **Feature** | **Implementation** | **Configuration** |
|-------------|-------------------|------------------|
| **Project Isolation** | SHA256-based container naming | `{user_id}:{workspace_path}` hash |
| **Path Validation** | Container/host path mapping | `/workspace` mount point with translation |
| **Resource Limits** | Ripgrep constraints | Max 200 results, 30s timeout, 500 char patterns |
| **Input Sanitization** | Regex validation, file type allowlist | 23 allowed file extensions |
| **User Isolation** | Non-root container user | UID/GID mapping from host (any UID/GID supported) |
| **Read-only Workspace** | Docker volume mount | `/workspace:ro` prevents modification |

> **UID/GID Mapping**: The container runs as the host user (`docker run --user $(id -u):$(id -g)`), ensuring files created in `/data` volumes have correct ownership on the host. Any host UID/GID combination is supported.

## 📊 **Performance & Storage**

| **Component** | **Technology** | **Configuration** | **Tuning Parameters** |
|---------------|----------------|------------------|---------------------|
| **Vector Index** | HNSW algorithm | ChromaDB settings | `construction_ef=100`, `search_ef=50`, `M=16` |
| **Embeddings** | Batch processing | Model-specific batching | 32-64 items per batch |
| **Caching** | LRU cache | Max 10,000 ignore patterns | File modification tracking with checksums |
| **Log Rotation** | Docker limits | 50MB max, 5 files | Configurable via compose |
| **Indexing Speed** | Tree-sitter parsing | ~100 symbols/second (i9-7900X) | Batch processing |
| **Search Speed** | ChromaDB + ripgrep | <100ms typical | Depends on corpus size |

## 🧪 **Testing Infrastructure**

| **Test Type** | **Framework** | **Coverage** | **Files** |
|---------------|---------------|--------------|-----------|
| **MCP Integration** | pytest-asyncio + UV deps | Protocol compliance, 2 search modes | `tests/test_mcp_with_uv.py` |
| **Unit Tests** | pytest | Core functionality | `tests/test_server.py` |
| **Claude Integration** | Custom runners | In-environment testing | `tests/claude_mcp_test_runner.py` |

> **⚠️ Test Coverage Gap**: Symbol search tests exist but test non-functional code paths

## 🔄 **Data Management**

| **Feature** | **Implementation** | **Container Path** | **Host Mount** | **Format** |
|-------------|-------------------|------------------|----------------|------------|
| **Project Data** | Per-project isolation | `/data/projects/{project_id}/` | Docker volume | Directory structure |
| **Vector Store** | ChromaDB persistence | `{project_data_dir}/chroma_db/` | Docker volume | SQLite + HNSW |
| **Model Cache** | Shared across projects | `/data/models/` | Docker volume | HuggingFace cache |
| **Checksums** | File change tracking | In-memory + metadata | N/A | SHA256 hashes |
| **Project Registry** | Daemon management | Socket communication | N/A | JSON metadata |

> **Docker Volumes**: All `/data` paths are container paths. They map to named Docker volumes (e.g., `ragex_user_1000`) for persistence on the host.

### **Project Naming Scheme**

```bash
# Project ID format
PROJECT_ID = f"ragex_{user_id}_{sha256(f'{user_id}:{workspace_path}')[:16]}"

# Example
ragex_1000_a1b2c3d4e5f6g7h8  # User 1000, unique workspace hash
```

## 🌐 **Language Support**

| **Language** | **Tree-sitter Parser** | **Symbol Extraction** | **Search Support** |
|--------------|------------------------|----------------------|-------------------|
| **Python** | ✅ tree-sitter-python | Functions, classes, methods, docstrings | Full semantic |
| **JavaScript** | ✅ tree-sitter-javascript | Functions, classes, imports | Full semantic |
| **TypeScript** | ✅ tree-sitter-typescript | Types, interfaces, generics | Full semantic |
| **Java** | ❌ Ripgrep only | Pattern matching only | Regex only |
| **C/C++** | 🔄 **Planned** | Pattern matching only | Regex only |
| **Go** | 🔄 **Planned** | Pattern matching only | Regex only |
| **Rust** | ❌ Ripgrep only | Pattern matching only | Regex only |
| **19+ Others** | ❌ Ripgrep file types | Pattern matching only | Regex only |

> **Expansion Opportunity**: C/C++ and Go Tree-sitter parsers are planned. Adding more parsers would extend semantic search to additional languages.

## ⚡ **Advanced Features**

| **Feature** | **Status** | **Implementation** | **Configuration** |
|-------------|------------|-------------------|------------------|
| **Hot Reloading** | ✅ Available | Watchdog monitoring of .rgignore files | `RAGEX_ENABLE_WATCHDOG=true` |
| **Feature Reranking** | ✅ Active | LLM-based result improvement for fast, high-quality matches | `src/ragex_core/reranker.py` |
| **Path Translation** | ✅ Complete | Container/host path mapping | Automatic in MCP mode |
| **Incremental Indexing** | ✅ Available | Checksum-based file tracking | Automatic change detection |
| **Multi-arch Support** | ✅ Complete | AMD64, ARM64 builds | Cross-compilation via buildx |
| **GPU Acceleration** | ✅ Available | CUDA images for faster inference | Requires NVIDIA runtime |
| **Daemon Mode** | ✅ Active | Background indexing with file watching | Socket-based communication |

## 🔧 **Maintenance & Cleanup**

### **Dead Code Identified**

| **File** | **Issue** | **Lines** | **Action Needed** |
|----------|-----------|-----------|-------------------|
| `src/server.py` | References non-existent `symbol_available` | 452 | Remove reference |
| `src/server.py` | Auto-detection returns "symbol" | 549 | Route to "semantic" |
| `src/server.py` | Dead `execute_symbol_search()` function | 1155-1167 | Remove function |
| `src/server.py` | Capabilities lists "symbol" mode | 1006-1021 | Remove from capabilities |
| Documentation | Multiple symbol search references | Various | Update to reflect removal |
| Tests | Symbol search test cases | `tests/test_mcp_with_uv.py` | Remove or redirect |

### **Configuration Cleanup Opportunities**

1. **Environment Variables**: Standardize `RAGEX_*` prefixes
2. **Docker Images**: Optimize layer caching and size
3. **Log Levels**: Ensure TRACE level works consistently
4. **Error Handling**: Improve MCP protocol error responses

## 📈 **Performance Benchmarks**

| **Operation** | **Speed** | **Resource Usage** | **Scalability** |
|---------------|-----------|-------------------|-----------------|
| **Indexing** | ~100 symbols/sec (i9-7900X) | CPU + disk I/O | Linear with codebase size |
| **Semantic Search** | <100ms | RAM + ChromaDB | Sub-linear with HNSW |
| **Regex Search** | <50ms | CPU via ripgrep | Linear with file count |
| **Container Startup** | ~2-5 seconds | Docker overhead | Constant |
| **Model Loading** | ~10-30 seconds | GPU/CPU + RAM | One-time per container |

---

## 🎯 **Summary**

RAGex MCP is a sophisticated, production-ready code search system with:

- **2 Active Search Modes**: Semantic (AI-powered) and Regex (pattern-based)
- **Security Features**: Project isolation, path validation, resource limits
- **Advanced AI**: RAG + LLM re-ranking, ChromaDB vector storage, sentence transformers
- **Docker-First**: Multi-arch support, layered builds, GHCR distribution
- **MCP Integration**: 4 tools for seamless LLM integration
- **Developer Experience**: Hot reloading, progress indicators, comprehensive logging

The system successfully bridges traditional code search (ripgrep) with modern AI capabilities (embeddings) while maintaining security and performance through containerization.
