# Plan: Implement Optimal Balance for MCP Search Results

## Problem Statement

The MCP search tools are returning responses that exceed the 25K token limit, causing failures. Root cause analysis shows:

1. **JSON format overhead**: Current `json.dumps(result, indent=2)` adds 30-50% token bloat
2. **Full code snippets**: Each match includes complete code content vs CLI's file:line references
3. **Rich metadata**: Extensive metadata per match multiplies response size
4. **No token limiting**: Responses can grow unbounded with large result sets

CLI search returns ~2K tokens for same query that produces 50K+ tokens via MCP.

## Architecture Overview

### Three-Tier Output System
1. **`minimal`**: CLI-compatible format (~2K tokens)
2. **`compact`**: Smart compact with key context (~5K tokens) 
3. **`rich`**: Full context when needed (~15K tokens, capped)

### Parameter Design
```python
detail_level: Literal["minimal", "compact", "rich"] = "compact"
max_tokens: int = 20000  # Hard limit to prevent overflow
```

## Format Specifications

### Minimal Format (CLI Compatible)
```
/path/file.py:123:[function] (0.85) def vector_search
/path/file.py:456:[class] (0.82) class CodeVectorStore
```
- **Token estimate**: ~2K for 50 results
- **Use case**: Quick scanning, when you'll Read files anyway

### Compact Format (Smart Default)
```
/path/file.py:123:[function] (0.85) def vector_search(query: str, limit: int = 50)
  → Purpose: Main semantic search interface
  → Returns: Dict with matches and metadata

/path/file.py:456:[class] (0.82) class CodeVectorStore
  → Purpose: Manages code embeddings in ChromaDB
  → Key methods: add_symbols, search, delete_by_file
```
- **Token estimate**: ~5K for 50 results
- **Use case**: Balanced context without file reads for most decisions

### Rich Format (Full Context)
```
/path/file.py:123:[function] (0.85) def vector_search(query: str, limit: int = 50)
  → Purpose: Main semantic search interface
  → Returns: Dict with matches and metadata
  
  def vector_search(query: str, limit: int = 50):
      """Execute semantic search using vector similarity"""
      embedding = self.embed_text(query)
      return self.search(embedding, limit)
```
- **Token estimate**: ~15K for 50 results (capped at max_tokens)
- **Use case**: When full context needed, complex analysis

## Implementation Plan

### Phase 1: Format System Infrastructure

#### 1. **Create Format Renderer Module** (`src/ragex_core/result_formatters.py`)
```python
class ResultFormatter:
    def format_results(self, results: Dict, detail_level: str, max_tokens: int) -> str
    def estimate_tokens(self, text: str) -> int
    def truncate_if_needed(self, text: str, max_tokens: int) -> str

class MinimalFormatter(ResultFormatter):
    def format_results(self, results: Dict, detail_level: str, max_tokens: int) -> str:
        # CLI-compatible format: file:line:[type] (score) name
        
class CompactFormatter(ResultFormatter):
    def format_results(self, results: Dict, detail_level: str, max_tokens: int) -> str:
        # Add signatures + brief purpose + key info
        
class RichFormatter(ResultFormatter):
    def format_results(self, results: Dict, detail_level: str, max_tokens: int) -> str:
        # Include code context + docstrings + full metadata
```

#### 2. **Token Estimation Utility**
```python
def estimate_tokens(text: str) -> int:
    """Rough token estimation: chars/4 + overhead"""
    return len(text) // 4 + 50  # Conservative estimate

def truncate_to_token_limit(text: str, max_tokens: int) -> tuple[str, bool]:
    """Truncate text to stay under token limit"""
    # Return (truncated_text, was_truncated)
```

### Phase 2: MCP Integration

#### 3. **Update Tool Schemas**

