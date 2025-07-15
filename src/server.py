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
import sys
import atexit
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime

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

# Setup debug logging
DEBUG_LOG_PATH = "/tmp/mcp_coderag.log"

def setup_debug_logging():
    """Setup debug logging to file"""
    # Create formatter
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    # Create file handler
    file_handler = logging.FileHandler(DEBUG_LOG_PATH, mode='w')
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    
    # Add to root logger to catch everything
    root_logger = logging.getLogger()
    root_logger.addHandler(file_handler)
    
    # Log startup info
    logger.info("="*50)
    logger.info("MCP CodeRAG Server Started")
    logger.info(f"Time: {datetime.now()}")
    logger.info(f"CWD: {os.getcwd()}")
    logger.info(f"MCP_WORKING_DIR: {os.environ.get('MCP_WORKING_DIR', 'Not set')}")
    logger.info(f"Python: {sys.executable}")
    logger.info(f"Arguments: {sys.argv}")
    logger.info(f"Environment PATH: {os.environ.get('PATH', 'Not set')}")
    logger.info("="*50)

def cleanup_debug_log():
    """Remove debug log on exit"""
    if os.path.exists(DEBUG_LOG_PATH):
        try:
            os.remove(DEBUG_LOG_PATH)
            print(f"Cleaned up debug log: {DEBUG_LOG_PATH}")
        except Exception as e:
            print(f"Failed to clean up debug log: {e}")

# Setup debug logging
setup_debug_logging()

# Register cleanup on exit
# atexit.register(cleanup_debug_log)  # Commented out for debugging

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
        # Use MCP_WORKING_DIR if set, otherwise current directory
        cwd = Path(os.environ.get('MCP_WORKING_DIR', os.getcwd()))
        
        for path_str in paths:
            # Resolve relative to working directory
            if os.path.isabs(path_str):
                path = Path(path_str).resolve()
            else:
                path = (cwd / path_str).resolve()
            
            # Ensure path exists
            if not path.exists():
                logger.warning(f"Path does not exist: {path}")
                continue
                
            # For now, allow any path (you can add security checks later)
            validated_paths.append(path)
        
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
        
        # Log search request
        logger.info(f"Search request: pattern='{pattern}', file_types={file_types}, paths={paths}")
        logger.info(f"Working directory: {os.getcwd()}")
        logger.info(f"MCP_WORKING_DIR: {os.environ.get('MCP_WORKING_DIR', 'Not set')}")
        
        # Validate inputs
        try:
            pattern = self.validate_pattern(pattern)
        except ValueError as e:
            logger.error(f"Pattern validation failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "pattern": pattern,
                "total_matches": 0,
                "matches": [],
            }
        
        search_paths = self.validate_paths(paths or ["."])
        logger.info(f"Validated search paths: {[str(p) for p in search_paths]}")
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
        
        # Log the full command
        logger.info(f"Ripgrep command: {' '.join(cmd)}")
        
        # Track search time
        import time
        search_start = time.time()
        
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
            
            # Log search completion time
            search_time = time.time() - search_start
            logger.info(f"Search completed in {search_time:.3f} seconds")
            
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
            
            # Log search results
            logger.info(f"Found {len(matches)} matches, returning {min(len(matches), limit)}")
            
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

# Initialize semantic search components
semantic_searcher = None
semantic_available = False

try:
    from .embedding_manager import EmbeddingManager
    from .vector_store import CodeVectorStore
    from .indexer import CodeIndexer
    
    # Check if semantic index exists
    index_path = Path("./chroma_db")
    if index_path.exists():
        vector_store = CodeVectorStore()
        stats = vector_store.get_statistics()
        if stats['total_symbols'] > 0:
            embedder = EmbeddingManager()
            semantic_searcher = {
                'embedder': embedder,
                'vector_store': vector_store,
                'indexer': CodeIndexer()
            }
            semantic_available = True
            logger.info(f"Semantic search available with {stats['total_symbols']} symbols")
        else:
            logger.warning("Semantic index exists but is empty")
    else:
        logger.warning("Semantic search index not found. Run 'python scripts/build_semantic_index.py' to enable.")
        
except ImportError as e:
    logger.warning(f"Semantic search dependencies not available: {e}")
except Exception as e:
    logger.warning(f"Failed to initialize semantic search: {e}")


