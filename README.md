# CodeRAG MCP Server - POC

A secure, efficient MCP (Model Context Protocol) server for code search using ripgrep.

## Features

- **Fast code search** using ripgrep with regex support
- **Security-first design** with input validation and path restrictions
- **File type filtering** supporting 30+ programming languages
- **File exclusion patterns** using gitignore syntax (.mcpignore support)
- **Tree-sitter integration** for symbol context (functions, classes, methods)
- **Configurable limits** to prevent resource exhaustion
- **JSON-RPC interface** following MCP standards

## Quick Start

### Prerequisites

1. Install ripgrep:
   ```bash
   # macOS
   brew install ripgrep
   
   # Ubuntu/Debian
   sudo apt-get install ripgrep
   
   # Windows
   choco install ripgrep
   ```

2. Install Python dependencies:
   ```bash
   pip install -e .
   # or for development
   pip install -e ".[dev]"
   ```

### Running the Server

```bash
python src/server.py
```

### Testing

```bash
# Run test suite
python tests/test_server.py

# Run with pytest (if installed)
pytest tests/
```

## Integration

### Claude Code (CLI)

#### Option 1: Using CLI Command (Recommended)

Add the MCP server using the Claude Code CLI:

```bash
claude mcp add coderag /home/jeff/clients/coderagmcp/mcp_coderag.sh --scope project
```

Expected output:
```
Added stdio MCP server coderag with command: /home/jeff/clients/coderagmcp/mcp_coderag.sh  to project config
```

#### Option 2: Using .mcp.json

Create a `.mcp.json` file in your project root:

```json
{
  "mcpServers": {
    "coderag": {
      "command": "/path/to/coderagmcp/mcp_coderag.sh"
    }
  }
}
```

#### Option 3: Direct Python Command

If you prefer not to use the wrapper script:

```bash
# From within the coderagmcp directory
claude mcp add coderag uv run python src/server.py --scope project
```

### Claude Desktop (App)

Add to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "coderag": {
      "command": "python",
      "args": ["/path/to/coderagmcp/src/server.py"]
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

### Basic Code Search
```json
{
  "tool": "search_code",
  "arguments": {
    "pattern": "async def",
    "file_types": ["py"],
    "limit": 20
  }
}
```

### Case-Insensitive Search
```json
{
  "tool": "search_code",
  "arguments": {
    "pattern": "TODO|FIXME",
    "case_sensitive": false
  }
}
```

### Raw Output Format
```json
{
  "tool": "search_code",
  "arguments": {
    "pattern": "submit_file",
    "format": "raw"
  }
}
```
Returns simple `file:line` format for programmatic use.

### Search Specific Paths
```json
{
  "tool": "search_code",
  "arguments": {
    "pattern": "test_",
    "paths": ["tests", "src/tests"],
    "file_types": ["py"]
  }
}
```

## Security Features

1. **Pattern validation**: Regex patterns are validated and length-limited
2. **Path restriction**: Searches are confined to project directory
3. **Resource limits**: Maximum results and timeout protection
4. **Input sanitization**: All inputs are validated before execution
5. **No shell injection**: Direct subprocess execution without shell

## Architecture

```
┌─────────────────┐     ┌──────────────┐     ┌─────────────┐
│  Claude/Client  │────▶│  MCP Server  │────▶│   ripgrep   │
└─────────────────┘     └──────────────┘     └─────────────┘
                               │
                               ▼
                        ┌──────────────┐
                        │  Validation  │
                        │   & Security │
                        └──────────────┘
```

## Supported File Types

`py`, `js`, `ts`, `java`, `cpp`, `c`, `go`, `rust`, `rb`, `php`, `cs`, `swift`, `kotlin`, `scala`, `r`, `lua`, `sh`, `yaml`, `json`, `xml`, `html`, `css`, `sql`, `md`, `txt`

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

- Searches timeout after 30 seconds
- Results are limited to 200 matches maximum
- Large files have column preview limited to 500 characters
- JSON parsing is streamed for efficiency

## Future Enhancements

- [ ] Add caching for repeated searches
- [ ] Implement search history
- [ ] Add semantic search capabilities
- [ ] Support for incremental indexing
- [ ] Advanced pattern builders for common searches

## License

MIT