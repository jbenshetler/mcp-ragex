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
        
        # Log search request with mode indication
        logger.info(f"🔍 REGEX search: pattern='{pattern}', file_types={file_types}, paths={paths}")
        logger.debug(f"Working directory: {os.getcwd()}")
        logger.debug(f"MCP_WORKING_DIR: {os.environ.get('MCP_WORKING_DIR', 'Not set')}")
        
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
        logger.debug(f"Validated search paths: {[str(p) for p in search_paths]}")
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
        logger.debug(f"Ripgrep command: {' '.join(cmd)}")
        
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
    # Import semantic search modules
    import sys
    import os
    from pathlib import Path
    
    # Add the current directory to the path for imports
    current_dir = Path(__file__).parent
    if str(current_dir) not in sys.path:
        sys.path.insert(0, str(current_dir))
    
    # Try importing the semantic search modules
    try:
        from embedding_manager import EmbeddingManager
        from vector_store import CodeVectorStore
        from indexer import CodeIndexer
    except ImportError:
        # If that fails, try with full path
        import importlib.util
        
        def load_module(name, path):
            spec = importlib.util.spec_from_file_location(name, path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            return module
        
        EmbeddingManager = load_module("embedding_manager", current_dir / "embedding_manager.py").EmbeddingManager
        CodeVectorStore = load_module("vector_store", current_dir / "vector_store.py").CodeVectorStore
        CodeIndexer = load_module("indexer", current_dir / "indexer.py").CodeIndexer
    
    # Check if semantic index exists
    # First check MCP_WORKING_DIR (where Claude Code was launched from)
    mcp_working_dir = os.environ.get('MCP_WORKING_DIR')
    if mcp_working_dir:
        index_path = Path(mcp_working_dir) / "chroma_db"
        logger.info(f"Checking for ChromaDB at MCP working directory: {index_path}")
    else:
        index_path = Path("./chroma_db")
        logger.info(f"No MCP_WORKING_DIR set, checking current directory: {index_path}")
    
    if index_path.exists():
        vector_store = CodeVectorStore(persist_directory=str(index_path))
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
    
    # Check for environment variable and configuration patterns - use semantic
    env_config_indicators = [
        r'\b(env|environ|environment)\s+(var|variable)',
        r'\b(config|configuration|setting)',
        r'\bos\.environ',
        r'\bgetenv\b',
        r'^[A-Z][A-Z_]+[A-Z]$',           # CONSTANT_NAME pattern
        r'\b(API_KEY|DATABASE_URL|SECRET|TOKEN|PASSWORD)\b',
    ]
    
    if any(re.search(pattern, query, re.IGNORECASE) for pattern in env_config_indicators):
        return "semantic"  # Semantic search works best for env vars
    
    # Check for import patterns - use semantic
    import_indicators = [
        r'\b(import|imports|importing|uses?|using)\s+\w+',
        r'\bfrom\s+\w+\s+import',
        r'\b(files?|modules?)\s+(that\s+)?(use|import|require)',
        r'\b(pandas|numpy|requests|flask|django)\b',  # Common libraries
    ]
    
    if any(re.search(pattern, query, re.IGNORECASE) for pattern in import_indicators):
        return "semantic"  # Semantic search works best for imports
    
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
    
    if not arguments:
        arguments = {}
    
    # Handle original search_code tool
    if name == "search_code":
        # Check if this is the new intelligent search (has 'query' param) or old search (has 'pattern' param)
        if 'query' in arguments:
            # New intelligent search
            return await handle_intelligent_search(
                query=arguments['query'],
                mode=arguments.get('mode', 'auto'),
                file_types=arguments.get('file_types'),
                paths=arguments.get('paths'),
                limit=arguments.get('limit', 50),
                case_sensitive=arguments.get('case_sensitive', False),
                include_symbols=arguments.get('include_symbols', False),
                similarity_threshold=arguments.get('similarity_threshold', 0.7),
                format=arguments.get('format', 'navigation')
            )
        elif 'pattern' in arguments:
            # Old search - convert pattern to query and use intelligent search
            pattern = arguments.get('pattern')
            if not pattern:
                raise ValueError("Missing pattern argument")
            
            # Convert old pattern-based search to intelligent search
            logger.info(f"🔄 CONVERTING pattern search to intelligent search: '{pattern}'")
            return await handle_intelligent_search(
                query=pattern,
                mode='auto',  # Let auto-detection handle it
                file_types=arguments.get('file_types'),
                paths=arguments.get('paths'),
                limit=arguments.get('limit', 50),
                case_sensitive=arguments.get('case_sensitive', False),
                include_symbols=arguments.get('include_symbols', False),
                similarity_threshold=arguments.get('similarity_threshold', 0.7),
                format=arguments.get('format', 'navigation')
            )
        else:
            raise ValueError("Missing query or pattern argument")
    
    # Handle new intelligent search tools
    elif name == "get_search_capabilities":
        return await handle_search_capabilities()
    
    elif name == "search_code_simple":
        query = arguments.get('query')
        if not query:
            raise ValueError("Missing query argument")
        return await handle_simple_search(query)
    
    else:
        raise ValueError(f"Unknown tool: {name}")
    
    # This should never be reached due to the routing above
    raise ValueError("Unexpected code path")


# Helper functions for intelligent search
async def handle_intelligent_search(
    query: str,
    mode: str = "auto",
    file_types: Optional[List[str]] = None,
    paths: Optional[List[str]] = None,
    limit: int = 50,
    case_sensitive: bool = False,
    include_symbols: bool = False,  # For compatibility with Claude Code
    similarity_threshold: float = 0.7,
    format: str = "navigation",
    **kwargs  # Catch any other unexpected parameters
) -> List[types.TextContent]:
    """
    Intelligent code search with automatic mode detection and fallback.
    """
    
    # Detect or validate mode
    if mode == "auto":
        detected_mode = detect_query_type(query)
        logger.info(f"🔍 AUTO-DETECTED → {detected_mode.upper()} search: '{query}'")
    else:
        detected_mode = mode
        logger.info(f"🔍 EXPLICIT → {detected_mode.upper()} search: '{query}'")
    
    # Check if semantic search is available
    if detected_mode == "semantic" and not semantic_available:
        logger.warning("🧠 SEMANTIC search requested but not available → falling back to REGEX")
        detected_mode = "regex"
    
    # Enhance query for the selected mode
    enhanced_query = enhance_query_for_mode(query, detected_mode)
    if enhanced_query != query:
        logger.info(f"Enhanced query: '{query}' → '{enhanced_query}'")
    
    # Execute search based on mode
    if detected_mode == "semantic":
        logger.info(f"🧠 EXECUTING semantic search with embeddings")
        result = await execute_semantic_search(enhanced_query, file_types, paths, limit, similarity_threshold)
    elif detected_mode == "symbol":
        logger.info(f"🎯 EXECUTING symbol search with Tree-sitter")
        result = await execute_symbol_search(enhanced_query, file_types, paths, limit)
    else:  # regex mode
        logger.info(f"⚡ EXECUTING regex search with ripgrep")
        result = await searcher.search(
            pattern=enhanced_query,
            file_types=file_types,
            paths=paths,
            limit=limit,
            case_sensitive=case_sensitive
        )
    
    # Add metadata about search execution
    result.update({
        "original_query": query,
        "enhanced_query": enhanced_query,
        "requested_mode": mode,
        "detected_mode": detected_mode,
        "search_mode": detected_mode,
        "fallback_used": False
    })
    
    # Format response
    if format == "raw":
        response_text = ""
        if result.get("matches"):
            for match in result["matches"]:
                response_text += f"{match['file']}:{match['line_number']}\n"
        else:
            response_text = "No matches found."
        return [types.TextContent(type="text", text=response_text)]
    
    # Navigation format 
    return await format_search_results(result, limit, format)


async def handle_search_capabilities() -> List[types.TextContent]:
    """Get detailed information about available search capabilities"""
    
    logger.info("📊 Search capabilities requested")
    
    # Check semantic search status
    semantic_status = {
        "available": semantic_available,
        "reason": "Index found" if semantic_available else "No index found - run build_semantic_index.py"
    }
    
    if semantic_available:
        try:
            stats = semantic_searcher['vector_store'].get_statistics()
            semantic_status.update({
                "symbols_indexed": stats.get('total_symbols', 0),
                "languages": list(stats.get('languages', {}).keys()),
                "index_size_mb": stats.get('index_size_mb', 0)
            })
        except Exception as e:
            semantic_status["error"] = str(e)
    
    capabilities = {
        "available_modes": {
            "regex": {
                "available": True,
                "description": "Fast exact pattern matching with ripgrep",
                "best_for": [
                    "Known exact patterns",
                    "Wildcards and regex expressions", 
                    "Case-sensitive searches",
                    "File name patterns"
                ],
                "examples": [
                    "handleError.*Exception",
                    "class.*User.*{",
                    "def.*validate.*:",
                    "*.py"
                ]
            },
            "symbol": {
                "available": True,
                "description": "Language-aware symbol search using Tree-sitter",
                "best_for": [
                    "Exact function/class names",
                    "Method names",
                    "Variable names",
                    "When you know the identifier"
                ],
                "examples": [
                    "DatabaseConnection",
                    "submitToQueue", 
                    "UserAuthService",
                    "validateInput"
                ]
            },
            "semantic": {
                "available": semantic_status["available"],
                "description": "Natural language search using embeddings",
                "best_for": [
                    "Conceptual searches",
                    "Finding related functionality",
                    "When you know what it does, not what it's called",
                    "Exploring unfamiliar codebase"
                ],
                "examples": [
                    "functions that handle user authentication",
                    "error handling for database connections",
                    "code that processes uploaded files",
                    "validation logic for user input"
                ],
                "status": semantic_status
            }
        },
        "auto_detection": {
            "enabled": True,
            "description": "Automatically chooses the best search mode",
            "fallback_chain": "Primary mode → fallback modes if no results"
        },
        "recommendations": {
            "unknown_exact_name": "Use semantic mode: 'functions that handle...'",
            "know_exact_name": "Use symbol mode: 'MyClassName'",
            "know_pattern": "Use regex mode: 'handle.*Error'",
            "exploring_codebase": "Use semantic mode with broad queries",
            "debugging_specific_issue": "Use regex mode with error patterns"
        }
    }
    
    import json
    response_text = f"# Search Capabilities\n\n```json\n{json.dumps(capabilities, indent=2)}\n```"
    return [types.TextContent(type="text", text=response_text)]


async def handle_simple_search(query: str) -> List[types.TextContent]:
    """Simple code search - auto-detects best mode and searches"""
    logger.info(f"🔍 Simple search requested: '{query}'")
    return await handle_intelligent_search(query, mode="auto")


# Helper functions for new search modes
async def execute_semantic_search(query: str, file_types: Optional[List[str]], paths: Optional[List[str]], limit: int, similarity_threshold: float) -> Dict:
    """Execute semantic search using embeddings"""
    try:
        # Create query embedding
        query_embedding = semantic_searcher['embedder'].embed_text(query)
        
        # Search vector store
        where_filter = {}
        if file_types:
            where_filter["language"] = {"$in": file_types}
        
        results = semantic_searcher['vector_store'].search(
            query_embedding=query_embedding,
            limit=limit,
            where=where_filter if where_filter else None
        )
        
        # Convert to standard format
        matches = []
        for result in results["results"]:
            if result["distance"] <= (1.0 - similarity_threshold):  # Convert similarity to distance
                matches.append({
                    "file": result["metadata"]["file"],
                    "line_number": result["metadata"]["line"],
                    "line": result["code"][:100] + "..." if len(result["code"]) > 100 else result["code"],
                    "similarity": 1.0 - result["distance"]
                })
        
        return {
            "success": True,
            "pattern": query,
            "total_matches": len(matches),
            "matches": matches,
            "truncated": False
        }
        
    except Exception as e:
        logger.error(f"Semantic search failed: {e}")
        return {
            "success": False,
            "error": str(e),
            "pattern": query,
            "total_matches": 0,
            "matches": []
        }


async def execute_symbol_search(query: str, file_types: Optional[List[str]], paths: Optional[List[str]], limit: int) -> Dict:
    """Execute symbol search using Tree-sitter"""
    # For now, use enhanced ripgrep search
    # This could be enhanced to use the Tree-sitter enhancer directly
    return await searcher.search(
        pattern=query,
        file_types=file_types,
        paths=paths,
        limit=limit,
        case_sensitive=False
    )


async def format_search_results(result: Dict, limit: int, format: str) -> List[types.TextContent]:
    """Format search results for display"""
    if format == "raw":
        response_text = ""
        if result.get("matches"):
            for match in result["matches"]:
                response_text += f"{match['file']}:{match['line_number']}\n"
        else:
            response_text = "No matches found."
        return [types.TextContent(type="text", text=response_text)]
    
    # Navigation format - reuse existing logic
    matches_by_file = {}
    for match in result.get("matches", []):
        file_path = match["file"]
        if file_path not in matches_by_file:
            matches_by_file[file_path] = []
        matches_by_file[file_path].append(match)
    
    # Build response with file-centric format
    response_text = f"## Search Results: '{result['pattern']}'\n\n"
    response_text += f"**Summary**: {result['total_matches']} matches in {len(matches_by_file)} files\n\n"
    
    # Add search mode info
    if "search_mode" in result:
        response_text += f"**Search mode**: {result['search_mode']}\n\n"
    
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
                
                # Add similarity for semantic search
                if "similarity" in match:
                    response_text += f"  Similarity: {match['similarity']:.2f}\n"
            
            response_text += "\n"
        
        if result.get("truncated"):
            response_text += f"*Note: Results truncated to {limit} matches*\n"
    else:
        response_text += "No matches found.\n"
    
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