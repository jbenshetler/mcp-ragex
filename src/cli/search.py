"""
Search CLI implementation - can be imported and executed directly.
"""
import argparse
import asyncio
import sys
import os
from pathlib import Path
from typing import List, Dict, Any, Optional

# Import from lib modules
from src.lib.ripgrep_searcher import RipgrepSearcher
from src.lib.pattern_matcher import PatternMatcher
from src.tree_sitter_enhancer import TreeSitterEnhancer

# Try to import semantic search components
try:
    from src.lib.embedding_manager import EmbeddingManager
    from src.lib.vector_store import CodeVectorStore
    semantic_available = True
except ImportError:
    semantic_available = False


class SearchClient:
    """Search client that can be kept in memory and reused"""
    
    def __init__(self, index_dir: Optional[str] = None):
        self.pattern_matcher = PatternMatcher()
        self.searcher = RipgrepSearcher(self.pattern_matcher)
        self.enhancer = TreeSitterEnhancer(self.pattern_matcher)
        
        # Initialize semantic search if available
        self.semantic_searcher = None
        if semantic_available and index_dir:
            try:
                index_path = Path(index_dir) / "chroma_db"
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
                        print("# Semantic index is empty. Run: ragex index .", file=sys.stderr)
                else:
                    print("# No semantic index found. Run: ragex index .", file=sys.stderr)
            except Exception as e:
                print(f"# Failed to initialize semantic search: {e}", file=sys.stderr)
    
    async def search_semantic(self, query: str, limit: int = 50) -> List[Dict]:
        """Perform semantic search"""
        if not self.semantic_searcher:
            return []
        
        # Create query embedding
        query_embedding = self.semantic_searcher['embedder'].embed_text(query)
        
        # Search vector store
        results = self.semantic_searcher['vector_store'].search(
            query_embedding=query_embedding,
            limit=limit * 2,  # Get more to deduplicate
        )
        
        # Process results
        matches = []
        seen = set()
        for result in results["results"]:
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
    
    async def search_symbol(self, query: str, limit: int = 50) -> List[Dict]:
        """Perform symbol search using ripgrep"""
        import re
        pattern = f"\\b{re.escape(query)}\\b"
        
        result = await self.searcher.search(
            pattern=pattern,
            limit=limit,
            case_sensitive=False
        )
        
        if result.get("success") and result.get("matches"):
            return result["matches"]
        return []
    
    async def search_regex(self, pattern: str, limit: int = 50) -> List[Dict]:
        """Perform regex search using ripgrep"""
        result = await self.searcher.search(
            pattern=pattern,
            limit=limit,
            case_sensitive=True
        )
        
        if result.get("success") and result.get("matches"):
            return result["matches"]
        return []
    
    def format_output(self, matches: List[Dict], mode: str = "semantic") -> None:
        """Format and print search results"""
        for match in matches:
            file_path = self._container_to_host_path(match['file'])
            line_num = match.get('line', match.get('line_number', 0))
            
            if mode == "semantic" and 'code' in match:
                # Show semantic result
                symbol_lines = match['code'].split('\n')
                if symbol_lines:
                    line_content = symbol_lines[0].rstrip()
                    print(f"{file_path}:{line_num}:[{match.get('type', 'unknown')}] {line_content}")
            else:
                # Show regex/symbol result
                if 'line' in match:
                    print(f"{file_path}:{line_num}:{match['line'].rstrip()}")
                elif 'line_content' in match:
                    print(f"{file_path}:{line_num}:{match['line_content'].rstrip()}")
    
    def _container_to_host_path(self, path: str) -> str:
        """Convert container path to host path for display"""
        workspace_host = os.environ.get('WORKSPACE_PATH', '')
        
        if path.startswith('/workspace/'):
            relative_path = path[11:]
            if workspace_host:
                return os.path.join(workspace_host, relative_path)
            else:
                return relative_path
        elif path == '/workspace':
            return workspace_host or '.'
        
        return path


async def run_search(args: argparse.Namespace) -> int:
    """Run search with parsed arguments"""
    # Initialize client
    client = SearchClient(index_dir=args.index_dir)
    
    # Determine search mode
    if args.symbol:
        mode = "symbol"
    elif args.regex:
        mode = "regex"
    else:
        mode = "semantic"
    
    print(f"# Searching for '{args.query}' using {mode} mode", file=sys.stderr)
    
    # Perform search
    matches = []
    if mode == "semantic":
        matches = await client.search_semantic(args.query, args.limit)
    elif mode == "symbol":
        matches = await client.search_symbol(args.query, args.limit)
    elif mode == "regex":
        matches = await client.search_regex(args.query, args.limit)
    
    if not matches:
        print(f"# No matches found", file=sys.stderr)
        return 0
    
    print(f"# Found {len(matches)} matches", file=sys.stderr)
    
    # Format and print results
    client.format_output(matches, mode)
    
    return 0


def parse_args(args: List[str]) -> argparse.Namespace:
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description='Search codebase')
    parser.add_argument('query', help='Search query')
    parser.add_argument('--symbol', action='store_true', help='Symbol search mode')
    parser.add_argument('--regex', action='store_true', help='Regex search mode')
    parser.add_argument('-A', '--after-context', type=int, default=0, help='Lines after match')
    parser.add_argument('-B', '--before-context', type=int, default=0, help='Lines before match')
    parser.add_argument('--limit', type=int, default=50, help='Maximum results')
    parser.add_argument('--brief', action='store_true', help='Brief output')
    parser.add_argument('--index-dir', type=str, help='Directory containing chroma_db index')
    
    return parser.parse_args(args)


async def main(args: List[str]) -> int:
    """Main entry point for search CLI"""
    parsed_args = parse_args(args)
    return await run_search(parsed_args)


if __name__ == "__main__":
    sys.exit(asyncio.run(main(sys.argv[1:])))