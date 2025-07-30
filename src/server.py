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

# Import Tree-sitter enhancer and utilities
try:
    from src.tree_sitter_enhancer import TreeSitterEnhancer
    from src.ragex_core.pattern_matcher import PatternMatcher
    from src.utils import configure_logging, get_logger
    from src.watchdog_monitor import WatchdogMonitor, WATCHDOG_AVAILABLE
except ImportError:
    from .tree_sitter_enhancer import TreeSitterEnhancer
    from .ragex_core.pattern_matcher import PatternMatcher
    from .utils import configure_logging, get_logger
    try:
        from .watchdog_monitor import WatchdogMonitor, WATCHDOG_AVAILABLE
    except ImportError:
        WATCHDOG_AVAILABLE = False
        WatchdogMonitor = None

# Configure logging based on environment
# Only configure logging if we're the main process, not when imported by socket daemon
if os.environ.get('RAGEX_DAEMON_INITIALIZED') != '1':
    configure_logging()

# Get logger for this module
logger = get_logger("ragex-mcp")

# Log startup info only if we're the main process
if os.environ.get('RAGEX_DAEMON_INITIALIZED') != '1':
    logger.info("="*50)
    logger.info("MCP RAGex Server Started")
    logger.info(f"Time: {datetime.now()}")
    logger.info(f"CWD: {os.getcwd()}")
    logger.info(f"MCP_WORKING_DIR: {os.environ.get('MCP_WORKING_DIR', 'Not set')}")
    logger.info(f"Python: {sys.executable}")
    logger.info(f"Arguments: {sys.argv}")
    logger.info("="*50)

# Import constants from ripgrep_searcher
from src.ragex_core.ripgrep_searcher import ALLOWED_FILE_TYPES, DEFAULT_RESULTS, MAX_RESULTS


# Initialize server
app = Server("ragex-mcp")

# Initialize shared pattern matcher
pattern_matcher = PatternMatcher()

# Initialize watchdog monitor if available and enabled
watchdog_monitor = None
if WATCHDOG_AVAILABLE and os.environ.get("RAGEX_ENABLE_WATCHDOG", "false").lower() in ("true", "1", "yes"):
    try:
        # Access the internal ignore manager from pattern matcher
        ignore_manager = pattern_matcher._ignore_manager
        watchdog_monitor = WatchdogMonitor(ignore_manager, debounce_seconds=1.0)
        
        def on_ignore_change(file_path: str):
            logger.info(f"Detected change to ignore file: {file_path}")
            # The ignore manager will automatically reload
            
        watchdog_monitor.start(on_change_callback=on_ignore_change)
        logger.info("Watchdog monitoring enabled for .mcpignore files")
        
        # Register cleanup
        def cleanup_watchdog():
            if watchdog_monitor and watchdog_monitor.is_running():
                logger.info("Stopping watchdog monitor...")
                watchdog_monitor.stop()
                
        atexit.register(cleanup_watchdog)
        
    except Exception as e:
        logger.warning(f"Failed to initialize watchdog monitor: {e}")
        watchdog_monitor = None
