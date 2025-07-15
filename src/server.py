#!/usr/bin/env python3
"""
MCP Code Search Server - A secure ripgrep-based code search server
"""

import asyncio
import json
import logging
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Any

from mcp.server import Server, NotificationOptions
from mcp.server.models import InitializationOptions
import mcp.server.stdio
import mcp.types as types

# Import Tree-sitter enhancer
try:
    from .tree_sitter_enhancer import TreeSitterEnhancer
    from .pattern_matcher import PatternMatcher
except ImportError:
    from tree_sitter_enhancer import TreeSitterEnhancer
    from pattern_matcher import PatternMatcher

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("coderag-mcp")

# Security constants
MAX_RESULTS = 200
DEFAULT_RESULTS = 50
MAX_PATTERN_LENGTH = 500
ALLOWED_FILE_TYPES = {
    "py", "python", "js", "javascript", "ts", "typescript", 
    "java", "cpp", "c", "go", "rust", "rb", "ruby", "php",
    "cs", "csharp", "swift", "kotlin", "scala", "r", "lua",
    "sh", "bash", "ps1", "yaml", "yml", "json", "xml", "html",
    "css", "scss", "sass", "sql", "md", "markdown", "txt"
}

class RipgrepSearcher:
    """Manages ripgrep subprocess with security and performance optimizations"""
    
    def __init__(self, pattern_matcher: Optional[PatternMatcher] = None):
        self.rg_path = shutil.which("rg")
        if not self.rg_path:
            raise RuntimeError("ripgrep (rg) not found. Please install ripgrep.")
        
        # Pattern matcher for exclusions
        self.pattern_matcher = pattern_matcher or PatternMatcher()
        
        # Base arguments for all searches
        self.base_args = [
            "--json",           # JSON output for parsing
            "--no-heading",     # Disable grouping by file
            "--with-filename",  # Include filename in results
            "--line-number",    # Include line numbers
            "--no-config",      # Ignore user config files
            "--max-columns", "500",  # Limit line length
            "--max-columns-preview",  # Show preview of long lines
        ]
    
    def validate_pattern(self, pattern: str) -> str:
        """Validate and sanitize regex pattern"""
        if not pattern or len(pattern) > MAX_PATTERN_LENGTH:
            raise ValueError(f"Pattern must be 1-{MAX_PATTERN_LENGTH} characters")
        
        # Basic validation - ensure it's a valid regex
        try:
            re.compile(pattern)
        except re.error as e:
            raise ValueError(f"Invalid regex pattern: {e}")
        
        return pattern
    
    def validate_paths(self, paths: List[str]) -> List[Path]:
        """Validate and resolve search paths"""
        validated_paths = []
        cwd = Path.cwd()
        
        for path_str in paths:
            path = Path(path_str).resolve()
            
            # Ensure path exists and is within current directory or subdirectories
            if not path.exists():
                logger.warning(f"Path does not exist: {path}")
                continue
                
            # Security: ensure we're not searching outside project directory
            try:
                path.relative_to(cwd)
                validated_paths.append(path)
            except ValueError:
                logger.warning(f"Path outside project directory: {path}")
                continue
        
        return validated_paths or [cwd]
    
    async def search(
        self,
        pattern: str,
        file_types: Optional[List[str]] = None,
        paths: Optional[List[str]] = None,
        limit: int = DEFAULT_RESULTS,
        case_sensitive: bool = False,
        exclude_patterns: Optional[List[str]] = None,
        respect_gitignore: bool = True,
    ) -> Dict[str, Any]:
        """Execute ripgrep search with given parameters"""
        
        # Validate inputs
        try:
            pattern = self.validate_pattern(pattern)
        except ValueError as e:
            return {
                "success": False,
                "error": str(e),
                "pattern": pattern,
                "total_matches": 0,
                "matches": [],
            }
        
        search_paths = self.validate_paths(paths or ["."])
        limit = min(max(1, limit), MAX_RESULTS)
        
        # Build command
        cmd = [self.rg_path] + self.base_args
        
        # Handle gitignore
        if not respect_gitignore:
            cmd.append("--no-ignore")
        
        # Add exclusion patterns
        if exclude_patterns:
            # Create temporary pattern matcher with custom patterns
            matcher = PatternMatcher(custom_patterns=exclude_patterns)
        else:
            matcher = self.pattern_matcher
        
        # Add exclusion arguments from pattern matcher
        cmd.extend(matcher.get_ripgrep_args())
        
        # Add file type filters
        if file_types:
            for ft in file_types:
                if ft in ALLOWED_FILE_TYPES:
                    cmd.extend(["--type", ft])
        
        # Add case sensitivity flag
        if not case_sensitive:
            cmd.append("--ignore-case")
        
        # Add max count
        cmd.extend(["--max-count", str(limit)])
        
        # Add pattern
        cmd.append(pattern)
        
        # Add paths
        cmd.extend(str(p) for p in search_paths)
        
        # Execute search
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=30.0  # 30 second timeout
            )
            
            if process.returncode not in (0, 1):  # 0=matches found, 1=no matches
                raise RuntimeError(f"ripgrep failed: {stderr.decode()}")
            
            # Parse results
            matches = []
            for line in stdout.decode().strip().split('\n'):
                if not line:
                    continue
                    
                try:
                    data = json.loads(line)
                    if data.get("type") == "match":
                        match_data = data["data"]
                        matches.append({
                            "file": match_data["path"]["text"],
                            "line_number": match_data["line_number"],
                            "line": match_data["lines"]["text"].strip(),
                            "column": match_data.get("submatches", [{}])[0].get("start", 0),
                        })
                except json.JSONDecodeError:
                    logger.warning(f"Failed to parse line: {line}")
                    continue
            
            return {
                "success": True,
                "pattern": pattern,
                "total_matches": len(matches),
                "matches": matches[:limit],  # Ensure we respect limit
                "truncated": len(matches) > limit,
            }
            
        except asyncio.TimeoutError:
            return {
                "success": False,
                "error": "Search timed out after 30 seconds",
                "pattern": pattern,
            }
        except Exception as e:
            logger.error(f"Search error: {e}")
            return {
                "success": False,
                "error": str(e),
                "pattern": pattern,
            }


