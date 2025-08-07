# RAGex MCP Server

A secure, intelligent **MCP (Model Context Protocol) server** for **Claude** and AI assistants, providing semantic code search using **RAG**, **tree-sitter**, and **ripgrep**. Search code using natural language or regex patterns.

## What is RAGex?

RAGex is an **MCP server** that enhances **Claude Code** and other AI coding assistants with advanced code search capabilities. It combines:
- **RAG (Retrieval-Augmented Generation)** for semantic code search
- **Tree-sitter** for language-aware symbol search  
- **Ripgrep** for blazing-fast regex search

## Why RAGex?

Unlike simple grep-based tools, RAGex understands code semantically:

| Feature | grep/ripgrep | RAGex |
|---------|-------------|---------|
| Find "auth functions" | ❌ | ✅ Semantic search |
| Find `validateUser()` | ✅ | ✅ Symbol-aware search |
| Cross-language patterns | ❌ | ✅ Coming soon |
| Natural language queries | ❌ | ✅ "functions that handle errors" |

## Features

### 🔍 **Intelligent Search Modes**
- **Auto-detection**: Automatically chooses the best search mode based on query patterns
- **Regex mode**: Fast pattern matching with ripgrep for exact patterns
- **Semantic mode**: Natural language search using sentence-transformers embeddings

### 🚀 **Performance & Security**
- **Fast code search** using ripgrep with regex support
- **Security-first design** with input validation and path restrictions
- **File type filtering** supporting 30+ programming languages
- **Enhanced file exclusions** with multi-level .mcpignore support and comprehensive defaults
- **Configurable limits** to prevent resource exhaustion
- **JSON-RPC interface** following MCP standards

### 🧠 **AI-Powered Features**
- **Semantic code search** using sentence-transformers embeddings
- **Query enhancement** with abbreviation expansion and context addition
- **Intelligent fallback** when primary search mode fails
- **Teaching system** that guides Claude Code to optimal search usage

## Quick Start

### 🐳 Docker Installation (Recommended)

The fastest and most reliable way to get started is with Docker:

```bash
# Option 1: Use the installation script (easiest)
curl -sSL https://raw.githubusercontent.com/YOUR_USERNAME/mcp-ragex/main/install.sh | bash

# Option 2: Manual setup
git clone https://github.com/YOUR_USERNAME/mcp-ragex.git
cd mcp-ragex
docker build -t ragex/mcp-server .
./install.sh  # This installs the 'ragex' command to ~/.local/bin
```

**What gets installed:**
- Docker image: `ragex/mcp-server:latest` (6.2GB)
- CLI wrapper: `~/.local/bin/ragex` (handles Docker communication)
- User volume: `ragex_user_${UID}` (stores your project indexes)

**Post-installation:**
```bash
# Add to PATH if needed
export PATH="$PATH:$HOME/.local/bin"

# Verify installation
ragex info
which ragex  # Should show: /home/USERNAME/.local/bin/ragex
```

### 🔧 Manual Installation

For development or custom setups:

