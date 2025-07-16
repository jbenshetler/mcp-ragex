# CodeRAG MCP Tests

This directory contains tests for the CodeRAG MCP server.

## Test Files

### test_enhanced_symbol_extraction.py
Tests the enhanced Tree-sitter symbol extraction that captures:
- Import statements (import X, from X import Y)
- Module-level constants
- Environment variable access patterns
- Functions, classes, and methods

**Run with:**
```bash
uv run python tests/test_enhanced_symbol_extraction.py
```

**Test data:** Uses `tests/data/test_enhanced_extraction.py` as sample input

### test_tree_sitter_query.py
Utility for debugging Tree-sitter AST structure and understanding how to write queries.
Prints the full AST tree for Python code snippets.

**Run with:**
```bash
uv run python tests/test_tree_sitter_query.py
```

**Use case:** When adding new symbol extraction patterns, use this to understand the AST structure

### test_comment_extraction.py
Tests the separation of comment/docstring extraction for semantic vs symbol search.
Shows how comments and docstrings are included only in semantic search.

**Run with:**
```bash
uv run python tests/test_comment_extraction.py
```

**Test data:** Uses `tests/data/test_comments.py` which contains various comment types (TODO, FIXME, NOTE, etc.)

### test_server.py
Main test suite for the MCP server functionality.

**Run with:**
```bash
uv run python tests/test_server.py
# or
uv run pytest tests/
```

## Adding New Tests

1. Create test data files in `tests/data/`
2. Add test scripts in `tests/`
3. Update this README with test descriptions

## Environment Variable Testing

When testing environment variable extraction, the test file includes examples of:
- `os.environ.get("VAR", "default")`
- `os.getenv("VAR", "default")`
- `os.environ["VAR"]`

All three patterns should be detected by the enhanced symbol extraction.