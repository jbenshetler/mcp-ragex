#!/usr/bin/env python3
"""
Semantic search implementation using ChromaDB embeddings.

Performs similarity-based search using vector embeddings of code symbols.
"""

import logging
from typing import Dict, Any, Optional, List
from pathlib import Path

try:
    from .searcher_base import SearcherBase
    from .embedding_manager import EmbeddingManager
    from .vector_store import CodeVectorStore
    from .project_utils import get_chroma_db_path
except ImportError:
    from searcher_base import SearcherBase
    from embedding_manager import EmbeddingManager
    from vector_store import CodeVectorStore
    from project_utils import get_chroma_db_path

logger = logging.getLogger("semantic-searcher")


class SemanticSearcher(SearcherBase):
    """Semantic search using ChromaDB embeddings (similarity search)"""
    
    def __init__(self, project_info: dict, workspace_path: str):
        super().__init__(project_info, workspace_path)
        
        # Initialize embedding and vector store components
        chroma_path = get_chroma_db_path(self.project_data_dir)
        
        try:
            self.embedder = EmbeddingManager()
            self.vector_store = CodeVectorStore(persist_directory=str(chroma_path))
            
            # Verify ChromaDB has data
            stats = self.vector_store.get_statistics()
            self.total_symbols = stats.get('total_symbols', 0)
            
            if self.total_symbols > 0:
                logger.info(f"✓ SemanticSearcher initialized with {self.total_symbols} symbols")
            else:
                logger.warning("⚠ SemanticSearcher initialized but ChromaDB appears empty")
                
        except Exception as e:
            logger.error(f"Failed to initialize SemanticSearcher: {e}")
            raise
    
    async def search(self, query: str, limit: int = 50, file_types: Optional[List[str]] = None, 
                    similarity_threshold: float = 0.25, **kwargs) -> Dict[str, Any]:
        """Execute semantic search using embeddings
        
        Args:
            query: Search query string
            limit: Maximum number of results to return
            file_types: Optional list of file types to filter by (e.g., ['python'])
            similarity_threshold: Minimum similarity score for results
            **kwargs: Additional parameters (ignored)
            
        Returns:
            Dictionary with search results
        """
        self.log_search_start(query, limit=limit, file_types=file_types, threshold=similarity_threshold)
        
        try:
            # Create query embedding
            logger.info(f"Creating embedding for query: '{query}'")
            query_embedding = self.embedder.embed_text(query)
            logger.debug(f"Query embedding shape: {query_embedding.shape}")
            
            # Build metadata filter (follow CLI model - only pass where if needed)
            search_kwargs = {
                "query_embedding": query_embedding,
                "limit": limit
            }
            
            if file_types:
                where_filter = {"language": {"$in": file_types}}
                search_kwargs["where"] = where_filter
                logger.info(f"Filtering by file types: {file_types}")
            
            # Execute search (like CLI - no where parameter if no filters)
            search_results = self.vector_store.search(**search_kwargs)
            
            # Format results for standardized output
            formatted_matches = []
            for result in search_results.get('results', []):
                metadata = result.get('metadata', {})
                
                match = {
                    'file': metadata.get('file', ''),
                    'line_number': metadata.get('line', 0),
                    'line': result.get('code', '').strip(),
                    'similarity': 1.0 - result.get('distance', 1.0),  # Convert distance to similarity
                    'type': metadata.get('type', 'unknown'),
                    'name': metadata.get('name', ''),
                    'code': result.get('code', ''),
                    'docstring': metadata.get('docstring', ''),
                    'signature': metadata.get('signature', ''),
                }
                
                # Apply similarity threshold
                if match['similarity'] >= similarity_threshold:
                    formatted_matches.append(match)
            
            # Create standardized result
            result = {
                "success": True,
                "pattern": query,
                "total_matches": len(formatted_matches),
                "matches": formatted_matches,
                "truncated": len(search_results.get('results', [])) >= limit,
                "search_type": "semantic",
                "total_symbols_searched": self.total_symbols
            }
            
            self.log_search_result(result)
            return result
            
        except Exception as e:
            error_msg = f"Semantic search failed: {e}"
            logger.error(error_msg)
            
            result = {
                "success": False,
                "error": error_msg,
                "pattern": query,
                "total_matches": 0,
                "matches": [],
                "search_type": "semantic"
            }
            
            self.log_search_result(result)
            return result
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get statistics about the semantic search index
        
        Returns:
            Dictionary with index statistics
        """
        try:
            stats = self.vector_store.get_statistics()
            context = self.get_project_context()
            
            return {
                **stats,
                **context,
                'searcher_ready': self.total_symbols > 0
            }
        except Exception as e:
            logger.error(f"Failed to get semantic search statistics: {e}")
            return {
                'error': str(e),
                'searcher_ready': False
            }