#### Prerequisites
1. **Install Claude Code**
[![Install with Claude Code](https://img.shields.io/badge/Install-Claude_Code-blue)](https://claude.ai)

2. **Install ripgrep:**
    ```bash
    # macOS
    brew install ripgrep

    # Ubuntu/Debian
    sudo apt-get install ripgrep

    # Windows
    choco install ripgrep
    ```
3. **Install Python dependencies:**
    ```bash
    # Using uv (recommended)
    uv pip install -r requirements.txt

    # Or using pip
    pip install -r requirements.txt
    ```

## Usage with Docker

### 🚀 Quick Setup

After installation, each project gets its own isolated data:

```bash
# Navigate to your first project
cd /path/to/project1
ragex index .                    # Creates project-specific index
ragex info                       # Shows project details

# Navigate to your second project  
cd /path/to/project2
ragex index . --preset balanced  # Different embedding model
ragex info                       # Shows different project ID

# Register with Claude Code (one-time setup)
# The 'ragex' command was installed to ~/.local/bin by install.sh
claude mcp add ragex $(which ragex) --scope project

# List all your projects
ragex ls
```

### 🔍 Available Commands

```bash
# Project Management
ragex info                       # Show current project info
ragex ls                         # List all user projects
ragex ls -l                      # List with details (model, indexed status)
ragex ls -a                      # List all projects (including admin)
ragex ls "api*"                  # List projects matching pattern
ragex rm PROJECT_ID              # Remove specific project

# Indexing
ragex index .                    # Index current project (fast model)
ragex index . --preset balanced  # Index with balanced model
ragex index . --preset accurate  # Index with accurate model

# Searching
ragex search "auth functions"    # Search current project
ragex serve                      # Start MCP server (for Claude)

# Development
ragex bash                       # Get shell for debugging
```

#### Project Listing (`ragex ls`)

The `ls` command shows your indexed projects:

**Flags:**
- `-l, --long`: Show detailed information including embedding model and index status
- `-a, --all`: Show all projects including admin projects (normally hidden)
- Pattern argument: Filter projects by name (supports wildcards like `api*`)

**Admin Projects:**
Projects with the name `.ragex_admin` are special system projects created when ragex runs without a mounted workspace (e.g., during certain admin operations). These projects:
- Are hidden by default (use `-a` to see them)
- Have minimal disk usage (no actual code is indexed)
- Can be safely ignored or removed with `ragex rm`

### 🏗️ Project Isolation

Each project gets its own isolated data:

```bash
# Example: Two different projects
cd ~/work/api-server
ragex index . --preset accurate  # Large model for work project
# → Creates: ragex_1000_a1b2c3d4ef56789 

cd ~/personal/blog  
ragex index . --preset fast      # Fast model for personal project  
# → Creates: ragex_1000_f9e8d7c6b5a43210

ragex ls -l
# PROJECT NAME          PROJECT ID                      MODEL       INDEXED   PATH
# --------------------------------------------------------------------------------
# api-server            ragex_1000_a1b2c3d4ef56789     accurate    yes       ~/work/api-server
# blog                  ragex_1000_f9e8d7c6b5a43210     fast        yes       ~/personal/blog
```

### 🐳 Docker Compose (Development)

For active development, use Docker Compose:

```bash
# Start development environment
docker compose up -d

# Watch logs
docker compose logs -f

# Build semantic index
docker compose exec ragex python scripts/build_semantic_index.py /workspace --stats

# Stop when done
docker compose down
```

### 📦 Persistent Data

Your data is organized for multi-project use:

#### User-Level Storage
- **Volume**: `ragex_user_1000` (where 1000 is your user ID)
- **Models**: `/data/models/` (shared across all your projects)
- **Projects**: `/data/projects/` (individual project indexes)

#### Project-Level Storage
```
/data/
├── models/                    # Shared embedding models (400MB-1.3GB)
└── projects/
    ├── ragex_1000_a1b2c3d4/   # Project 1 data
    │   ├── chroma_db/         # Vector database
    │   └── project_info.json  # Project metadata
    └── ragex_1000_f9e8d7c6/   # Project 2 data
        ├── chroma_db/
        └── project_info.json
```

#### Volume Management
```bash
# List your projects
ragex list-projects

# Clean up specific project
ragex clean-project ragex_1000_a1b2c3d4

# Check volume usage
docker volume ls | grep ragex_user_$(id -u)

# Remove all your data (nuclear option)
docker volume rm ragex_user_$(id -u)
```

## Manual Installation

For development or when Docker isn't available:

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
1. Check `/tmp/mcp_ragex.log` for "Semantic search ENABLED" message
2. Test with: `search_code(query="your search terms", mode="semantic")`

#### Alternative Registration (Legacy)
```bash
# Uses current project's Python environment (may have missing dependencies)
claude mcp add ragex /path/to/mcp-ragex/mcp_ragex_pwd.sh --scope project
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
./mcp_ragex.sh
```

### Testing

```bash
# Run test suite
uv run tests/test_server.py

# Run with pytest (if installed)
pytest tests/
```

## Docker Architecture

### 🔌 MCP Communication Through Docker

The MCP protocol uses stdin/stdout for communication. The `ragex` wrapper script handles this transparently:

```bash
# When Claude Code runs:
claude mcp add ragex /home/user/.local/bin/ragex

# It communicates like this:
Claude Code ←→ ragex script ←→ Docker container ←→ MCP Server
           stdin/stdout    stdin/stdout      stdin/stdout
```

**Key points:**
- The `ragex` script acts as a bridge between Claude Code and the Docker container
- For MCP server mode, Docker runs with `-i` (interactive) but NOT `-t` (no TTY)
- TTY would break JSON-RPC communication by adding terminal control codes
- The wrapper preserves stdin/stdout pipes for proper MCP protocol communication

### 🏗️ Container Structure

```
/app/                     # Application code (read-only)
├── src/                  # Source code
├── scripts/              # Utility scripts
├── requirements.txt      # Python dependencies
└── entrypoint.sh        # Container entrypoint

/data/                    # User-specific persistent data (volume)
├── models/              # Shared embedding models (400MB-1.3GB)
└── projects/            # Project-specific data
    ├── ragex_1000_abc123/  # Project 1
    │   ├── chroma_db/      # ChromaDB vector database  
    │   └── project_info.json # Project metadata
    └── ragex_1000_def456/  # Project 2
        ├── chroma_db/
        └── project_info.json

/workspace/              # Your code (volume, read-only)
└── [current project]    # Code to be indexed
```

### 🔧 Environment Variables

Docker containers support these environment variables:

```bash
# Project identification (automatically set by wrapper)
WORKSPACE_PATH=/path/to/your/project    # Workspace being indexed
PROJECT_NAME=ragex_1000_abc123          # Generated project ID

# Data directories (automatically configured)
RAGEX_PROJECT_DATA_DIR=/data/projects/ragex_1000_abc123  # Project data
RAGEX_CHROMA_PERSIST_DIR=/data/projects/ragex_1000_abc123/chroma_db  # ChromaDB
TRANSFORMERS_CACHE=/data/models         # Shared model cache
SENTENCE_TRANSFORMERS_HOME=/data/models # Sentence transformers cache

# User configuration
RAGEX_EMBEDDING_MODEL=fast              # Model preset (fast/balanced/accurate)
RAGEX_CHROMA_COLLECTION=code_embeddings # Collection name

# System configuration
RAGEX_LOG_LEVEL=INFO                    # Log level (DEBUG, INFO, WARN, ERROR) - default: INFO
LOG_LEVEL=INFO                          # Fallback log level (RAGEX_LOG_LEVEL takes precedence)
DOCKER_CONTAINER=true                   # Indicates running in container
```

### 🐳 Production Deployment

Use the production Docker Compose for deployment:

```bash
# Production setup with resource limits
docker compose -f docker-compose.prod.yml up -d

# Check status
docker compose -f docker-compose.prod.yml ps

# View logs
docker compose -f docker-compose.prod.yml logs ragex
```

## Integration

### 🖥️ Claude Code (CLI)

#### Docker Integration (Recommended)

Register the Docker-based MCP server:

```bash
cd /path/to/your/project
claude mcp add ragex /path/to/mcp-ragex/ragex --scope project
```

The `ragex` script automatically handles Docker execution and volume mounting.

#### Manual Integration

For manual/development setups:

```bash
# Option 1: Using wrapper script
claude mcp add ragex /path/to/mcp-ragex/mcp_ragex.sh --scope project

# Option 2: Direct Python command
claude mcp add ragex uv run /path/to/mcp-ragex/src/server.py --scope project
```

### 🖱️ Claude Desktop (App)

Add to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "ragex": {
      "command": "/path/to/mcp-ragex/ragex",
      "env": {
        "RAGEX_DATA_DIR": "/path/to/persistent/data"
      }
    }
  }
}
```

### ✅ Verifying MCP Connection

After configuration, verify the MCP server is connected:

```bash
# In Claude Code, use the /mcp command
/mcp
```

This will show the status of all configured MCP servers. You should see `ragex` in the list.

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
search_code("AuthenticationService")

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
search_code("UserService")

# Find specific functions
search_code("validateInput")

# Find methods
search_code("submitToQueue")
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

## Logging and Debugging

### Setting Log Levels

RAGex uses `RAGEX_LOG_LEVEL` to control logging verbosity. The default is `INFO`.

```bash
# Set log level before starting daemon
export RAGEX_LOG_LEVEL=DEBUG
ragex start

