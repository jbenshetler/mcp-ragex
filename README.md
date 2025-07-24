# CodeRAG MCP Server

A secure, intelligent **MCP (Model Context Protocol) server** for **Claude** and AI assistants, providing semantic code search using **RAG**, **tree-sitter**, and **ripgrep**. Search code using natural language, symbols, or regex patterns.

## What is CodeRAG?

CodeRAG is an **MCP server** that enhances **Claude Code** and other AI coding assistants with advanced code search capabilities. It combines:
- **RAG (Retrieval-Augmented Generation)** for semantic code search
- **Tree-sitter** for language-aware symbol search  
- **Ripgrep** for blazing-fast regex search

## Why CodeRAG?

Unlike simple grep-based tools, CodeRAG understands code semantically:

| Feature | grep/ripgrep | CodeRAG |
|---------|-------------|---------|
| Find "auth functions" | ❌ | ✅ Semantic search |
| Find `validateUser()` | ✅ | ✅ Symbol-aware search |
| Cross-language patterns | ❌ | ✅ Coming soon |
| Natural language queries | ❌ | ✅ "functions that handle errors" |

## Features

### 🔍 **Intelligent Search Modes**
- **Auto-detection**: Automatically chooses the best search mode based on query patterns
- **Regex mode**: Fast pattern matching with ripgrep for exact patterns
- **Symbol mode**: Language-aware symbol search using Tree-sitter
- **Semantic mode**: Natural language search using sentence-transformers embeddings

### 🚀 **Performance & Security**
- **Fast code search** using ripgrep with regex support
- **Security-first design** with input validation and path restrictions
- **File type filtering** supporting 30+ programming languages
- **File exclusion patterns** using gitignore syntax (.mcpignore support)
- **Configurable limits** to prevent resource exhaustion
- **JSON-RPC interface** following MCP standards

### 🧠 **AI-Powered Features**
- **Semantic code search** using sentence-transformers embeddings
- **Query enhancement** with abbreviation expansion and context addition
- **Intelligent fallback** when primary search mode fails
- **Teaching system** that guides Claude Code to optimal search usage

## Quick Start

To set up CodeRAG MCP Server, you'll need to install Claude Code, ripgrep, and Python dependencies.