# Initialize server
app = Server("coderag-mcp")

# Initialize shared pattern matcher
pattern_matcher = PatternMatcher()

# Initialize components with same pattern matcher
searcher = RipgrepSearcher(pattern_matcher)

# Initialize Tree-sitter enhancer
try:
    enhancer = TreeSitterEnhancer(pattern_matcher)
    logger.info("Tree-sitter enhancer initialized successfully")
except Exception as e:
    logger.warning(f"Failed to initialize Tree-sitter enhancer: {e}")
    enhancer = None

@app.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    """List available tools"""
    return [
        types.Tool(
            name="search_code",
            description="Search for code patterns using ripgrep. Supports regex patterns and file type filtering.",
            inputSchema={
                "type": "object",
                "properties": {
                    "pattern": {
                        "type": "string",
                        "description": "Regex pattern to search for",
                    },
                    "file_types": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": f"File types to search in. Options: {', '.join(sorted(ALLOWED_FILE_TYPES))}",
                    },
                    "paths": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Paths to search in (relative to current directory)",
                    },
                    "limit": {
                        "type": "integer",
                        "description": f"Maximum results to return (1-{MAX_RESULTS}, default: {DEFAULT_RESULTS})",
                        "minimum": 1,
                        "maximum": MAX_RESULTS,
                    },
                    "case_sensitive": {
                        "type": "boolean",
                        "description": "Whether search should be case sensitive (default: false)",
                    },
                    "include_symbols": {
                        "type": "boolean",
                        "description": "Include symbol context (function/class info) in results (default: false)",
                    },
                    "exclude_patterns": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Additional patterns to exclude (gitignore syntax). Default exclusions: .venv/**, __pycache__/**, etc.",
                    },
                    "respect_gitignore": {
                        "type": "boolean",
                        "description": "Whether to respect .gitignore files (default: true)",
                    },
                    "format": {
                        "type": "string",
                        "enum": ["navigation", "raw"],
                        "description": "Output format: 'navigation' for human-friendly file grouping (default), 'raw' for simple file:line format",
                    },
                },
                "required": ["pattern"],
            },
        ),
    ]

@app.call_tool()
async def handle_call_tool(
    name: str, arguments: dict | None
) -> list[types.TextContent | types.ImageContent | types.EmbeddedResource]:
    """Handle tool calls"""
    
    if name != "search_code":
        raise ValueError(f"Unknown tool: {name}")
    
    if not arguments:
        raise ValueError("Missing arguments")
    
    # Extract arguments
    pattern = arguments.get("pattern")
    if not pattern:
        raise ValueError("Pattern is required")
    
    file_types = arguments.get("file_types", [])
    paths = arguments.get("paths", ["."])
    limit = arguments.get("limit", DEFAULT_RESULTS)
    case_sensitive = arguments.get("case_sensitive", False)
    include_symbols = arguments.get("include_symbols", False)
    exclude_patterns = arguments.get("exclude_patterns", None)
    respect_gitignore = arguments.get("respect_gitignore", True)
    output_format = arguments.get("format", "navigation")
    
    # Perform search
    result = await searcher.search(
        pattern=pattern,
        file_types=file_types,
        paths=paths,
        limit=limit,
        case_sensitive=case_sensitive,
        exclude_patterns=exclude_patterns,
        respect_gitignore=respect_gitignore,
    )
    
    # Enhance with Tree-sitter if requested and available
    if include_symbols and enhancer and result["success"]:
        try:
            result = await enhancer.enhance_search_results(result)
        except Exception as e:
            logger.warning(f"Failed to enhance results with Tree-sitter: {e}")
    
    # Format response based on requested format
    if result["success"]:
        if output_format == "raw":
            # Simple format: just file:line references
            response_text = ""
            if result.get("matches"):
                for match in result["matches"]:
                    response_text += f"{match['file']}:{match['line_number']}\n"
                if result.get("truncated"):
                    response_text += f"\n[Truncated to {limit} results]"
            else:
                response_text = "No matches found."
            return [types.TextContent(type="text", text=response_text)]
        # Group matches by file for better navigation
        matches_by_file = {}
        for match in result.get("matches", []):
            file_path = match["file"]
            if file_path not in matches_by_file:
                matches_by_file[file_path] = []
            matches_by_file[file_path].append(match)
        
        # Build response with file-centric format
        response_text = f"## Search Results: '{result['pattern']}'\n\n"
        response_text += f"**Summary**: {result['total_matches']} matches in {len(matches_by_file)} files\n\n"
        
        if matches_by_file:
            response_text += "### Files with matches:\n\n"
            
            # List all files first for quick navigation
            for file_path in sorted(matches_by_file.keys()):
                match_count = len(matches_by_file[file_path])
                response_text += f"- `{file_path}` ({match_count} match{'es' if match_count > 1 else ''})\n"
            
            response_text += "\n### Match details:\n\n"
            
            # Then show details grouped by file
            for file_path in sorted(matches_by_file.keys()):
                matches = matches_by_file[file_path]
                response_text += f"#### {file_path}\n"
                
                for match in matches:
                    line_num = match['line_number']
                    line_preview = match['line'].strip()
                    
                    # Truncate long lines
                    if len(line_preview) > 80:
                        line_preview = line_preview[:77] + "..."
                    
                    response_text += f"- Line {line_num}: `{line_preview}`\n"
                    
                    # Add symbol context if available
                    if "symbol_context" in match:
                        ctx = match["symbol_context"]
                        context_parts = [f"{ctx['type']} '{ctx['name']}'"]
                        if ctx.get('parent'):
                            context_parts.append(f"in {ctx['parent']}")
                        response_text += f"  Context: {' '.join(context_parts)}\n"
                
                response_text += "\n"
            
            if result.get("truncated"):
                response_text += f"*Note: Results truncated to {limit} matches*\n"
        else:
            response_text += "No matches found.\n"
    else:
        response_text = f"Search failed: {result['error']}"
    
    return [types.TextContent(type="text", text=response_text)]

async def main():
    """Run the MCP server"""
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="coderag-mcp",
                server_version="0.1.0",
                capabilities=app.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )

if __name__ == "__main__":
    asyncio.run(main())