else:
    if not WATCHDOG_AVAILABLE:
        logger.debug("Watchdog package not installed - hot reload disabled")
    else:
        logger.debug("Watchdog monitoring disabled (set RAGEX_ENABLE_WATCHDOG=true to enable)")

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
    
    # Try importing the semantic search modules with absolute imports
    try:
        from src.embedding_manager import EmbeddingManager
        from src.vector_store import CodeVectorStore
        from src.indexer import CodeIndexer
    except ImportError:
        # Try relative imports as fallback
        from .embedding_manager import EmbeddingManager
        from .vector_store import CodeVectorStore
        from .indexer import CodeIndexer
        
        def load_module(name, path):
            spec = importlib.util.spec_from_file_location(name, path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            return module
        
        EmbeddingManager = load_module("embedding_manager", current_dir / "embedding_manager.py").EmbeddingManager
        CodeVectorStore = load_module("vector_store", current_dir / "vector_store.py").CodeVectorStore
        CodeIndexer = load_module("indexer", current_dir / "indexer.py").CodeIndexer
    
    # Check if semantic index exists
    # Try multiple locations for ChromaDB
    search_paths = []
    
    # 1. First check MCP_WORKING_DIR (where Claude Code was launched from)
    mcp_working_dir = os.environ.get('MCP_WORKING_DIR')
    if mcp_working_dir:
        search_paths.append(Path(mcp_working_dir) / "chroma_db")
        logger.info(f"MCP_WORKING_DIR set to: {mcp_working_dir}")
    
    # 2. Check current working directory
    cwd = Path.cwd()
    search_paths.append(cwd / "chroma_db")
    logger.info(f"Current working directory: {cwd}")
    
    # 3. Check RAGEX_CHROMA_PERSIST_DIR if set
    custom_dir = os.environ.get('RAGEX_CHROMA_PERSIST_DIR')
    if custom_dir:
        search_paths.append(Path(custom_dir))
        logger.info(f"RAGEX_CHROMA_PERSIST_DIR set to: {custom_dir}")
    
    # Log all search paths for debugging
    logger.info("ChromaDB search paths:")
    for i, path in enumerate(search_paths, 1):
        exists = "EXISTS" if path.exists() else "NOT FOUND"
        logger.info(f"  {i}. {path} [{exists}]")
    
    # Try each path
    index_path = None
    for path in search_paths:
        if path.exists():
            index_path = path
            logger.info(f"✓ Found ChromaDB at: {index_path}")
            break
    
    if index_path:
        try:
            vector_store = CodeVectorStore(persist_directory=str(index_path))
            stats = vector_store.get_statistics()
            logger.info(f"ChromaDB stats: {stats}")
            
            if stats['total_symbols'] > 0:
                embedder = EmbeddingManager()
                semantic_searcher = {
                    'embedder': embedder,
                    'vector_store': vector_store,
                    'indexer': CodeIndexer()
                }
                semantic_available = True
                logger.info(f"✓ Semantic search ENABLED with {stats['total_symbols']} symbols from {stats['unique_files']} files")
                logger.info(f"  Languages: {', '.join(stats.get('languages', {}).keys())}")
            else:
                logger.warning("✗ Semantic index exists but is EMPTY")
                logger.info("  Run: uv run python scripts/build_semantic_index.py . --stats")
        except Exception as e:
            logger.error(f"✗ Failed to load ChromaDB from {index_path}: {e}")
            logger.exception("Full traceback:")
    else:
        logger.warning("✗ Semantic search index NOT FOUND in any search path")
        logger.info("  To enable semantic search, run from project directory:")
        logger.info("  uv run python scripts/build_semantic_index.py . --stats")
        
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
                        "default": DEFAULT_RESULTS
                    },
                    "case_sensitive": {
                        "type": "boolean",
                        "description": "Whether search should be case sensitive (default: false)",
                        "default": False
                    },
                    "include_symbols": {
                        "type": "boolean",
                        "description": "Include symbol context (function/class info) in results (default: false)",
                        "default": False
                    },
                    "similarity_threshold": {
                        "type": "number",
                        "description": "Minimum similarity score for semantic search results (0.0-1.0, default: 0.25)",
                        "minimum": 0.0,
                        "maximum": 1.0,
                        "default": 0.25
                    },
                    "exclude_patterns": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Additional patterns to exclude (gitignore syntax)",
                    },
                    "respect_gitignore": {
                        "type": "boolean",
                        "description": "Whether to respect .gitignore files (default: true)",
                        "default": True
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
            name="get_search_capabilities",
            description="Get detailed information about available search modes and current capabilities",
            inputSchema={
                "type": "object",
                "properties": {},
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
        types.Tool(
            name="get_watchdog_status",
            description="Get the status of the watchdog file monitor for .mcpignore hot reloading",
            inputSchema={
                "type": "object",
                "properties": {},
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
                similarity_threshold=arguments.get('similarity_threshold', 0.25),
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
                similarity_threshold=arguments.get('similarity_threshold', 0.25),
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
    
    elif name == "get_watchdog_status":
        return await handle_watchdog_status()
    
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
    similarity_threshold: float = 0.25,
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


async def handle_watchdog_status() -> List[types.TextContent]:
    """Get watchdog monitor status"""
    
    logger.info("🔍 Watchdog status requested")
    
    status_lines = ["# Watchdog Monitor Status\n"]
    
    # Check if watchdog is available
    if not WATCHDOG_AVAILABLE:
        status_lines.append("❌ **Watchdog not available**: Package not installed")
        status_lines.append("   Install with: `pip install watchdog` or `uv pip install watchdog`")
        return [types.TextContent(type="text", text="\n".join(status_lines))]
    
    # Check if watchdog is enabled
    watchdog_enabled = os.environ.get("RAGEX_ENABLE_WATCHDOG", "false").lower() in ("true", "1", "yes")
    if not watchdog_enabled:
        status_lines.append("⚠️  **Watchdog disabled**: Not enabled via environment variable")
        status_lines.append("   Enable with: `export RAGEX_ENABLE_WATCHDOG=true`")
        return [types.TextContent(type="text", text="\n".join(status_lines))]
    
    # Check if monitor is running
    if watchdog_monitor and watchdog_monitor.is_running():
        status_lines.append("✅ **Watchdog active**: Monitoring for .mcpignore changes")
        status_lines.append(f"   Debounce period: {watchdog_monitor.debounce_seconds}s")
        
        # Get watched paths
        watched_paths = watchdog_monitor.get_watched_paths()
        status_lines.append(f"\n📁 **Watched directories** ({len(watched_paths)}):")
        for path in watched_paths:
            status_lines.append(f"   - {path}")
            
        # Get ignore files being monitored
        ignore_files = pattern_matcher._ignore_manager.get_ignore_files()
        status_lines.append(f"\n📄 **Active .mcpignore files** ({len(ignore_files)}):")
        for file in ignore_files:
            status_lines.append(f"   - {file}")
            
    else:
        status_lines.append("❌ **Watchdog not running**: Failed to initialize or stopped")
        
    # Add configuration info
    status_lines.append("\n## Configuration")
    status_lines.append(f"- Ignore filename: `{pattern_matcher._ignore_manager.ignore_filename}`")
    status_lines.append(f"- Root path: `{pattern_matcher._ignore_manager.root_path}`")
    status_lines.append(f"- Multi-level support: ✅ Enabled")
    status_lines.append(f"- Hot reload: {'✅ Active' if watchdog_monitor and watchdog_monitor.is_running() else '❌ Inactive'}")
    
    return [types.TextContent(type="text", text="\n".join(status_lines))]


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
    
    # Check if semantic search is available
    if not semantic_available or not semantic_searcher:
        error_msg = "Semantic search is not available. "
        error_msg += "ChromaDB index may not be found or dependencies missing. "
        error_msg += "Check /tmp/mcp_ragex.log for initialization details."
        logger.error(error_msg)
        return {
            "success": False,
            "error": error_msg,
            "pattern": query,
            "total_matches": 0,
            "matches": [],
            "semantic_unavailable": True
        }
    
    try:
        # Create query embedding
        logger.info(f"Creating embedding for query: '{query}'")
        query_embedding = semantic_searcher['embedder'].embed_text(query)
        logger.info(f"Query embedding shape: {query_embedding.shape}, first 5 values: {query_embedding[:5]}")
        
        # Search vector store
        where_filter = {}
        if file_types:
            where_filter["language"] = {"$in": file_types}
            logger.info(f"Filtering by file types: {file_types}")
        
        logger.info(f"Searching vector store with limit={limit}, where={where_filter}")
        results = semantic_searcher['vector_store'].search(
            query_embedding=query_embedding,
            limit=limit,
            where=where_filter if where_filter else None
        )
        logger.info(f"Raw search returned {len(results.get('results', []))} results")
        
        # Convert to standard format
        matches = []
        logger.info(f"Filtering results with similarity_threshold={similarity_threshold} (distance <= {1.0 - similarity_threshold})")
        for i, result in enumerate(results["results"]):
            distance = result["distance"]
            similarity = 1.0 - distance
            if i < 5:  # Log first 5 for debugging
                logger.info(f"  Result {i}: distance={distance:.4f}, similarity={similarity:.4f}, file={result['metadata']['file']}, name={result['metadata']['name']}")
            
            if distance <= (1.0 - similarity_threshold):  # Convert similarity to distance
                matches.append({
                    "file": result["metadata"]["file"],
                    "line_number": result["metadata"]["line"],
                    "line": result["code"][:100] + "..." if len(result["code"]) > 100 else result["code"],
                    "similarity": similarity
                })
        
        # Sort by similarity (highest first) to ensure best matches come first
        matches.sort(key=lambda x: x['similarity'], reverse=True)
        
        logger.info(f"Semantic search completed: found {len(matches)} matches for '{query}'")
        
        return {
            "success": True,
            "pattern": query,
            "total_matches": len(matches),
            "matches": matches,
            "truncated": False
        }
        
    except Exception as e:
        logger.error(f"Semantic search failed: {e}")
        logger.exception("Full traceback:")
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
        
        # Add debugging info if semantic search was attempted but failed
        if result.get("search_mode") == "semantic" and result.get("requested_mode") == "semantic":
            response_text += "\n**Debugging info**: Semantic search was attempted but may have failed.\n"
            response_text += "Check /tmp/mcp_ragex.log for details about ChromaDB initialization.\n"
        
        # Show error if semantic search was unavailable
        if result.get("semantic_unavailable"):
            response_text += "\n⚠️ **Semantic Search Unavailable**\n"
            response_text += "The ChromaDB index could not be found. Please ensure:\n"
            response_text += "1. You have built the index: `uv run python scripts/build_semantic_index.py . --stats`\n"
            response_text += "2. The index exists in one of these locations:\n"
            response_text += "   - Project directory: `./chroma_db`\n"
            response_text += "   - Or set RAGEX_CHROMA_PERSIST_DIR environment variable\n"
            response_text += "\nFalling back to regex search instead.\n"
    
    return [types.TextContent(type="text", text=response_text)]


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