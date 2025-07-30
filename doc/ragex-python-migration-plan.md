# RAGex Python Migration Plan

## Overview

This document outlines the plan to migrate the `ragex` bash script to a Python implementation with robust argument parsing and integrated MCP server support.

## Current State

- **`ragex`**: Bash script (~426 lines) that manages Docker containers with project isolation
- **Limitations**: 
  - Weak argument parsing using bash conditionals
  - Difficult to maintain and extend
  - No integrated MCP support (requires separate server)

## Goals

1. **Replace bash script with Python** for better maintainability
2. **Add robust argument parsing** using Python's argparse
3. **Integrate MCP server mode** with `--mcp` flag
4. **Maintain 100% compatibility** with existing functionality
5. **Improve error handling and debugging**

## Architecture

### Current Flow
```
User -> ragex (bash) -> docker run/exec -> daemon container -> socket -> search
```

### New Flow (CLI mode)
```
User -> ragex (python) -> docker run/exec -> daemon container -> socket -> search
```

### New Flow (MCP mode)
```
MCP Client -> ragex --mcp (python) -> daemon container -> socket -> search --json
```

## Functionality to Preserve

### Core Commands (via daemon)
- `index [PATH]` - Build semantic index and start daemon
- `search QUERY` - Search in current project  
- `bash` - Get shell in container
- `init` - Create .mcpignore file

### Management Commands (direct docker)
- `ls` / `list-projects` - List all projects
- `rm ID` / `clean-project ID` - Remove project data
- `register` / `unregister` - Show registration instructions
- `info` - Show project information

### Daemon Control
- `stop` - Stop daemon if running
- `status` - Check daemon status
- `log [PROJECT] [-f]` - Show/follow logs with full docker logs options

### Environment Variables
- `RAGEX_DOCKER_IMAGE` - Docker image to use (default: ragex:local)
- `RAGEX_EMBEDDING_MODEL` - Model preset (fast/balanced/accurate)
- `RAGEX_PROJECT_NAME` - Override project name
- `RAGEX_DEBUG` - Enable debug output

### Key Features
1. **Project Isolation**: Each workspace gets unique daemon container
2. **User Volumes**: `ragex_user_{uid}` for persistent data
3. **Project ID Generation**: SHA256 hash of `{uid}:{absolute_path}`
4. **TTY Handling**: Interactive for bash, non-TTY for serve/MCP
5. **Socket Communication**: Via `/tmp/ragex.sock` in daemon container

## Implementation Structure