# Or set for a single command
RAGEX_LOG_LEVEL=DEBUG ragex start
```

**Available Log Levels:**
- `DEBUG`: Detailed debugging info (file processing, embeddings, scores)
- `INFO`: General operation info (search queries, index progress) - **default**
- `WARN`: Warnings and potential issues only
- `ERROR`: Error messages only

**Important:** The log level is set when the daemon starts and cannot be changed without restarting:

```bash
# To change log level after daemon is running:
ragex stop
RAGEX_LOG_LEVEL=DEBUG ragex start
```

### Viewing Logs

```bash
# View daemon logs for current project
ragex log

# Follow logs in real-time
ragex log -f

# View last 50 lines
ragex log --tail 50

# View logs for specific project
ragex log project-name

# View MCP server logs (when using with Claude)
tail -f /tmp/ragex-mcp.log
```

### What Gets Logged

**At INFO level:**
- Project detection and initialization
- Search mode detection (semantic/regex)
- Search query execution
- Number of results found
- Index progress and file counts

**At DEBUG level adds:**
- Individual file processing
- Embedding generation details
- ChromaDB query internals
- Similarity scores for each result
- Pattern matcher decisions

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

The server provides an enhanced ignore system with comprehensive defaults and multi-level support:

### Default Exclusions
MCP-RageX includes comprehensive default exclusions for:
- **Python**: `.venv/**`, `__pycache__/**`, `*.pyc`, `.eggs/**`, `.tox/**`, etc.
- **JavaScript/TypeScript**: `node_modules/**`, `*.tsbuildinfo`, `.npm/**`, etc.
- **Build artifacts**: `build/**`, `dist/**`, `*.o`, `*.so`, `*.exe`, etc.
- **IDEs**: `.vscode/**`, `.idea/**`, `*.swp`, etc.
- **OS files**: `.DS_Store`, `Thumbs.db`, `._*`, etc.
- **Media/Archives**: `*.jpg`, `*.mp4`, `*.zip`, etc.

### Initialize .mcpignore
When starting a new project, MCP-RageX can create a `.mcpignore` file with all defaults visible:

```bash
# Create comprehensive .mcpignore with categorized patterns
ragex init

# Create minimal .mcpignore (essential patterns only)
ragex init --minimal

# Add custom patterns
ragex init --add "*.custom" --add "data/**"

# Force overwrite existing file
ragex init --force
```

**Note**: If no `.mcpignore` exists, the system uses built-in defaults and shows a warning suggesting to run `ragex init`. Set `RAGEX_IGNOREFILE_WARNING=false` to disable this warning.

### Custom Exclusions (.mcpignore)
Create or edit `.mcpignore` files using gitignore syntax:

```gitignore
# Example .mcpignore
test_output/
*.tmp
docs/**/*.generated.md
!important.log  # Negation pattern (include this file)

