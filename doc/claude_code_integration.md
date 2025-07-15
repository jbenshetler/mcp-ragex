# Claude Code Integration Guide

This guide explains how to use the MCP code search server effectively with Claude Code to speed up code navigation and search.

## Problem Statement

Claude Code currently uses slow grep operations without context when searching for code. This MCP server provides:
- Faster search using ripgrep
- Tree-sitter symbol context (functions, classes, methods)
- Smart file exclusions (.venv, node_modules, etc.)
- Results formatted for efficient navigation

## Output Formats

### Navigation Format (Default)

Designed to help Claude Code quickly identify where to look:

```markdown
## Search Results: 'submit_file'

**Summary**: 15 matches in 3 files

### Files with matches:

- `src/api/handlers.py` (5 matches)
- `src/utils/file_submission.py` (8 matches)  
- `tests/test_submission.py` (2 matches)

### Match details:

#### src/api/handlers.py
- Line 45: `def submit_file(request):`
  Context: function 'submit_file'
- Line 89: `result = submit_file(cleaned_data)`
  Context: function 'process_request'
...
```

This format:
- Shows all files upfront for quick scanning
- Groups matches by file to reduce context switching
- Includes symbol context when available
- Presents information hierarchically

### Raw Format

For programmatic use or when you want minimal output:

```
src/api/handlers.py:45
src/api/handlers.py:89
src/utils/file_submission.py:12
src/utils/file_submission.py:67
tests/test_submission.py:23
tests/test_submission.py:45
```

Use with: `"format": "raw"`

## Best Practices for Claude Code

### 1. Initial Code Exploration

When starting work on a feature:

```json
{
  "pattern": "class.*User|function.*User|def.*user",
  "include_symbols": true,
  "limit": 30
}
```

This finds all user-related code with context.

### 2. Finding Specific Functions

```json
{
  "pattern": "def submit_file|function submit_file",
  "file_types": ["py", "js"],
  "format": "raw"
}
```

Raw format gives Claude Code a quick list of locations to check.

### 3. Understanding Code Structure

```json
{
  "pattern": "import.*submit|from.*submit",
  "include_symbols": true
}
```

Shows where and how the code is imported/used.

### 4. Excluding Test Files

When focusing on implementation:

```json
{
  "pattern": "submit_file",
  "exclude_patterns": ["tests/**", "**/*.test.js", "**/*.spec.ts"]
}
```

## Speeding Up Claude Code Workflow

### Before (Claude Code's default approach):
1. Uses grep to search
2. No context about symbols
3. Includes irrelevant files (.venv, node_modules)
4. Results are unorganized

### After (with MCP search server):
1. Ripgrep is 5-10x faster
2. Shows function/class context
3. Automatically excludes irrelevant files
4. Results are organized by file

### Example Workflow

**You**: "Find where submit_file is implemented"

**Claude Code** uses:
```json
{
  "pattern": "def submit_file|function submit_file|class.*submit_file",
  "include_symbols": true,
  "exclude_patterns": ["tests/**"]
}
```

Gets back organized results showing:
- Implementation files first
- Symbol context (is it a method? standalone function?)
- Can immediately navigate to the right file

## Tips for Queries

1. **Be specific with patterns**: Instead of searching for "user", search for "class User|def.*user"

2. **Use file types**: Narrow searches with `"file_types": ["py"]` 

3. **Start broad, then narrow**: First search without exclusions to see the full picture, then exclude tests/docs

4. **Use raw format for lists**: When you just need a list of files to process

5. **Enable symbols for context**: When understanding code structure, always use `"include_symbols": true`

## Future Enhancements

The roadmap includes:
- Semantic search using embeddings
- Caching for repeated searches
- Cross-reference detection (find all callers)
- Real-time indexing with file watching

These will make Claude Code even more efficient at navigating and understanding large codebases.