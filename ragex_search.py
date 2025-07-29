#!/usr/bin/env python3
"""
Code search client with grep-like output.

Usage:
    ./search_client.py "search term"                    # Semantic search (default)
    ./search_client.py --symbol "functionName"          # Symbol search
    ./search_client.py --regex "pattern.*here"          # Regex search
    ./search_client.py -A 3 -B 3 "search term"         # Include 3 lines before/after
"""

import argparse
import asyncio
import sys
from pathlib import Path
import re
import logging
from typing import List, Dict

# Configure logging based on environment variable
import os
log_level = os.environ.get('RAGEX_LOG_LEVEL', 'WARN').upper()
logging.basicConfig(level=getattr(logging, log_level, logging.WARN), format='%(message)s')

# Suppress verbose logging from all components unless overridden
for logger_name in [
    "ragex-mcp", "pattern-matcher", "vector-store", "embedding-manager",
    "sentence_transformers", "code-indexer", "mcp-ragex", "src.ignore.manager",
    "ignore.manager", "embedding-config", "chromadb", "transformers", "torch"
]:
    logging.getLogger(logger_name).setLevel(getattr(logging, log_level, logging.WARN))

# Path setup handled by PYTHONPATH in Docker, no need to manipulate sys.path

from src.server import RipgrepSearcher
from src.tree_sitter_enhancer import TreeSitterEnhancer
from src.pattern_matcher import PatternMatcher


def container_to_host_path(path: str) -> str:
    """Convert container path to host path for display."""
    # Get the workspace path from environment (passed from host)
    workspace_host = os.environ.get('WORKSPACE_PATH', '')
    
    # If the path starts with /workspace, replace it with the host path
    if path.startswith('/workspace/'):
        relative_path = path[11:]  # Remove '/workspace/'
        if workspace_host:
            return os.path.join(workspace_host, relative_path)
        else:
            # Fallback to relative path
            return relative_path
    elif path == '/workspace':
        return workspace_host or '.'
    
    # Return as-is if not a workspace path
    return path

# Try to import semantic search components
try:
    from src.embedding_manager import EmbeddingManager
    from src.vector_store import CodeVectorStore
    semantic_available = True
except ImportError:
    semantic_available = False


