#!/usr/bin/env python3
"""
Refactored MCP Code Search Server - Uses CLI SearchClient directly
"""

import asyncio
import json
import logging
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime

from mcp.server import Server, NotificationOptions
from mcp.server.models import InitializationOptions
import mcp.server.stdio
import mcp.types as types

# Import the working CLI search components
from src.cli.search import SearchClient
from src.utils import configure_logging, get_logger

# Configure logging
if os.environ.get('RAGEX_DAEMON_INITIALIZED') != '1':
    configure_logging()

logger = get_logger("ragex-mcp-refactored")

# Initialize server
app = Server("ragex-mcp")

# Global search client instance
search_client = None


def get_project_directory() -> str:
    """Get the project directory for ChromaDB, matching daemon behavior"""
    # Check for explicit project data dir (same as daemon)
    project_data_dir = os.environ.get('RAGEX_PROJECT_DATA_DIR')
    if project_data_dir:
        return project_data_dir
    
    # Check for project name
    project_name = os.environ.get('PROJECT_NAME')
    if project_name:
        return f'/data/projects/{project_name}'
    
    # Check MCP_WORKING_DIR (where Claude Code was launched from)
    mcp_working_dir = os.environ.get('MCP_WORKING_DIR')
    if mcp_working_dir:
        return mcp_working_dir
    
    # Default to current directory
    return str(Path.cwd())


def initialize_search_client():
    """Initialize the search client with proper project directory"""
    global search_client
    
    project_dir = get_project_directory()
    logger.info(f"Initializing SearchClient with project directory: {project_dir}")
    
    try:
        search_client = SearchClient(index_dir=project_dir)
        logger.info("SearchClient initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize SearchClient: {e}")
        search_client = SearchClient()  # Fallback without semantic search


# Initialize on startup
initialize_search_client()


def detect_search_mode(query: str) -> str:
    """Simple mode detection based on query characteristics"""
    import re
    
    # Check for regex patterns
    if any(char in query for char in r'.*+?[]{}()^$|\\'):
        return "regex"
    
    # Check for simple identifier (likely symbol search)
    if re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', query):
        return "symbol"
    
    # Default to semantic for natural language queries
    return "semantic"


@app.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    """List available tools"""
    return [
        types.Tool(
            name="search_code",
            description="Intelligent code search with automatic mode detection. Use 'semantic' mode when searching for concepts or functionality. Use 'symbol' or 'regex' modes when you know specific names or patterns.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query (natural language for semantic search, exact names for symbol search, or patterns for regex search)",
                    },
                    "mode": {
                        "type": "string",
                        "enum": ["auto", "semantic", "symbol", "regex"],
                        "description": "Search mode - 'auto' (default): automatically detects best mode. 'semantic': natural language search for concepts/functionality. 'symbol': exact function/class/variable names. 'regex': pattern matching with regular expressions",
                        "default": "auto"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum results to return (1-200, default: 50)",
                        "minimum": 1,
                        "maximum": 200,
                        "default": 50
                    },
                    "format": {
                        "type": "string",
                        "enum": ["navigation", "raw"],
                        "description": "Output format: 'navigation' for human-friendly file grouping (default), 'raw' for simple file:line format",
                        "default": "navigation"
                    },
                },
                "required": ["query"],
            },
        ),
        types.Tool(
            name="search_code_simple", 
            description="Simple search interface - just provide a query and let the system handle everything",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Your search query in any format",
                    },
                },
                "required": ["query"],
            },
        ),
    ]


@app.call_tool()
async def handle_call_tool(
    name: str, arguments: dict | None
) -> list[types.TextContent | types.ImageContent | types.EmbeddedResource]:
    """Handle tool calls"""
    
    if not arguments:
        arguments = {}
    
    if name == "search_code":
        query = arguments.get('query')
        if not query:
            raise ValueError("Missing query argument")
        
        mode = arguments.get('mode', 'auto')
        limit = min(arguments.get('limit', 50), 200)
        format_type = arguments.get('format', 'navigation')
        
        return await handle_search(query, mode, limit, format_type)
    
    elif name == "search_code_simple":
        query = arguments.get('query')
        if not query:
            raise ValueError("Missing query argument")
        
        return await handle_search(query, 'auto', 50, 'navigation')
    
    else:
        raise ValueError(f"Unknown tool: {name}")