### Prerequisites
1. **Install Claude Code**
[![Install with Claude Code](https://img.shields.io/badge/Install-Claude_Code-blue)](https://claude.ai)

    ```bash
    claude mcp add coderag [https://github.com/YOUR_USERNAME/mcp-coderag](https://github.com/YOUR_USERNAME/mcp-coderag)
    ````
2.  **Install ripgrep:**
    ```bash
    # macOS
    brew install ripgrep

    # Ubuntu/Debian
    sudo apt-get install ripgrep

    # Windows
    choco install ripgrep
    ```
3.  **Install Python dependencies:**
    ```bash
    # Using uv (recommended)
    uv pip install -r requirements.txt

    # Or using pip
    pip install -r requirements.txt
    ```

### Setup Semantic Search (Optional)

To enable semantic search capabilities:

1. **Build the semantic index:**
   ```bash
   # Use default fast model (~80MB)
   uv run scripts/build_semantic_index.py . --stats
   
   # Or choose a different preset
   uv run scripts/build_semantic_index.py . --preset balanced --stats  # ~420MB model
   uv run scripts/build_semantic_index.py . --preset accurate --stats  # ~1.3GB model
   ```
   
   This will:
   - Automatically install required dependencies (sentence-transformers, chromadb, etc.)
   - Download the sentence-transformer model (size varies by preset)
   - Index all Python/JS/TS files in the current directory
   - Create a ChromaDB vector database in `./chroma_db`

2. **Check index status:**
   ```bash
   uv run scripts/check_index.py
   ```

### Install MCP Server (One-time setup)

Install the MCP server with all dependencies in an isolated environment:

```bash
cd /path/to/mcp-ragex
./scripts/install_mcp_server.sh
```

This creates a dedicated virtual environment (`.mcp_venv`) with all required dependencies, ensuring the MCP server works consistently across all projects.

### Register MCP Server

After installation, register the MCP server from your project directory:

```bash
cd /path/to/your/project

# Option 1: Use the flexible wrapper (recommended)
claude mcp add ragex /path/to/mcp-ragex/mcp_ragex.sh --scope project

# Option 2: Use the isolated environment directly
claude mcp add ragex /path/to/mcp-ragex/mcp_server_isolated.sh --scope project
```

**Important**: After registering, restart Claude Code completely for the changes to take effect.

#### Verify Semantic Search

After registration and restart, verify semantic search is working:
1. Check `/tmp/mcp_coderag.log` for "Semantic search ENABLED" message
2. Test with: `search_code(query="your search terms", mode="semantic")`

#### Alternative Registration (Legacy)
```bash
# Uses current project's Python environment (may have missing dependencies)
claude mcp add ragex /path/to/mcp-ragex/mcp_coderag_pwd.sh --scope project
```

#### Unregister MCP Server
```bash
claude mcp remove ragex --scope project
```


### Running the Server

```bash
# Using uv (recommended)
uv run src/server.py

# Or using the wrapper script
./mcp_coderag.sh
```

### Testing

```bash
# Run test suite
uv run tests/test_server.py

# Run with pytest (if installed)
pytest tests/
```

## Integration

### Claude Code (CLI)

#### Option 1: Using CLI Command (Recommended)

Add the MCP server using the Claude Code CLI:

```bash
claude mcp add coderag /home/jeff/clients/mcp-ragex/mcp_coderag.sh --scope project
```

Expected output:
```
Added stdio MCP server coderag with command: /home/jeff/clients/mcp-ragex/mcp_coderag.sh  to project config
```

#### Option 2: Using .mcp.json

Create a `.mcp.json` file in your project root:

```json
{
  "mcpServers": {
    "coderag": {
      "command": "/path/to/mcp-ragex/mcp_coderag.sh"
    }
  }
}
```

#### Option 3: Direct Python Command

If you prefer not to use the wrapper script:

```bash
# From within the mcp-ragex directory
claude mcp add coderag uv run src/server.py --scope project
```

### Claude Desktop (App)

Add to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "coderag": {
      "command": "python",
      "args": ["/path/to/mcp-ragex/src/server.py"]
    }
  }
}
```

**Note:** After updating the configuration, restart Claude Code or Claude Desktop for the changes to take effect.

### Verifying MCP Connection

After configuration, verify the MCP server is connected:

```bash
# In Claude Code, use the /mcp command
/mcp
```

This will show the status of all configured MCP servers. You should see `coderag` in the list.

## Usage Examples

### **Example Semantic Search**
This is what happened in the CLI:
```
● Let me try a broader semantic search:

● Let me search for admin endpoints:
 ⎿  Interrupted by user

> /exit
 ⎿  (no content)

> Try the ragex semantic search again.

● Task(Search for reindex endpoints)
 ⎿  Done (8 tool uses · 79.3k tokens · 1m 32.2s)

● Based on the search results, I found the department reindexing endpoints. The main force reindex endpoint is:

 POST /admin/reindex/department in /docprocessor/workflows_api.py (line 834)

```

And this is what the Ctrl-R logs show:
```
● I'll search for the function that adds documents to OpenSearch and check the field structure, then verify all 11 documents have extracted text.

● Task(Task: Find OpenSearch indexing function

   Prompt: Search for the function that indexes documents to OpenSearch. Look for:
   1. Functions that create or update documents in OpenSearch
   2. The field names used when indexing, particularly for extracted text
   3. Index operations, PUT or POST requests to OpenSearch
   4. Document structure being sent to OpenSearch

   Use search terms like:
   - opensearch index document
   - _doc PUT POST
   - index_document
   - create_document
   - extracted_text content text)
 ⎿  Search(pattern: "index.*document|create.*document|update.*document", path: "undefined")
      ⎿  Found 55 files
         /home/jeff/clients/search/contextsearch/tests/ui/README.md
         /home/jeff/clients/search/contextsearch/tests/ocr/output_metadata.json
         /home/jeff/clients/search/contextsearch/tests/ocr/output_rmeta_fixed.json
         /home/jeff/clients/search/contextsearch/tests/needs_porting/test_workflow_implementation.py
         /home/jeff/clients/search/contextsearch/tests/obsolete/test_workflow_celery_integration.py
         /home/jeff/clients/search/contextsearch/tests/obsolete/test_workflow_integration.py
         /home/jeff/clients/search/contextsearch/tests/docprocessor/test_workflows_real_files.py
         /home/jeff/clients/search/contextsearch/tests/functional/cache/test_cache_repopulation.py
         /home/jeff/clients/search/contextsearch/tests/functional/cache/test_comprehensive_cache_validation.py
         /home/jeff/clients/search/contextsearch/tests/functional/integration/filesystem_scanner.py
         /home/jeff/clients/search/contextsearch/tests/functional/nlp/test_batch_size_one.py
         /home/jeff/clients/search/contextsearch/tests/functional/search/test_date_filtering.py
         /home/jeff/clients/search/contextsearch/tests/functional/search/test_entity_filtering.py
         /home/jeff/clients/search/contextsearch/tests/functional/search/test_force_reindexing.py
         /home/jeff/clients/search/contextsearch/samples/simulate_tasks.py
```

### 🔍 **Intelligent Search Modes**

#### Auto-Detection (Recommended)
```bash
# Claude Code automatically detects the best search mode
search_code("DatabaseConnection")              # → symbol mode
search_code("functions that handle auth")      # → semantic mode  
search_code("error.*Exception")                # → regex mode
```

#### Explicit Mode Selection
```bash
# Symbol search - when you know exact names
search_code("AuthenticationService", mode="symbol")

# Semantic search - when you know the concept
search_code("functions that validate user input", mode="semantic")

# Regex search - when you know the pattern
search_code("handleError.*Exception", mode="regex")
```

### 🧠 **Semantic Search Examples**

```bash
# Find authentication-related code
search_code("functions that handle user authentication")

# Find error handling patterns
search_code("error handling for database connections")

# Find file processing code
search_code("code that processes uploaded files")

# Find validation logic
search_code("functions that validate user input")
```

### 📋 **Symbol Search Examples**

```bash
# Find specific classes
search_code("UserService", mode="symbol")

# Find specific functions
search_code("validateInput", mode="symbol")

# Find methods
search_code("submitToQueue", mode="symbol")
```

### 🔧 **Regex Search Examples**

```bash
# Find async functions
search_code("async def", mode="regex")

# Find TODO comments
search_code("TODO|FIXME", mode="regex")

# Find error handling blocks
search_code("try.*except", mode="regex")
```

### 🛠 **Advanced Features**

#### Capability Discovery
```bash
# Check available search modes
get_search_capabilities()
```

#### Simple Search Interface
```bash
# Just search - auto-detects everything
search_code_simple("database connection error")
```

#### Raw Output Format
```bash
search_code("submit_file", format="raw")
```
Returns simple `file:line` format for programmatic use.

### 📁 **File Type and Path Filtering**

```bash
# Search only Python files
search_code("class.*User", file_types=["py"])

# Search specific directories
search_code("test_", paths=["tests", "src/tests"])

# Combine filters
search_code("async def", file_types=["py"], paths=["src"])
```

## Security Features

1. **Pattern validation**: Regex patterns are validated and length-limited
2. **Path restriction**: Searches are confined to project directory
3. **Resource limits**: Maximum results and timeout protection
4. **Input sanitization**: All inputs are validated before execution
5. **No shell injection**: Direct subprocess execution without shell

## Architecture

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│   Claude Code   │────▶│   MCP Server     │────▶│ Search Engines  │
│                 │     │                  │     │                 │
└─────────────────┘     └──────────────────┘     └─────────────────┘
                                │                         │
                                ▼                         ▼
                        ┌──────────────────┐     ┌─────────────────┐
                        │ Auto-Detection   │     │ • Ripgrep       │
                        │ & Mode Selection │     │ • Tree-sitter   │
                        └──────────────────┘     │ • ChromaDB      │
                                │                │ • Embeddings    │
                                ▼                └─────────────────┘
                        ┌──────────────────┐
                        │ Query Enhancement│
                        │ & Fallback Logic │
                        └──────────────────┘
                                │
                                ▼
                        ┌──────────────────┐
                        │ Security &       │
                        │ Validation       │
                        └──────────────────┘
```

### Search Mode Flow

1. **Query Analysis**: Auto-detect search intent (regex, symbol, semantic)
2. **Query Enhancement**: Expand abbreviations, add context
3. **Primary Search**: Execute using detected/specified mode
4. **Fallback Logic**: Try alternative modes if no results
5. **Result Formatting**: Return navigation-friendly results with metadata
6. **Guidance**: Provide suggestions for better queries when needed

## Supported File Types

1. All file types are supported for regex search. 

1. These file types are supported for symbol and semantic search:
  `py`, `js`, `jsx`, `ts`, `tsx`, `cpp`, `c`, `html`, `css`

## File Exclusions

The server provides multiple ways to exclude files from search results:

### Default Exclusions
These patterns are automatically excluded (see full list in `src/pattern_matcher.py`):
- `.venv/**`, `venv/**` - Virtual environments
- `__pycache__/**`, `*.pyc` - Python cache files  
- `node_modules/**` - Node.js dependencies
- `.git/**` - Git repository data
- `*.log`, `*.swp`, `*.swo` - Log and swap files
- `.mypy_cache/**`, `.pytest_cache/**`, `.tox/**` - Python tool caches
- `.DS_Store`, `Thumbs.db` - OS files

### Custom Exclusions (.mcpignore)
Create a `.mcpignore` file in your project root using gitignore syntax:

```gitignore
# Example .mcpignore
test_output/
*.tmp
docs/**/*.generated.md
!important.log  # Negation pattern (include this file)

# Patterns are relative to project root
src/generated/
*.min.js

# Invalid patterns are logged and skipped
```

**Notes:**
- Place `.mcpignore` in your project root directory
- Uses standard gitignore syntax
- Invalid patterns are warned about but don't break the server
- See `.mcpignore.example` for a comprehensive example

### Search-time Exclusions
Override or add exclusions for specific searches:

```json
{
  "tool": "search_code",
  "arguments": {
    "pattern": "TODO",
    "exclude_patterns": ["tests/**", "*.spec.js"],
    "respect_gitignore": true  // default: true
  }
}
```

### Exclusion Priority
1. Default exclusions (always applied)
2. `.gitignore` files (if `respect_gitignore: true`)
3. `.mcpignore` patterns (if file exists)
4. API `exclude_patterns` (if provided)

## Performance Considerations

### Search Performance
- **Regex searches**: Sub-second response using ripgrep
- **Symbol searches**: Fast Tree-sitter parsing with caching
- **Semantic searches**: ~50-100ms for 1000+ symbols
- **Timeout protection**: 30-second limit for all searches
- **Result limits**: Maximum 200 matches to prevent overload

### Resource Usage
- **Memory**: ~300MB during semantic search, ~100MB baseline
- **Storage**: ~1MB per 1000 symbols indexed
- **Model cache**: ~420MB for sentence-transformer model
- **Index size**: ~32MB for 77 symbols (typical small project)

### Optimization Features
- **Intelligent caching**: Tree-sitter results cached per file
- **Efficient exclusions**: Skip unwanted files before processing
- **Streaming JSON**: Large result sets processed incrementally
- **Batch embeddings**: Process multiple symbols efficiently

## Semantic Search Details

### Model Information
- **Model**: `sentence-transformers/all-mpnet-base-v2`
- **Dimensions**: 768-dimensional embeddings
- **Quality**: Best general-purpose model for semantic similarity
- **Speed**: ~36 symbols/second indexing, <100ms search

### Index Statistics
For a typical project (77 symbols):
- **Indexing time**: 2.1 seconds
- **Functions**: 70 indexed
- **Classes**: 7 indexed  
- **Index size**: 32.5 MB
- **Languages**: Python, JavaScript, TypeScript supported

### Indexing Strategy
- **Pre-indexing**: Build index before starting MCP server
- **Incremental updates**: Update individual files as needed
- **Metadata tracking**: Track file changes and index freshness
- **Progress visibility**: Show indexing progress and timing

## Teaching System

The MCP server actively teaches Claude Code how to use search effectively:

### Capability Discovery
- **Auto-detection examples**: Shows what query patterns trigger each mode
- **Mode recommendations**: Suggests best mode for different use cases
- **Fallback explanations**: Explains why fallbacks occurred

### Query Guidance
- **Enhancement suggestions**: How to improve queries for better results
- **Alternative approaches**: Different ways to search for the same concept
- **Pattern examples**: Common regex and semantic query patterns

### Learning Features
- **Rich tool descriptions**: Detailed documentation in tool schemas
- **Response metadata**: Information about search mode selection
- **Failure guidance**: Helpful suggestions when searches fail

## Configuration

### Embedding Model Configuration

The semantic search system supports multiple embedding models with different trade-offs:

#### Model Presets

| Preset | Model | Dimensions | Size | Use Case |
|--------|-------|------------|------|----------|
| `fast` (default) | all-MiniLM-L6-v2 | 384 | ~80MB | Quick prototyping, smaller codebases |
| `balanced` | all-mpnet-base-v2 | 768 | ~420MB | Good balance of speed and quality |
| `accurate` | all-roberta-large-v1 | 1024 | ~1.3GB | Best quality, larger codebases |

#### Configuration Methods

1. **Command-line preset:**
   ```bash
   uv run scripts/build_semantic_index.py . --preset balanced
   ```

2. **Environment variable:**
   ```bash
   # Use a preset
   export RAGEX_EMBEDDING_MODEL=balanced
   
   # Or specify a custom model
   export RAGEX_EMBEDDING_MODEL=sentence-transformers/codebert-base
   ```

3. **Other environment variables:**
   ```bash
   # ChromaDB settings
   export RAGEX_CHROMA_PERSIST_DIR=/custom/path/to/db
   export RAGEX_CHROMA_COLLECTION=my_project_embeddings
   ```

### File Exclusion (.mcpignore)

Create a `.mcpignore` file in your project root to exclude files from indexing:

```gitignore
# Dependencies
node_modules/
venv/
.venv/

# Build outputs
dist/
build/
*.min.js

# Large files
*.csv
*.json
data/

# Test files (optional)
*_test.py
*.test.js
```

The system automatically excludes common directories like `.git`, `__pycache__`, etc.

## Future Enhancements

### Planned Features
- [ ] **CodeBERT integration**: Upgrade to code-specific embeddings
- [ ] **Incremental indexing**: Automatic index updates on file changes
- [ ] **Cross-language search**: Find similar patterns across languages
- [ ] **Search history**: Remember and optimize frequent queries
- [ ] **Custom embeddings**: Train project-specific models

### Performance Improvements
- [ ] **Hybrid search**: Combine keyword and semantic results
- [ ] **Query optimization**: Learn from usage patterns
- [ ] **Caching strategies**: Cache frequent semantic searches
- [ ] **Distributed indexing**: Scale to very large codebases

## License

MIT