class SearchClient:
    def __init__(self, index_dir=None):
        self.pattern_matcher = PatternMatcher()
        self.searcher = RipgrepSearcher(self.pattern_matcher)
        self.enhancer = TreeSitterEnhancer(self.pattern_matcher)
        
        # Initialize semantic search if available
        self.semantic_searcher = None
        if semantic_available:
            try:
                # Check if index exists
                if index_dir:
                    index_path = Path(index_dir) / "chroma_db"
                else:
                    index_path = Path("./chroma_db")
                    
                if index_path.exists():
                    self.vector_store = CodeVectorStore(persist_directory=str(index_path))
                    stats = self.vector_store.get_statistics()
                    if stats['total_symbols'] > 0:
                        self.embedder = EmbeddingManager()
                        self.semantic_searcher = {
                            'embedder': self.embedder,
                            'vector_store': self.vector_store
                        }
                        print(f"# Semantic search available ({stats['total_symbols']} symbols indexed)", file=sys.stderr)
                    else:
                        print("# Semantic index is empty. Run: uv run python scripts/build_semantic_index.py .", file=sys.stderr)
                else:
                    print("# No semantic index found. Run: uv run python scripts/build_semantic_index.py .", file=sys.stderr)
            except Exception as e:
                print(f"# Failed to initialize semantic search: {e}", file=sys.stderr)
    
    async def search_semantic(self, query: str, limit: int = 50, type_filter: str = None):
        """Perform semantic search"""
        if not self.semantic_searcher:
            print("# Error: Semantic search not available", file=sys.stderr)
            return []
        
        # Check if query requests specific type
        query_lower = query.lower()
        if 'function' in query_lower and not type_filter:
            type_filter = 'function'
        elif 'class' in query_lower and not type_filter:
            type_filter = 'class'
        elif 'method' in query_lower and not type_filter:
            type_filter = 'method'
        
        # Create query embedding
        query_embedding = self.semantic_searcher['embedder'].embed_text(query)
        
        # Build where filter if type specified
        where_filter = None
        if type_filter:
            where_filter = {"type": type_filter}
        
        # Search vector store
        results = self.semantic_searcher['vector_store'].search(
            query_embedding=query_embedding,
            limit=limit * 2,  # Get more to deduplicate
            where=where_filter
        )
        
        # Deduplicate results based on file:line:name
        seen = set()
        matches = []
        for result in results["results"]:
            # Create unique key
            key = f"{result['metadata']['file']}:{result['metadata']['line']}:{result['metadata']['name']}"
            if key not in seen:
                seen.add(key)
                matches.append({
                    'file': result["metadata"]["file"],
                    'line': result["metadata"]["line"],
                    'type': result["metadata"]["type"],
                    'name': result["metadata"]["name"],
                    'code': result["code"],
                    'similarity': 1.0 - result["distance"]
                })
                if len(matches) >= limit:
                    break
        
        return matches
    
    async def search_symbol(self, query: str, limit: int = 50):
        """Perform symbol search using ripgrep with symbol-friendly patterns"""
        # Search for the symbol as a whole word
        pattern = f"\\b{re.escape(query)}\\b"
        
        result = await self.searcher.search(
            pattern=pattern,
            limit=limit,
            case_sensitive=False
        )
        
        if result.get("success") and result.get("matches"):
            return result["matches"]
        return []
    
    async def search_regex(self, pattern: str, limit: int = 50):
        """Perform regex search using ripgrep"""
        result = await self.searcher.search(
            pattern=pattern,
            limit=limit,
            case_sensitive=True
        )
        
        if result.get("success") and result.get("matches"):
            return result["matches"]
        return []
    
    def read_file_lines(self, filepath: str, start_line: int, end_line: int):
        """Read specific lines from a file (1-based line numbers)"""
        try:
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
                # Convert to 0-based indexing
                start_idx = max(0, start_line - 1)
                end_idx = min(len(lines), end_line)
                return lines[start_idx:end_idx]
        except Exception:
            return []
    
    def format_output(self, matches, before_context=0, after_context=0, mode="regex", show_type=True):
        """Format matches in grep-like output"""
        for match in matches:
            file_path = container_to_host_path(match['file'])
            line_num = match['line']
            
            # For semantic search, show the symbol with context
            if mode == "semantic" and 'code' in match:
                # Get the symbol's code
                symbol_lines = match['code'].split('\n')
                
                # Show type and name for semantic results
                symbol_info = f"[{match.get('type', 'unknown')}] {match.get('name', 'unknown')}"
                
                # For context, read from the file
                if before_context > 0 or after_context > 0:
                    # Show context before the symbol
                    if before_context > 0:
                        start = max(1, line_num - before_context)
                        # Use original container path for reading
                        context_before = self.read_file_lines(match['file'], start, line_num - 1)
                        for i, line in enumerate(context_before, start=start):
                            print(f"{file_path}:{i}-{line.rstrip()}")
                    
                    # Show the symbol itself (potentially multi-line)
                    for i, line in enumerate(symbol_lines):
                        current_line = line_num + i
                        print(f"{file_path}:{current_line}:{line.rstrip()}")
                    
                    # Show context after the symbol
                    if after_context > 0:
                        # Calculate end line of symbol
                        symbol_end_line = line_num + len(symbol_lines) - 1
                        end = symbol_end_line + after_context
                        context_after = self.read_file_lines(match['file'], symbol_end_line + 1, end)
                        for i, line in enumerate(context_after, start=symbol_end_line + 1):
                            print(f"{file_path}:{i}+{line.rstrip()}")
                else:
                    # No context requested, just show the first line of the symbol
                    if symbol_lines:
                        line_content = symbol_lines[0].rstrip()
                        if show_type and mode == "semantic":
                            # Include type info in the output line
                            print(f"{file_path}:{line_num}:[{match.get('type', 'unknown')}] {line_content}")
                        else:
                            # Standard grep format
                            print(f"{file_path}:{line_num}:{line_content}")
            
            else:
                # For regex/symbol matches, show the matched line
                if 'line_content' in match:
                    # Ripgrep result with line content
                    print(f"{file_path}:{line_num}:{match['line_content'].rstrip()}")
                else:
                    # Read the line from file
                    lines = self.read_file_lines(match['file'], line_num, line_num)
                    if lines:
                        print(f"{file_path}:{line_num}:{lines[0].rstrip()}")
                
                # Show context if requested
                if before_context > 0 or after_context > 0:
                    # Show before context
                    if before_context > 0:
                        start = max(1, line_num - before_context)
                        context_before = self.read_file_lines(match['file'], start, line_num - 1)
                        for i, line in enumerate(context_before, start=start):
                            print(f"{file_path}:{i}-{line.rstrip()}")
                    
                    # Show after context
                    if after_context > 0:
                        end = line_num + after_context
                        context_after = self.read_file_lines(match['file'], line_num + 1, end)
                        for i, line in enumerate(context_after, start=line_num + 1):
                            print(f"{file_path}:{i}+{line.rstrip()}")
            
            # Add separator between matches when showing context
            if (before_context > 0 or after_context > 0) and match != matches[-1]:
                print("--")
    
    async def run_search(self, query: str, symbol_search: bool = False, regex_search: bool = False,
                        limit: int = 50, before_context: int = 0, after_context: int = 0,
                        brief: bool = False) -> List[Dict]:
        """
        Run a search with the specified parameters.
        
        Args:
            query: The search query
            symbol_search: Use symbol search mode
            regex_search: Use regex search mode
            limit: Maximum number of results
            before_context: Lines to show before matches
            after_context: Lines to show after matches
            brief: Use brief output format
            
        Returns:
            List of matches
        """
        # Determine search mode
        if symbol_search:
            mode = "symbol"
        elif regex_search:
            mode = "regex"
        else:
            mode = "semantic"
        
        print(f"# Searching for '{query}' using {mode} mode", file=sys.stderr)
        
        # Perform search
        matches = []
        if mode == "semantic":
            matches = await self.search_semantic(query, limit)
        elif mode == "symbol":
            matches = await self.search_symbol(query, limit)
        elif mode == "regex":
            matches = await self.search_regex(query, limit)
        
        if not matches:
            print(f"# No matches found", file=sys.stderr)
            return matches
        
        print(f"# Found {len(matches)} matches", file=sys.stderr)
        
        # Format and print results
        self.format_output(matches, before_context, after_context, mode, show_type=not brief)
        
        return matches