async def handle_search(query: str, mode: str, limit: int, format_type: str) -> List[types.TextContent]:
    """Handle search using the CLI SearchClient"""
    global search_client
    
    # Detect mode if auto
    if mode == "auto":
        mode = detect_search_mode(query)
        logger.info(f"Auto-detected mode: {mode} for query: '{query}'")
    
    # Ensure search client is initialized
    if not search_client:
        initialize_search_client()
    
    # Perform search using the CLI SearchClient methods
    try:
        matches = []
        
        if mode == "semantic":
            if search_client.semantic_searcher:
                matches = await search_client.search_semantic(query, limit)
            else:
                # Fallback to regex if semantic not available
                logger.warning("Semantic search not available, falling back to regex")
                mode = "regex"
                matches = await search_client.search_regex(query, limit)
        
        elif mode == "symbol":
            matches = await search_client.search_symbol(query, limit)
        
        elif mode == "regex":
            matches = await search_client.search_regex(query, limit)
        
        # Build result structure
        result = {
            "success": True,
            "pattern": query,
            "query": query,
            "mode": mode,
            "total_matches": len(matches),
            "matches": matches,
            "truncated": False
        }
        
        # Format based on requested format
        if format_type == "raw":
            # Simple format
            lines = []
            for match in matches:
                file_path = match.get('file', '')
                line_num = match.get('line', match.get('line_number', 0))
                lines.append(f"{file_path}:{line_num}")
            response_text = "\n".join(lines) if lines else "No matches found."
        else:
            # Navigation format
            response_text = format_navigation_output(result)
        
        # Return as JSON for MCP compatibility
        return [types.TextContent(type="text", text=json.dumps(result, indent=2))]
        
    except Exception as e:
        logger.error(f"Search error: {e}")
        error_result = {
            "success": False,
            "error": str(e),
            "pattern": query,
            "query": query,
            "mode": mode,
            "total_matches": 0,
            "matches": []
        }
        return [types.TextContent(type="text", text=json.dumps(error_result, indent=2))]


def format_navigation_output(result: Dict) -> str:
    """Format search results for navigation display"""
    matches_by_file = {}
    for match in result.get("matches", []):
        file_path = match.get("file", "")
        if file_path not in matches_by_file:
            matches_by_file[file_path] = []
        matches_by_file[file_path].append(match)
    
    lines = [
        f"## Search Results: '{result.get('query', '')}'",
        f"**Mode**: {result.get('mode', 'unknown')}",
        f"**Total matches**: {result.get('total_matches', 0)} in {len(matches_by_file)} files",
        ""
    ]
    
    if matches_by_file:
        lines.append("### Files with matches:")
        for file_path in sorted(matches_by_file.keys()):
            count = len(matches_by_file[file_path])
            lines.append(f"- `{file_path}` ({count} match{'es' if count > 1 else ''})")
        
        lines.extend(["", "### Match details:"])
        for file_path in sorted(matches_by_file.keys()):
            lines.append(f"\n#### {file_path}")
            for match in matches_by_file[file_path]:
                line_num = match.get('line', match.get('line_number', 0))
                
                # Handle different match formats
                if 'code' in match:  # Semantic search result
                    preview = match['code'].split('\n')[0][:80]
                    lines.append(f"- Line {line_num}: `{preview}`")
                    if 'similarity' in match:
                        lines.append(f"  Similarity: {match['similarity']:.2f}")
                else:  # Regex/symbol result
                    line_content = match.get('line', '').strip()[:80]
                    lines.append(f"- Line {line_num}: `{line_content}`")
    else:
        lines.append("No matches found.")
    
    return "\n".join(lines)


async def main():
    """Run the MCP server"""
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="ragex-mcp",
                server_version="0.1.0",
                capabilities=app.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )


if __name__ == "__main__":
    asyncio.run(main())