# Search mode detection and enhancement
def detect_query_type(query: str) -> str:
    """Detect the best search mode based on query characteristics"""
    
    # Check for regex patterns
    regex_indicators = [
        r'\.',      # literal dots
        r'\*',      # wildcards  
        r'\+',      # plus quantifier
        r'\?',      # optional quantifier
        r'\[.*\]',  # character classes
        r'\{.*\}',  # quantifiers
        r'\^',      # start anchor
        r'\$',      # end anchor
        r'\|',      # alternation
        r'\\[a-z]', # escape sequences
    ]
    
    if any(re.search(pattern, query) for pattern in regex_indicators):
        return "regex"
    
    # Check for symbol-like queries
    symbol_indicators = [
        r'^[a-zA-Z_][a-zA-Z0-9_]*$',  # Simple identifier
        r'^class\s+\w+',              # "class MyClass"
        r'^def\s+\w+',                # "def function_name"
        r'^function\s+\w+',           # "function myFunc"
        r'^\w+\s*\(',                 # "funcName("
    ]
    
    if any(re.search(pattern, query, re.IGNORECASE) for pattern in symbol_indicators):
        return "symbol"
    
    # Check for natural language queries
    natural_language_indicators = [
        r'\b(functions?|methods?|classes?)\s+(that|which|for)\b',
        r'\b(how to|where|what|when|why)\b',
        r'\b(handles?|processes?|manages?|creates?|validates?)\b',
        r'\b(error|exception|authentication|database|queue|file)\b',
        r'\s(and|or|with|for|in|on|at|by)\s',
        r'\b(submit|send|process|handle|create|delete|update)\b',
    ]
    
    if any(re.search(pattern, query, re.IGNORECASE) for pattern in natural_language_indicators):
        return "semantic"
    
    # Default fallback logic
    if len(query.split()) >= 3:  # Multi-word queries likely semantic
        return "semantic"
    elif query.isidentifier():   # Valid identifier -> symbol search
        return "symbol"
    else:                        # Everything else -> regex
        return "regex"


def enhance_query_for_mode(query: str, mode: str) -> str:
    """Enhance query based on the selected mode"""
    
    if mode == "semantic":
        # Add context for better semantic matching
        enhanced = query
        
        # Add programming context
        if not any(word in query.lower() for word in ["function", "class", "method", "code"]):
            enhanced = f"code {enhanced}"
        
        # Expand abbreviations
        abbreviations = {
            "auth": "authentication",
            "db": "database", 
            "config": "configuration",
            "util": "utility",
            "impl": "implementation"
        }
        
        for abbr, full in abbreviations.items():
            enhanced = re.sub(rf'\b{abbr}\b', full, enhanced, flags=re.IGNORECASE)
        
        return enhanced
    
    elif mode == "symbol":
        # Clean up symbol queries
        # Remove common prefixes
        cleaned = re.sub(r'^(def|class|function)\s+', '', query, flags=re.IGNORECASE)
        # Remove parentheses
        cleaned = re.sub(r'\s*\(.*\)', '', cleaned)
        return cleaned.strip()
    
    elif mode == "regex":
        # Escape special chars if it doesn't look like intentional regex
        if not any(char in query for char in r'.*+?[]{}()^$|\\'):
            return re.escape(query)
        return query
    
    return query


def get_fallback_chain(preferred_mode: str, query: str) -> List[str]:
    """Get intelligent fallback chain based on preferred mode"""
    
    if preferred_mode == "semantic":
        # Semantic failed -> try symbol if looks like identifier, else regex
        if query.replace("_", "").isalnum():
            return ["symbol", "regex"]
        else:
            return ["regex", "symbol"]
    
    elif preferred_mode == "symbol":
        # Symbol failed -> try regex (maybe partial match), then semantic
        return ["regex", "semantic"]
    
    elif preferred_mode == "regex":
        # Regex failed -> try semantic (maybe they meant natural language)
        return ["semantic", "symbol"]
    
    return []


def generate_search_guidance(query: str, mode: str) -> Dict:
    """Generate helpful guidance when search fails"""
    
    guidance = {
        "message": f"No results found for '{query}' in {mode} mode.",
        "suggestions": []
    }
    
    if mode == "semantic":
        guidance["suggestions"] = [
            f"Try symbol mode if you know specific names: search_code('{query.split()[0] if query.split() else query}', mode='symbol')",
            f"Try regex mode for patterns: search_code('{query}.*', mode='regex')",
            "Make query more specific: 'functions that handle file upload validation'",
            "Try broader terms: 'file processing code' or 'queue management'"
        ]
    
    elif mode == "symbol":
        guidance["suggestions"] = [
            f"Try semantic mode: search_code('functions related to {query}', mode='semantic')",
            f"Try partial regex: search_code('{query}.*', mode='regex')",
            "Check spelling and capitalization",
            "Try variations: CamelCase, snake_case, kebab-case"
        ]
    
    elif mode == "regex":
        guidance["suggestions"] = [
            f"Try semantic mode: search_code('code that handles {query}', mode='semantic')",
            "Simplify pattern - remove some wildcards",
            "Try case-insensitive search",
            "Check regex syntax"
        ]
    
    return guidance


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