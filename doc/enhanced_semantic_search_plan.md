# Enhanced Semantic Search Plan

## Overview

This document outlines a comprehensive plan to enhance the semantic search capabilities of the RAGex MCP server. The current implementation only indexes symbols (functions, classes, methods) which misses critical context like imports, module-level constants, environment variables, and documentation.

## Current Limitations

1. **Missing Module-Level Code**
   - Import statements are not indexed
   - Module-level constants (e.g., `OPENSEARCH_URL = os.environ.get(...)`)
   - Global configurations and environment variable reads
   - Module initialization code

2. **Lost Context**
   - Comments explaining implementation rationale
   - Docstrings are not separately searchable
   - Configuration patterns are invisible
   - File relationships through imports

3. **Incomplete Semantic Understanding**
   - Can't search for "files using requests library"
   - Can't find "environment variable configuration"
   - Missing connection between symbols and their dependencies

## Implementation Phases

### Phase 1: Expand Symbol Extraction (High Priority)

#### 1.1 Enhance Tree-sitter Symbol Extraction
- **Import Extraction**
  - Extract all import statements as `import` type symbols
  - Capture both `import X` and `from X import Y` patterns
  - Store imported module names and specific imports
  
- **Module-Level Constants**
  - Extract top-level variable assignments as `constant` type
  - Special handling for environment variable patterns
  - Include type annotations when present

- **Module Documentation**
  - Extract module docstrings as `module_doc` type
  - Parse file-level comments at the beginning of files
  - Capture copyright and license information

#### 1.2 Configuration Pattern Detection
- **Environment Variables**
  - Detect patterns: `os.environ.get()`, `os.getenv()`, `environ[]`
  - Extract the variable name and default value
  - Mark as `config_env` type for special handling

- **Configuration Files**
  - Identify config loading patterns
  - Extract configuration class definitions
  - Link config usage to definitions

#### 1.3 Enhanced Documentation Extraction
- **Docstring Separation**
  - Index docstrings as separate searchable entities
  - Link docstrings to their parent symbol
  - Support different docstring formats (Google, NumPy, Sphinx)

- **Comment Association**
  - Extract inline comments with their associated code
  - Capture TODO/FIXME/NOTE comments specially
  - Index block comments before functions/classes

### Phase 2: Improve Embedding Strategy

#### 2.1 Context-Aware Embeddings
- **Function Embeddings**
  ```
  Embed: function_name + signature + docstring + first_line_of_body
  ```

- **Import Embeddings**
  ```
  Embed: import_statement + surrounding_imports + module_docstring_excerpt
  ```

- **Configuration Embeddings**
  ```
  Embed: variable_name + value_pattern + surrounding_config + comments
  ```

#### 2.2 Hierarchical Context
- Maintain parent-child relationships (function → class → module)
- Include file path context in embeddings
- Weight symbols by their scope and visibility

### Phase 3: Enhanced Search Capabilities

#### 3.1 Multi-Modal Search
- **Symbol Search**: Current Tree-sitter based approach
- **Content Search**: Full-text search within function bodies
- **Import Search**: Specialized search for dependencies
- **Config Search**: Find configuration patterns

#### 3.2 Intelligent Query Routing
```python
Query: "files using AWS"
→ Routes to: Import search for "boto3", "aws"

Query: "read environment variables"  
→ Routes to: Config search for "environ", "getenv"

Query: "authentication logic"
→ Routes to: Symbol + content search for "auth", "login", "token"
```

#### 3.3 Result Ranking
- Exact symbol matches rank highest
- Consider symbol type relevance
- Boost frequently imported modules
- Factor in documentation quality

### Phase 4: Advanced Features

#### 4.1 Incremental Indexing
- Track file modification times
- Update only changed files
- Maintain index consistency
- Support real-time updates

#### 4.2 Cross-File Intelligence
- Track import dependencies
- Build symbol usage graphs
- Enable "find all usages" functionality
- Support refactoring assistance

#### 4.3 Rich Metadata
- Git information (branch, last commit, author)
- Code quality metrics (complexity, test coverage)
- File statistics (size, language, framework)
- Maintenance status (last updated, frequency of changes)

## Implementation Priority

1. **Immediate** (Enables core functionality)
   - Extract imports and module-level constants
   - Update embedding strategy for new symbol types
   - Modify search to handle configuration queries

2. **Short-term** (Significant value add)
   - Separate docstring indexing
   - Enhanced query routing
   - Configuration pattern detection

3. **Long-term** (Advanced features)
   - Incremental indexing
   - Cross-file intelligence
   - Rich metadata integration

## Example: Enhanced Index Entry

Current index entry:
```json
{
  "type": "function",
  "name": "scan_departments",
  "file": "monitor.py",
  "line": 160,
  "code": "def scan_departments():..."
}
```

Enhanced index entry:
```json
{
  "type": "function",
  "name": "scan_departments",
  "file": "monitor.py",
  "line": 160,
  "signature": "scan_departments() -> List[str]",
  "docstring": "Scan for department directories and ensure indexes exist",
  "imports_used": ["os", "Environment"],
  "config_accessed": ["BASE_DIR", "excluded_directories"],
  "parent": null,
  "complexity": 12,
  "last_modified": "2024-01-15T10:30:00Z"
}
```

## Success Metrics

1. **Search Coverage**
   - Can find imports: "files using pandas"
   - Can find config: "environment variable settings"
   - Can find patterns: "error handling code"

2. **Search Quality**
   - Relevant results in top 5
   - Reduced false positives
   - Better context in results

3. **Performance**
   - Index build time < 10s for 1000 files
   - Search latency < 100ms
   - Incremental updates < 1s per file

## Migration Strategy

1. Maintain backward compatibility with existing indexes
2. Add version field to index metadata
3. Provide upgrade command for existing indexes
4. Support mixed-mode operation during transition

This enhancement plan will transform the semantic search from a symbol-only tool to a comprehensive code intelligence system that understands the full context of a codebase.