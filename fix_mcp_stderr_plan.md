# Fix MCP Server stderr/stdout Issue

## Problem
1. MCP server is writing JSON responses to stderr instead of stdout
2. Various modules write diagnostic messages to stderr
3. MCP protocol requires clean JSON on stdout only

## Root Cause Analysis

### Files that write to stderr:
- `src/mcp_server.py` - Main MCP server
- `src/cli/search.py` - Search functionality (prints diagnostic messages)
- `ragex_search.py` - Legacy search module
- `src/utils/logging_setup.py` - Logging configuration
- Others that may be called during search

### Likely culprit
The MCP SDK (`mcp.server.stdio`) might be misconfigured or the server is using the wrong stream.

## Fix Plan

### 1. Check MCP server stdio configuration
- Verify `mcp.server.stdio.stdio_server()` usage
- Ensure write_stream goes to stdout

### 2. Capture all stderr during search
- Modify `_handle_search()` to capture stderr along with stdout
- Include captured stderr in error responses only

### 3. Configure logging properly
- Ensure all loggers write to stderr (not stdout)
- Set appropriate log levels for MCP mode

### 4. Fix search.py diagnostic messages
- The SearchClient prints messages like "# No semantic index found" to stderr
- These should be captured, not printed directly in MCP mode

## Implementation Steps

1. **Immediate fix**: Check if MCP server is writing to correct stream
2. **Comprehensive fix**: Ensure all stderr is captured during tool execution
3. **Test**: Verify JSON goes to stdout, diagnostics to stderr or captured

## Testing
```bash
# Should output JSON to stdout only
echo '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"0.1.0","capabilities":{},"clientInfo":{"name":"test","version":"1.0"}}}' | ragex-mcp

# Should handle search without polluting stdout
echo '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"search_code","arguments":{"query":"test"}}}' | ragex-mcp
```