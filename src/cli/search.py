"""
Search CLI implementation - can be imported and executed directly.
"""
import argparse
import asyncio
import sys
import os
import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional

# Import from lib modules
from src.ragex_core.ripgrep_searcher import RipgrepSearcher
from src.ragex_core.pattern_matcher import PatternMatcher
from src.tree_sitter_enhancer import TreeSitterEnhancer
from src.ragex_core.path_mapping import container_to_host_path, PathMappingError
from src.ragex_core.project_utils import get_chroma_db_path
from src.ragex_core.project_detection import detect_project_from_cwd
from src.ragex_core.reranker import FeatureReranker
from src.utils import get_logger

# Try to import semantic search components
try:
    from src.ragex_core.embedding_manager import EmbeddingManager
    from src.ragex_core.vector_store import CodeVectorStore
    semantic_available = True
except ImportError:
    semantic_available = False

# Get logger for this module
logger = get_logger("cli-search")


class SearchClient:
    """Search client that can be kept in memory and reused"""
    
    def __init__(self, index_dir: Optional[str] = None, json_output: bool = False):
        self.pattern_matcher = PatternMatcher()
        # Always use /workspace in container (where code is mounted)
        self.pattern_matcher.set_working_directory('/workspace')
        
        # Create searcher without pattern matcher - ripgrep will handle .rgignore files natively
        self.searcher = RipgrepSearcher(None)
        self.enhancer = TreeSitterEnhancer(self.pattern_matcher)
        self.reranker = FeatureReranker()
        self.json_output = json_output
        self.initialization_messages = []
        
        # Auto-detect project if no index_dir provided
        if not index_dir:
            project_info = detect_project_from_cwd()
            if project_info:
                index_dir = project_info['project_data_dir']
                msg = f"Detected project: {project_info['project_name']}"
                logger.info(msg)
                if not json_output:
                    print(f"# {msg}", file=sys.stderr)
                self.initialization_messages.append(msg)
            else:
                msg = "No indexed project found. Run 'ragex index .' first."
                logger.warning(msg)
                if not json_output:
                    print(f"# {msg}", file=sys.stderr)
                self.initialization_messages.append(msg)
        
        # Initialize semantic search if available
        self.semantic_searcher = None
        if semantic_available and index_dir:
            try:
                index_path = get_chroma_db_path(index_dir)
                if index_path.exists():
                    self.vector_store = CodeVectorStore(persist_directory=str(index_path))
                    stats = self.vector_store.get_statistics()
                    if stats['total_symbols'] > 0:
                        self.embedder = EmbeddingManager()
                        self.semantic_searcher = {
                            'embedder': self.embedder,
                            'vector_store': self.vector_store
                        }
                        msg = f"Semantic search available ({stats['total_symbols']} symbols indexed)"
                        logger.info(msg)
                        if not json_output:
                            print(f"# {msg}", file=sys.stderr)
                        self.initialization_messages.append({"level": "info", "message": msg})
                    else:
                        msg = "Semantic index is empty. Run: ragex index ."
                        logger.error(msg)
                        if not json_output:
                            print(f"# {msg}", file=sys.stderr)
                        self.initialization_messages.append({"level": "error", "message": msg})
                else:
                    msg = "No semantic index found. Run: ragex index ."
                    logger.error(msg)
                    if not json_output:
                        print(f"# {msg}", file=sys.stderr)
                    self.initialization_messages.append({"level": "error", "message": msg})
            except Exception as e:
                msg = f"Failed to initialize semantic search: {e}"
                logger.error(msg)
                if not json_output:
                    print(f"# {msg}", file=sys.stderr)
                self.initialization_messages.append({"level": "error", "message": msg})
    
    async def search_semantic(self, query: str, limit: int = 50, min_similarity: float = 0.0) -> List[Dict]:
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
                    'similarity': 1.0 - result["distance"],
                    'docstring': result["metadata"].get("docstring", ""),
                    'signature': result["metadata"].get("signature", "")
                })
                if len(matches) >= limit * 2:  # Get more for reranking
                    break
        
        # Filter by minimum similarity if specified
        if min_similarity > 0.0:
            original_count = len(matches)
            matches = [m for m in matches if m.get('similarity', 0.0) >= min_similarity]
            logger.info(f"Similarity filter ({min_similarity}): {original_count} -> {len(matches)} matches")
        
        # Apply feature-based reranking
        if matches:
            logger.info(f"Before reranking: {len(matches)} matches, top 3: {[(m['name'], m['similarity']) for m in matches[:3]]}")
            matches = self.reranker.rerank(query, matches, top_k=limit)
            logger.info(f"After reranking: {len(matches)} matches, top 3: {[(m['name'], m.get('reranked_score', 0)) for m in matches[:3]]}")
        
        return matches
    
    async def search_regex(self, pattern: str, limit: int = 50) -> List[Dict]:
        """Perform regex search using ripgrep"""
        # Always use /workspace in container
        workspace_path = Path('/workspace')
        result = await self.searcher.search(
            pattern=pattern,
            paths=[workspace_path],
            limit=limit,
            case_sensitive=True
        )
        
        # Debug logging
        logger.debug(f"Regex search result: success={result.get('success')}, matches={len(result.get('matches', []))}")
        
        if result.get("success") and result.get("matches"):
            return result["matches"]
        return []
    
    def format_output(self, matches: List[Dict], mode: str = "semantic") -> None:
        """Format and print search results"""
        for match in matches:
            file_path = self._container_to_host_path(match['file'])
            line_num = match.get('line', match.get('line_number', 0))
            
            if mode == "semantic" and 'code' in match:
                # Show semantic result with similarity score
                symbol_lines = match['code'].split('\n')
                if symbol_lines:
                    line_content = symbol_lines[0].rstrip()
                    similarity = match.get('similarity', 0.0)
                    print(f"{file_path}:{line_num}:[{match.get('type', 'unknown')}] ({similarity:.3f}) {line_content}")
            else:
                # Show regex/symbol result (no similarity score)
                if 'line' in match:
                    print(f"{file_path}:{line_num}:{match['line'].rstrip()}")
                elif 'line_content' in match:
                    print(f"{file_path}:{line_num}:{match['line_content'].rstrip()}")
    
    def _container_to_host_path(self, path: str) -> str:
        """Convert container path to host path for display"""
        return container_to_host_path(path)


