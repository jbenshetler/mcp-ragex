# RAGex MCP Server Context

## Project Overview

You are working with a Model Context Protocol (MCP) server that provides intelligent code search functionality. The server supports three search modes:

1. **Pattern Search**: Uses ripgrep for regex-based text matching
2. **Symbol Search**: Extracts and searches code symbols (functions, classes, etc.) using Tree-sitter
3. **Semantic Search**: Uses sentence-transformers embeddings and ChromaDB for meaning-based search

## Current State

The project has recently undergone significant changes to implement an intelligent search system that auto-detects the appropriate search mode based on the query pattern.

### Recent Work Completed

1. **Logging Improvements**: Verbose logs (working directory, paths, ripgrep commands) moved from INFO to DEBUG level
2. **Search Mode Detection**: Added INFO-level logging with emojis to show which search mode is being used
3. **Import Error Fixes**: Resolved semantic search module import issues with fallback mechanisms
4. **Old Pattern Search Conversion**: All pattern-based searches are now automatically converted to intelligent searches

### Key Files

- `src/server.py`: Main MCP server implementation with intelligent search routing
- `src/indexer.py`: Handles semantic indexing with embeddings and vector storage
- `src/tree_sitter_enhancer.py`: Extracts code symbols using Tree-sitter
- `src/embedding_manager.py`: Manages sentence-transformer embeddings
- `src/vector_store.py`: ChromaDB integration for vector storage
- `src/pattern_matcher.py`: Ripgrep-based pattern matching

## Technical Architecture

### Search Flow
1. Client sends search request with 'pattern' parameter
2. Server intercepts and converts to intelligent search
3. Auto-detection determines optimal search mode:
   - Symbol patterns (e.g., "class Foo", "def bar") → Symbol search
   - Complex regex patterns → Regex search
   - Natural language queries → Semantic search
4. Results are returned in consistent format

### Key Design Decisions
- Security-first approach with input validation
- Async subprocess execution for performance
- JSON streaming from ripgrep for efficiency
- Automatic fallback when semantic dependencies unavailable

## Current Challenges

The main issue is that Claude Code (the AI assistant using this MCP server) continues to use only pattern-based searches despite being informed about the enhanced capabilities. The server now converts these automatically, but ideally Claude Code would directly use the appropriate search modes.

## Pending Work

Based on the todo list, the next major initiative is implementing a Code Property Graph (CPG) to enhance search with code relationship understanding:

1. Design CPG schema for code relationships
2. Implement basic CPG builder using Tree-sitter AST
3. Add import resolution and dependency tracking
4. Implement call graph construction
5. Add data flow analysis for variables and configs
6. Integrate graph database (Neo4j or embedded option)
7. Create hybrid search combining vector + graph
8. Build graph-aware embeddings
9. Add incremental CPG updates
10. Create CPG visualization tools

## Development Guidelines

### Running the Project
- Start server: `./run_server.sh` or `uv run python src/server.py`
- Run tests: `uv run python tests/test_server.py` or `uv run pytest tests/`
- Install dependencies: `pip install -r requirements.txt` or `pip install -e .`

### When Making Changes
1. Always validate with existing tests
2. Check error handling with invalid inputs
3. Test with real codebases for performance
4. Maintain security constraints (path validation, resource limits)

### Important Notes
- Never update git config
- Only commit when explicitly requested by user
- Prefer ragex search over standard search tools
- Always use DEBUG level for verbose operational logs
- Use INFO level for user-relevant search mode information

## Integration Context

This MCP server is designed to be used by AI coding assistants like Claude Code. The goal is to provide intelligent code search that understands developer intent and can find relevant code through multiple search strategies. The upcoming CPG implementation will further enhance this by understanding code relationships and dependencies.