Add parameters to `search_code` tool in `src/server.py`:
```python
"detail_level": {
    "type": "string",
    "enum": ["minimal", "compact", "rich"],
    "description": "Output detail level: 'minimal' (~2K tokens, CLI-like), 'compact' (~5K tokens, balanced), 'rich' (~15K tokens, full context)",
    "default": "compact"
},
"max_tokens": {
    "type": "integer",
    "description": "Maximum response tokens (1000-25000, default: 20000)",
    "minimum": 1000,
    "maximum": 25000,
    "default": 20000
}
```

Add same parameters to `search_code_simple`.

#### 4. **Modify `handle_intelligent_search()`** 
```python
async def handle_intelligent_search(
    query: str,
    paths: List[str],
    mode: str = "auto",
    # ... existing parameters ...
    detail_level: str = "compact",
    max_tokens: int = 20000,
    **kwargs
) -> List[types.TextContent]:
    # ... existing search logic ...
    
    # NEW: Format results based on detail_level
    formatter = get_formatter(detail_level)
    formatted_text = formatter.format_results(result, detail_level, max_tokens)
    
    # Return formatted text instead of json.dumps
    return [types.TextContent(type="text", text=formatted_text)]

def get_formatter(detail_level: str) -> ResultFormatter:
    formatters = {
        "minimal": MinimalFormatter(),
        "compact": CompactFormatter(),
        "rich": RichFormatter()
    }
    return formatters[detail_level]
```

### Phase 3: Smart Features

#### 5. **Context Extraction Utilities**
```python
def extract_function_signature(code: str, symbol_name: str) -> str:
    """Extract clean function signature from code snippet"""

def summarize_docstring(docstring: str, max_chars: int = 100) -> str:
    """Summarize docstring to key points"""

def extract_class_summary(code: str, class_name: str) -> str:
    """Extract class purpose and key methods"""
```

#### 6. **Adaptive Result Limiting**
```python
def adaptive_limit(results: List, detail_level: str, max_tokens: int) -> List:
    """Reduce result count if approaching token limit"""
    estimated_tokens_per_result = get_tokens_per_result(detail_level)
    max_results = max_tokens // estimated_tokens_per_result
    return results[:max_results]
```

### Phase 4: Testing & Validation

#### 7. **Test Cases**
- Test each format with semantic and regex search
- Verify token counts stay under limits
- Test with various query types (classes, functions, imports)
- Validate Claude Code can effectively use compact format

#### 8. **Performance Benchmarking**
- Measure formatting speed overhead
- Test memory usage with large result sets
- Compare search effectiveness across formats

## File Changes Required

### New Files
1. **`src/ragex_core/result_formatters.py`** - Format implementation classes
2. **`tests/test_result_formatters.py`** - Comprehensive format testing

### Modified Files
1. **`src/server.py`** - Tool schemas and handler logic updates
2. **Update tool parameter handling in `handle_intelligent_search()`**

### Configuration
- Add format preferences to embedding config if needed
- Consider environment variable overrides for testing

## Migration Strategy

### Backward Compatibility
- **Default**: Use `compact` format (maintains good usability)
- **Existing behavior**: Available via `detail_level=rich` 
- **CLI parity**: Available via `detail_level=minimal`

### Rollout Plan
1. **Phase 1**: Implement formatters, test with semantic search
2. **Phase 2**: Add to regex search, comprehensive testing
3. **Phase 3**: Make `compact` the default
4. **Phase 4**: Optimize based on real usage patterns

### Success Metrics
- **Token reduction**: 60-90% reduction in response size
- **Usability**: Claude Code can make effective decisions without additional file reads
- **Performance**: <100ms formatting overhead for typical result sets
- **Reliability**: Zero token limit exceeded errors

## Expected Impact

- **Immediate**: Eliminates token limit exceeded errors
- **Performance**: Faster responses, reduced bandwidth
- **Usability**: Better balance of context vs efficiency
- **Scalability**: System works with large codebases and complex queries

This plan addresses the core issue while maintaining the effectiveness of code search for AI assistants.