#!/usr/bin/env python3
"""
Base class for all search implementations in MCP-RAGex.

Provides common project context management and interface standardization
for semantic, symbol, and regex search implementations.
"""

import os
import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from pathlib import Path

logger = logging.getLogger("searcher-base")


class SearcherBase(ABC):
    """Base class for all search implementations"""
    
    def __init__(self, project_info: dict, workspace_path: str):
        """Initialize searcher with project context
        
        Args:
            project_info: Project information dictionary containing project_id, project_data_dir, etc.
            workspace_path: Path to workspace directory (e.g., '/workspace' in container)
        """
        self.project_info = project_info
        self.workspace_path = workspace_path
        self.project_id = project_info['project_id']
        self.project_data_dir = project_info['project_data_dir']
        
        logger.info(f"Initialized {self.__class__.__name__} for project {self.project_id}")
        logger.info(f"  Workspace path: {self.workspace_path}")
        logger.info(f"  Project data dir: {self.project_data_dir}")
    
    @abstractmethod
    async def search(self, query: str, **kwargs) -> Dict[str, Any]:
        """Execute search with given query
        
        Args:
            query: Search query string
            **kwargs: Additional search parameters (limit, file_types, etc.)
            
        Returns:
            Dictionary with search results in standardized format:
            {
                "success": bool,
                "pattern": str,
                "total_matches": int,
                "matches": List[Dict],
                "truncated": bool,
                "error": Optional[str]
            }
        """
        raise NotImplementedError("Subclasses must implement search method")
    
    def get_project_context(self) -> dict:
        """Get common project context for logging and debugging
        
        Returns:
            Dictionary with project context information
        """
        return {
            'searcher_type': self.__class__.__name__,
            'project_id': self.project_id,
            'workspace_path': self.workspace_path,
            'data_dir': self.project_data_dir
        }
    
    def log_search_start(self, query: str, **kwargs):
        """Log search start with context"""
        context = self.get_project_context()
        logger.info(f"🔍 {context['searcher_type']} search started")
        logger.info(f"  Query: '{query}'")
        logger.info(f"  Project: {context['project_id']}")
        logger.info(f"  Workspace: {context['workspace_path']}")
        if kwargs:
            logger.info(f"  Parameters: {kwargs}")
    
    def log_search_result(self, result: Dict[str, Any]):
        """Log search results with context"""
        context = self.get_project_context()
        success = result.get('success', False)
        total_matches = result.get('total_matches', 0)
        
        if success:
            logger.info(f"✓ {context['searcher_type']} search completed: {total_matches} matches")
        else:
            error = result.get('error', 'Unknown error')
            logger.error(f"✗ {context['searcher_type']} search failed: {error}")
    
    def validate_workspace(self) -> bool:
        """Validate that workspace path exists and is accessible
        
        Returns:
            True if workspace is valid, False otherwise
        """
        workspace_path = Path(self.workspace_path)
        if not workspace_path.exists():
            logger.error(f"Workspace path does not exist: {self.workspace_path}")
            return False
        
        if not workspace_path.is_dir():
            logger.error(f"Workspace path is not a directory: {self.workspace_path}")
            return False
        
        # Try to list contents to verify access
        try:
            list(workspace_path.iterdir())
            logger.debug(f"Workspace path is accessible: {self.workspace_path}")
            return True
        except PermissionError:
            logger.error(f"No permission to access workspace path: {self.workspace_path}")
            return False
        except Exception as e:
            logger.error(f"Error accessing workspace path {self.workspace_path}: {e}")
            return False