async def main():
    parser = argparse.ArgumentParser(description='Search codebase with grep-like output')
    parser.add_argument('query', help='Search query')
    parser.add_argument('--symbol', action='store_true', help='Symbol search mode (literal symbol names)')
    parser.add_argument('--regex', action='store_true', help='Regex search mode')
    parser.add_argument('-A', '--after-context', type=int, default=0, help='Lines after match')
    parser.add_argument('-B', '--before-context', type=int, default=0, help='Lines before match')
    parser.add_argument('--limit', type=int, default=50, help='Maximum results (default: 50)')
    parser.add_argument('--brief', action='store_true', help='Brief output without type annotations')
    parser.add_argument('--index-dir', type=str, help='Directory containing chroma_db index (default: current directory)')
    
    args = parser.parse_args()
    
    if args.index_dir:
        print(f"# Using index from: {args.index_dir}", file=sys.stderr)
    
    # Initialize client
    client = SearchClient(index_dir=args.index_dir)
    
    # Run search using the new method
    await client.run_search(
        query=args.query,
        symbol_search=args.symbol,
        regex_search=args.regex,
        limit=args.limit,
        before_context=args.before_context,
        after_context=args.after_context,
        brief=args.brief
    )


if __name__ == "__main__":
    asyncio.run(main())