# Project-specific patterns
data/raw/**
models/**
*.pkl
```

### Multi-Level Support
You can create `.mcpignore` files in subdirectories for more specific control:

```
project/
├── .mcpignore          # Root patterns
├── src/
│   └── .mcpignore      # Additional patterns for src/
└── tests/
    └── .mcpignore      # Override parent rules for tests/
```

Deeper `.mcpignore` files override parent rules, allowing fine-grained control.

### Disabling Default Patterns
For minimal setups, you can disable all default patterns programmatically:

```python
# When using the Python API directly
manager = IgnoreManager("/path", use_defaults=False)
```

**Notes:**
- Uses standard gitignore syntax
- Invalid patterns are warned about but don't break the server
- Patterns are matched relative to the `.mcpignore` file location
- See `examples/.mcpignore.template` for a comprehensive example

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

#### Docker Resource Requirements
- **Memory**: 8GB RAM recommended (4GB minimum)
- **CPU**: 2+ cores recommended for indexing
- **Storage**: 
  - Base image: ~6.2GB
  - Data volume: ~1MB per 1000 symbols indexed
  - Model cache: 80MB-1.3GB depending on preset
- **GPU**: Optional, accelerates semantic search (requires nvidia-docker)

#### Memory Usage by Component
- **Base container**: ~100MB baseline
- **During indexing**: ~500MB peak
- **During semantic search**: ~300MB
- **ChromaDB**: ~50MB for typical projects
- **PyTorch models**: 80MB-1.3GB (cached in volume)

### Docker Optimization Features
- **Multi-stage builds**: Minimal runtime dependencies
- **Volume caching**: Models persist between container restarts
- **Resource limits**: Configurable memory/CPU limits in production
- **Efficient layers**: Optimized Docker layer caching
- **Non-root execution**: Security-first container design

### Production Scaling
```bash
# Resource-limited production deployment
docker compose -f docker-compose.prod.yml up -d

# Monitor resource usage
docker stats ragex_mcp_server

# Scale for multiple projects (if needed)
docker compose -f docker-compose.prod.yml up --scale ragex=3
```

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

The enhanced ignore system now provides comprehensive defaults and multi-level support:

```bash
# Initialize .mcpignore with visible defaults
ragex init

# The system will use built-in defaults if no .mcpignore exists
# and show a warning (disable with RAGEX_IGNOREFILE_WARNING=false)
```

Example `.mcpignore` for additional project-specific exclusions:

```gitignore
# Dependencies (already in defaults, shown for clarity)
node_modules/
venv/
.venv/

# Build outputs (already in defaults)
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

## Deployment & Operations

### 🚀 Production Deployment

#### Option 1: Docker Compose (Recommended)
```bash
# Clone the repository
git clone https://github.com/YOUR_USERNAME/mcp-ragex.git
cd mcp-ragex

# Deploy with resource limits
docker compose -f docker-compose.prod.yml up -d

# Verify deployment
docker compose -f docker-compose.prod.yml ps
```

#### Option 2: Kubernetes
```yaml
# Example Kubernetes deployment (k8s/deployment.yaml)
apiVersion: apps/v1
kind: Deployment
metadata:
  name: ragex-mcp-server
spec:
  replicas: 1
  selector:
    matchLabels:
      app: ragex-mcp-server
  template:
    metadata:
      labels:
        app: ragex-mcp-server
    spec:
      containers:
      - name: ragex
        image: ragex/mcp-server:latest
        resources:
          requests:
            memory: "1Gi"
            cpu: "500m"
          limits:
            memory: "4Gi"
            cpu: "2"
        volumeMounts:
        - name: ragex-data
          mountPath: /data
      volumes:
      - name: ragex-data
        persistentVolumeClaim:
          claimName: ragex-data-pvc
```

### 📊 Monitoring & Logging

#### Health Checks
```bash
# Check container health
docker compose exec ragex python -c "import src.server; print('Server OK')"

# Test MCP protocol
echo '{"jsonrpc": "2.0", "id": 1, "method": "tools/list"}' | \
  docker compose exec -T ragex python -m src.server
```

#### Log Management
```bash
# View real-time logs
docker compose logs -f ragex

# Export logs for analysis
docker compose logs ragex > ragex-logs.txt

# Container metrics
docker stats ragex_mcp_server
```

#### Volume Management
```bash
# Backup semantic index
docker run --rm -v ragex-data:/data -v $(pwd):/backup \
  alpine tar czf /backup/ragex-backup.tar.gz -C /data .

# Restore from backup
docker run --rm -v ragex-data:/data -v $(pwd):/backup \
  alpine tar xzf /backup/ragex-backup.tar.gz -C /data

# Reset data (forces model re-download)
docker volume rm ragex-data
```

## Future Enhancements

### Planned Features
- [ ] **CodeBERT integration**: Upgrade to code-specific embeddings
- [ ] **Incremental indexing**: Automatic index updates on file changes
- [ ] **Cross-language search**: Find similar patterns across languages
- [ ] **Search history**: Remember and optimize frequent queries
- [ ] **Custom embeddings**: Train project-specific models

### Docker & Infrastructure
- [ ] **Multi-architecture builds**: ARM64 support for Apple Silicon
- [ ] **Distroless images**: Even smaller container images
- [ ] **GPU acceleration**: CUDA-enabled containers for faster indexing
- [ ] **Kubernetes operators**: Automated deployment and scaling
- [ ] **Health endpoints**: HTTP health checks for orchestration

### Performance Improvements
- [ ] **Hybrid search**: Combine keyword and semantic results
- [ ] **Query optimization**: Learn from usage patterns
- [ ] **Caching strategies**: Cache frequent semantic searches
- [ ] **Distributed indexing**: Scale to very large codebases

## License

MIT