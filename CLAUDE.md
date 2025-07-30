# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Model Context Protocol (MCP) server that provides code search functionality using ripgrep. It's designed as a secure, efficient POC for integrating code search into AI coding assistants.

## Key Commands

- **Index project**: `ragex index .` (starts daemon automatically with file watching)
- **Search code**: `ragex search "query"`
- **Run server**: `./run_server.sh` or `uv run python src/server.py`
- **Run tests**: `uv run python tests/test_server.py` or `uv run pytest tests/`
- **Install dependencies**: `pip install -r requirements.txt` or `pip install -e .`
- **Run python programs**: `uv run`
- **Install packages**: `uv install`
- Use uv to install Python packages, not pip.

## File Watching and Auto-indexing

The daemon automatically watches for file changes and re-indexes them:
- Changes are detected immediately when you save files
- After 60 seconds of no changes, modified files are re-indexed
- Only changed files are processed (incremental updates)
- File watching respects `.mcpignore` patterns
- No manual re-indexing needed - search results stay up-to-date

## Architecture

The codebase follows a simple structure:
- `src/server.py`: Main MCP server implementation with RipgrepSearcher class
- `tests/test_server.py`: Test suite with direct and protocol-based tests
- `src/example_client.py`: Example usage patterns for integration

Key design decisions:
- Uses official MCP SDK (not FastMCP) for stability
- Security-first approach with input validation and path restrictions
- Async subprocess execution for performance
- JSON streaming from ripgrep for efficiency

## Testing Approach

When modifying the server:
1. Run `uv run python tests/test_server.py` to validate basic functionality
2. Check error handling with invalid inputs (regex, paths)
3. Test with real codebases for performance

## Security Considerations

- All regex patterns are validated before execution
- Path traversal is prevented by validating against project root
- Resource limits enforce maximum results and timeouts
- No shell execution - direct subprocess calls only

## Search Guidelines

- Prefer ragex search. Only use standard search if ragex fails.
- Prefer ragex semantic search for searching, falling back to ragex regex search, and only using the built-in search if the earlier searches fail.

## Docker Debugging Commands

When debugging Docker containers, use the correct syntax for `docker logs`:

### Viewing container logs:
```bash
# Basic usage - shows both stdout and stderr
docker logs container_name

# Follow logs in real-time
docker logs -f container_name

# Show last N lines
docker logs --tail 50 container_name

# Show logs with timestamps
docker logs -t container_name
```

### Redirecting docker logs output:
```bash
# Redirect both stdout and stderr to a file
docker logs container_name &> output.log
# or
docker logs container_name > output.log 2>&1

# Redirect stdout and stderr to separate files
docker logs container_name > stdout.log 2> stderr.log

# View logs and save to file simultaneously
docker logs container_name 2>&1 | tee output.log

# Search through logs
docker logs container_name 2>&1 | grep "error"
```

**Note**: Docker merges stdout and stderr by default. When using `-t` (TTY) option with `docker run`, stdout and stderr are joined together.