```python
#!/usr/bin/env python3
"""ragex - Smart code search with project isolation and MCP support"""

import argparse
import asyncio
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import List, Optional, Tuple

class RagexCLI:
    """Main RAGex CLI implementation"""
    
    def __init__(self):
        self.docker_image = os.environ.get('RAGEX_DOCKER_IMAGE', 'ragex:local')
        self.user_id = os.getuid()
        self.group_id = os.getgid()
        self.debug = os.environ.get('RAGEX_DEBUG', '').lower() == 'true'
        
    def generate_project_id(self, workspace_path: Path) -> str:
        """Generate consistent project ID based on user and path"""
        abs_path = workspace_path.resolve()
        project_hash = hashlib.sha256(
            f"{self.user_id}:{abs_path}".encode()
        ).hexdigest()[:16]
        return f"ragex_{self.user_id}_{project_hash}"
    
    def parse_args(self) -> argparse.Namespace:
        """Parse command line arguments with subcommands"""
        parser = argparse.ArgumentParser(
            description='RAGex - Smart code search with project isolation',
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog=self.get_examples()
        )
        
        # Global MCP flag (checked before subcommand parsing)
        parser.add_argument('--mcp', action='store_true', 
                          help='Run as MCP server (JSON-RPC over stdio)')
        
        subparsers = parser.add_subparsers(dest='command', help='Commands')
        
        # Index command
        index_parser = subparsers.add_parser('index', 
            help='Build semantic index and start daemon')
        index_parser.add_argument('path', nargs='?', default='.', 
            help='Path to index (default: current directory)')
        
        # Search command
        search_parser = subparsers.add_parser('search', 
            help='Search in current project')
        search_parser.add_argument('query', help='Search query')
        search_parser.add_argument('--limit', type=int, default=50,
            help='Maximum results (default: 50)')
        search_parser.add_argument('--symbol', action='store_true',
            help='Symbol search mode')
        search_parser.add_argument('--regex', action='store_true',
            help='Regex search mode')
        
        # ... other subcommands ...
        
        return parser.parse_args()
    
    def run(self) -> int:
        """Main entry point"""
        # Check for MCP mode first
        if '--mcp' in sys.argv:
            sys.argv.remove('--mcp')
            return self.run_mcp_mode()
        
        # Normal CLI mode
        args = self.parse_args()
        
        # Route to command handlers
        handler = getattr(self, f'cmd_{args.command}', None)
        if handler:
            return handler(args)
        else:
            print(f"Unknown command: {args.command}")
            return 1
    
    def run_mcp_mode(self) -> int:
        """Run as MCP server bridging to daemon"""
        # Import MCP dependencies only when needed
        try:
            from mcp.server import Server
            import mcp.server.stdio
            import mcp.types as types
        except ImportError:
            print("MCP dependencies not installed. Run: pip install mcp", 
                  file=sys.stderr)
            return 1
        
        # Create MCP server that communicates with daemon
        app = Server("ragex-mcp")
        
        @app.call_tool()
        async def handle_call_tool(name: str, arguments: dict):
            # Execute search via daemon with --json flag
            if name == "search_code":
                result = await self.search_via_daemon(
                    query=arguments['query'],
                    mode=arguments.get('mode', 'auto'),
                    limit=arguments.get('limit', 50),
                    json_output=True
                )
                return [types.TextContent(type="text", text=result)]
        
        # Run MCP server on stdio
        asyncio.run(self._run_mcp_server(app))
        return 0
```

## Migration Steps

### Phase 1: Create Python Implementation
1. Implement core `RagexCLI` class with all bash functionality
2. Add comprehensive argument parsing with argparse
3. Implement all command handlers (index, search, stop, etc.)
4. Add project ID generation and daemon management
5. Test each command for compatibility

### Phase 2: Add MCP Support
1. Add `--mcp` flag detection
2. Implement MCP server mode that bridges to daemon
3. Ensure search results use `--json` flag internally
4. Test with Claude Code integration

### Phase 3: Replace Bash Script
1. Extensive testing of Python version
2. Create transition script that warns about change
3. Replace `ragex` bash with Python version
4. Update documentation

## Testing Strategy

### Unit Tests
- Project ID generation
- Argument parsing
- Docker command construction

### Integration Tests
- Daemon start/stop
- Search functionality
- MCP mode communication
- TTY handling

### Compatibility Tests
- All existing commands work identically
- Environment variables respected
- Error messages preserved

## Benefits

1. **Maintainability**: Python is easier to read and modify than bash
2. **Error Handling**: Proper exceptions instead of error codes
3. **Argument Parsing**: argparse provides help, validation, and consistency
4. **Type Safety**: Python's type hints improve code quality
5. **Testing**: Easier to unit test Python functions
6. **Extensibility**: Simpler to add new features
7. **MCP Integration**: Single binary for both CLI and MCP modes

## Risks and Mitigations

### Risk: Breaking Changes
**Mitigation**: Extensive testing, gradual rollout, compatibility mode

### Risk: Performance
**Mitigation**: Python startup is negligible compared to Docker operations

### Risk: Dependency Management  
**Mitigation**: Minimal dependencies, optional MCP imports

## Timeline

- Week 1: Implement core Python CLI with all commands
- Week 2: Add MCP mode and test integration
- Week 3: Testing and documentation
- Week 4: Gradual rollout and monitoring

## Success Criteria

1. All existing `ragex` commands work identically
2. MCP mode successfully integrates with Claude Code
3. Improved error messages and debugging
4. Comprehensive test coverage
5. Positive user feedback on improved usability