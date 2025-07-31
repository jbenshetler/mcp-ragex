#!/usr/bin/env python3
"""
MCP (Model Context Protocol) server for RAGex

This server runs inside the container where all dependencies are available.
It provides search functionality to MCP clients like Claude.
"""

import asyncio
import json
import os
import sys
import logging
from pathlib import Path
from typing import List, Optional

# MCP imports
try:
    from mcp.server import Server, NotificationOptions
    from mcp.server.models import InitializationOptions
    import mcp.server.stdio
    import mcp.types as types
except ImportError as e:
    # Output JSON-RPC error response for missing dependencies
    error_response = {
        "jsonrpc": "2.0",
        "id": None,  # No request ID for startup errors
        "error": {
            "code": -32603,  # Internal error
            "message": "Failed to import MCP dependencies",
            "data": {
                "detail": str(e),
                "hint": "This should be run inside the ragex container"
            }
        }
    }
    print(json.dumps(error_response))
    sys.exit(1)

# Import search functionality
from src.cli.search import run_search, SearchClient
from src.ragex_core.project_utils import get_chroma_db_path

__version__ = "1.0.0"

# Configure logging
logging.basicConfig(
    level=logging.WARNING,  # Only show warnings and errors
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('mcp-server')


class RagexMCPServer:
    """MCP server implementation for RAGex"""
    
    def __init__(self):
        self.app = Server("ragex-mcp")
        self.search_client = None
        self._setup_handlers()
    
    def _setup_handlers(self):
        """Set up MCP handlers"""
        
        @self.app.list_tools()
        async def handle_list_tools() -> List[types.Tool]:
            """List available tools"""
            return [
                types.Tool(
                    name="search_code",
                    description="Search code in the current project using semantic, symbol, or regex search",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "Search query"
                            },
                            "mode": {
                                "type": "string",
                                "enum": ["auto", "semantic", "symbol", "regex"],
                                "default": "auto",
                                "description": "Search mode: auto (default), semantic, symbol, or regex"
                            },
                            "limit": {
                                "type": "integer",
                                "default": 50,
                                "description": "Maximum number of results to return"
                            }
                        },
                        "required": ["query"]
                    }
                )
            ]
        
        @self.app.call_tool()
        async def handle_call_tool(name: str, arguments: dict) -> List:
            """Handle tool calls"""
            if name == "search_code":
                return await self._handle_search(arguments)
            else:
                raise ValueError(f"Unknown tool: {name}")
    
    async def _initialize_search_client(self) -> bool:
        """Initialize the search client if needed"""
        if self.search_client is not None:
            return True
        
        try:
            # Get project data directory
            from src.ragex_core.project_utils import get_project_data_dir
            project_data_dir = get_project_data_dir()
            
            # Check if ChromaDB exists
            chroma_path = get_chroma_db_path(project_data_dir)
            if not chroma_path.exists():
                logger.warning(f"ChromaDB not found at {chroma_path}")
                return False
            
            # Create search client with project data dir (not chroma path)
            logger.info(f"Creating SearchClient with project_data_dir: {project_data_dir}")
            self.search_client = SearchClient(project_data_dir, json_output=True)
            logger.info(f"Search client initialized successfully: {self.search_client}")
            logger.info(f"Semantic searcher available: {self.search_client.semantic_searcher is not None}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize search client: {e}")
            return False
    
    async def _handle_search(self, arguments: dict) -> List:
        """Handle search_code tool call"""
        logger.info(f"_handle_search called with: {arguments}")
        query = arguments.get('query', '')
        mode = arguments.get('mode', 'auto')
        limit = arguments.get('limit', 50)
        
        # Initialize search client if needed
        logger.info("Initializing search client...")
        if not await self._initialize_search_client():
            error_result = {
                "success": False,
                "error": "Search index not available. Please run 'ragex index' first.",
                "query": query,
                "mode": mode,
                "total_matches": 0,
                "matches": []
            }
            return [types.TextContent(
                type="text",
                text=json.dumps(error_result, indent=2)
            )]
        
        # Create args namespace for run_search
        class Args:
            def __init__(self):
                self.query = query
                self.limit = limit
                self.symbol = mode == 'symbol'
                self.regex = mode == 'regex'
                self.json = True  # Always use JSON output for MCP
                self.mode = 'symbol' if self.symbol else ('regex' if self.regex else 'semantic')
                self.similarity_threshold = 0.3
                self.context_lines = 3
                self.file_types = None
                self.paths = None
                self.exclude_patterns = None
                self.case_sensitive = False
                self.show_score = False
                self.verbose = False
        
        args = Args()
        
        # Capture output
        import io
        from contextlib import redirect_stdout, redirect_stderr
        
        stdout_capture = io.StringIO()
        stderr_capture = io.StringIO()
        
        try:
            logger.info(f"Running search with args: query={query}, mode={mode}, limit={limit}")
            with redirect_stdout(stdout_capture), redirect_stderr(stderr_capture):
                # Run search with our search client
                logger.info("Calling run_search...")
                returncode = await run_search(args, search_client=self.search_client)
                logger.info(f"run_search returned: {returncode}")
            
            stdout_content = stdout_capture.getvalue()
            stderr_content = stderr_capture.getvalue()
            
            if returncode == 0 and stdout_content:
                # Return the JSON output
                return [types.TextContent(type="text", text=stdout_content)]
            else:
                # Handle error
                error_result = {
                    "success": False,
                    "error": stderr_content or "Search failed",
                    "query": query,
                    "mode": mode,
                    "total_matches": 0,
                    "matches": []
                }
                return [types.TextContent(
                    type="text",
                    text=json.dumps(error_result, indent=2)
                )]
                
        except Exception as e:
            logger.error(f"Search error: {e}", exc_info=True)
            error_result = {
                "success": False,
                "error": str(e),
                "query": query,
                "mode": mode,
                "total_matches": 0,
                "matches": []
            }
            return [types.TextContent(
                type="text",
                text=json.dumps(error_result, indent=2)
            )]
    
    async def run(self):
        """Run the MCP server"""
        async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
            await self.app.run(
                read_stream,
                write_stream,
                InitializationOptions(
                    server_name="ragex-mcp",
                    server_version=__version__,
                    capabilities=self.app.get_capabilities(
                        notification_options=NotificationOptions(),
                        experimental_capabilities={},
                    ),
                ),
            )


async def main():
    """Main entry point"""
    # Log startup (no prints to avoid breaking MCP protocol)
    logger.info("Starting RAGex MCP server")
    
    # Create and run server
    server = RagexMCPServer()
    
    try:
        await server.run()
    except KeyboardInterrupt:
        logger.info("MCP server interrupted")
    except Exception as e:
        logger.error(f"MCP server error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    asyncio.run(main())