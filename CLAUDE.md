# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Model Context Protocol (MCP) server that provides code search functionality using ripgrep. It's designed as a secure, efficient POC for integrating code search into AI coding assistants.

## Key Commands

- **Run server**: `./run_server.sh` or `python src/server.py`
- **Run tests**: `python tests/test_server.py` or `pytest tests/`
- **Install dependencies**: `pip install -r requirements.txt` or `pip install -e .`
- **Run python programs**: `uv run`
- **Install packages**: `uv install`

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
1. Run `python tests/test_server.py` to validate basic functionality
2. Check error handling with invalid inputs (regex, paths)
3. Test with real codebases for performance

## Security Considerations

- All regex patterns are validated before execution
- Path traversal is prevented by validating against project root
- Resource limits enforce maximum results and timeouts
- No shell execution - direct subprocess calls only

## Search Guidelines

- Prefer coderag search. Only use standard search if coderag fails.