async def run_search(args: argparse.Namespace, search_client: Optional[SearchClient] = None) -> int:
    """Run search with parsed arguments
    
    Args:
        args: Parsed command line arguments
        search_client: Optional pre-initialized SearchClient to use
    """
    # Initialize client if not provided
    json_output = getattr(args, 'json', False)
    if search_client is None:
        client = SearchClient(index_dir=args.index_dir, json_output=json_output)
    else:
        client = search_client
    
    # Determine search mode
    if args.regex:
        mode = "regex"
    else:
        mode = "semantic"
    
    if not json_output:
        print(f"# Searching for '{args.query}' using {mode} mode", file=sys.stderr)
    
    # Perform search
    matches = []
    try:
        if mode == "semantic":
            min_similarity = getattr(args, 'min_similarity', 0.0)
            matches = await client.search_semantic(args.query, args.limit, min_similarity)
        elif mode == "regex":
            matches = await client.search_regex(args.query, args.limit)
    except PathMappingError as e:
        # Fatal error - can't continue
        if json_output:
            result = {
                "success": False,
                "error": str(e),
                "query": args.query,
                "mode": mode,
                "total_matches": 0,
                "matches": [],
                "messages": client.initialization_messages
            }
            print(json.dumps(result, indent=2))
        else:
            print(f"# FATAL ERROR: {e}", file=sys.stderr)
        return 1
    
    if json_output:
        # Output MCP-compatible JSON
        result = {
            "success": True,
            "query": args.query,
            "mode": mode,
            "total_matches": len(matches),
            "matches": matches,
            "messages": client.initialization_messages
        }
        print(json.dumps(result, indent=2))
    else:
        # Human-readable output
        if not matches:
            print(f"# No matches found", file=sys.stderr)
            return 0
        
        print(f"# Found {len(matches)} matches", file=sys.stderr)
        
        # Format and print results
        try:
            client.format_output(matches, mode)
        except PathMappingError as e:
            print(f"# FATAL ERROR: {e}", file=sys.stderr)
            return 1
    
    return 0


def parse_args(args: List[str]) -> argparse.Namespace:
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description='Search codebase')
    parser.add_argument('query', help='Search query')
    parser.add_argument('--regex', action='store_true', help='Regex search mode')
    parser.add_argument('-A', '--after-context', type=int, default=0, help='Lines after match')
    parser.add_argument('-B', '--before-context', type=int, default=0, help='Lines before match')
    parser.add_argument('--limit', type=int, default=50, help='Maximum results')
    parser.add_argument('--min-similarity', type=float, default=0.0, help='Minimum similarity score for semantic results (0.0-1.0)')
    parser.add_argument('--brief', action='store_true', help='Brief output')
    parser.add_argument('--index-dir', type=str, help='Directory containing chroma_db index')
    parser.add_argument('--json', action='store_true', help='Output MCP-compatible JSON format')
    
    return parser.parse_args(args)


async def main(args: List[str]) -> int:
    """Main entry point for search CLI"""
    parsed_args = parse_args(args)
    return await run_search(parsed_args)


if __name__ == "__main__":
    sys.exit(asyncio.run(main(sys.argv[1:])))