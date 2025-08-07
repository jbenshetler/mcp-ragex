#!/usr/bin/env python3
"""
Regex search implementation using ripgrep with proper workspace context.

Performs filesystem-based regex pattern matching with correct working directory
and path context for containerized environments.
"""

import os
import logging
from typing import Dict, Any, Optional, List
from pathlib import Path

try:
    from .searcher_base import SearcherBase
    from .ripgrep_searcher import RipgrepSearcher
except ImportError:
    from searcher_base import SearcherBase
    from ripgrep_searcher import RipgrepSearcher

logger = logging.getLogger("regex-searcher")


class RegexSearcher(SearcherBase):
    """Regex search using ripgrep with proper workspace context"""
    
    def __init__(self, project_info: dict, workspace_path: str):
        super().__init__(project_info, workspace_path)
        
        # Initialize ripgrep searcher
        try:
            self.ripgrep = RipgrepSearcher()
            logger.info("✓ RegexSearcher initialized with RipgrepSearcher")
            
            # Validate workspace is accessible
            if not self.validate_workspace():
                logger.warning("⚠ Workspace validation failed - searches may not work correctly")
            
        except Exception as e:
            logger.error(f"Failed to initialize RegexSearcher: {e}")
            raise
    
    async def search(self, query: str, limit: int = 50, paths: Optional[List[str]] = None,
                    file_types: Optional[List[str]] = None, case_sensitive: bool = True, 
                    **kwargs) -> Dict[str, Any]:
        """Execute regex search using ripgrep with correct workspace context
        
        Args:
            query: Regex pattern to search for
            limit: Maximum number of results to return
            paths: Optional list of specific paths to search (relative to workspace)
            file_types: Optional list of file types to include
            case_sensitive: Whether search is case-sensitive
            **kwargs: Additional ripgrep parameters
            
        Returns:
            Dictionary with search results
        """
        self.log_search_start(query, limit=limit, paths=paths, file_types=file_types, 
                             case_sensitive=case_sensitive)
        
        # Save original working directory
        original_cwd = os.getcwd()
        directory_changed = False
        
        try:
            # Change to workspace directory
            os.chdir(self.workspace_path)
            directory_changed = True
            logger.info(f"🔧 Changed working directory: {original_cwd} → {self.workspace_path}")
            
            # Prepare search paths
            if paths:
                # Convert provided paths to Path objects, making them relative to workspace
                search_paths = []
                for path_str in paths:
                    path = Path(path_str)
                    # If absolute path, make it relative to workspace
                    if path.is_absolute():
                        try:
                            # Try to make it relative to workspace
                            rel_path = path.relative_to(Path(self.workspace_path))
                            search_paths.append(rel_path)
                        except ValueError:
                            # Path is outside workspace, use as-is but log warning
                            logger.warning(f"Path outside workspace: {path}")
                            search_paths.append(path)
                    else:
                        # Relative path, use as-is
                        search_paths.append(path)
            else:
                # Default to searching current directory (workspace)
                search_paths = [Path('.')]
            
            logger.info(f"🔍 Searching in paths: {[str(p) for p in search_paths]}")
            
            # Verify search paths exist
            valid_paths = []
            for path in search_paths:
                abs_path = Path(self.workspace_path) / path
                if abs_path.exists():
                    valid_paths.append(path)
                    logger.debug(f"✓ Path exists: {path}")
                else:
                    logger.warning(f"⚠ Path does not exist: {path} (absolute: {abs_path})")
            
            if not valid_paths:
                logger.error("No valid search paths found")
                return self._create_error_result(query, "No valid search paths found")
            
            # Execute ripgrep search
            result = await self.ripgrep.search(
                pattern=query,
                paths=valid_paths,
                file_types=file_types,
                limit=limit,
                case_sensitive=case_sensitive,
                **kwargs
            )
            
            # Add search type metadata
            result.update({
                "search_type": "regex",
                "workspace_path": self.workspace_path,
                "searched_paths": [str(p) for p in valid_paths]
            })
            
            # Convert relative file paths back to container paths for consistency
            if result.get('success') and result.get('matches'):
                for match in result['matches']:
                    file_path = match.get('file', '')
                    if file_path and not os.path.isabs(file_path):
                        # Convert relative path to absolute container path
                        abs_path = os.path.join(self.workspace_path, file_path)
                        match['file'] = abs_path
            
            logger.info(f"🔍 Ripgrep found {result.get('total_matches', 0)} matches in {self.workspace_path}")
            self.log_search_result(result)
            return result
            
        except Exception as e:
            error_msg = f"Regex search failed: {e}"
            logger.error(error_msg)
            logger.exception("Full traceback:")
            
            result = self._create_error_result(query, error_msg)
            self.log_search_result(result)
            return result
            
        finally:
            # CRITICAL: Always restore original working directory
            if directory_changed:
                try:
                    os.chdir(original_cwd)
                    logger.info(f"🔧 Restored working directory: {self.workspace_path} → {original_cwd}")
                except Exception as restore_error:
                    logger.critical(f"CRITICAL: Failed to restore working directory to {original_cwd}: {restore_error}")
                    logger.critical(f"Current working directory is now: {os.getcwd()}")
                    # This is a serious issue that could affect other operations
                    # Log extensively for debugging
                    logger.critical("This could cause issues with subsequent operations!")
    
    def _create_error_result(self, query: str, error_msg: str) -> Dict[str, Any]:
        """Create standardized error result"""
        return {
            "success": False,
            "error": error_msg,
            "pattern": query,
            "total_matches": 0,
            "matches": [],
            "search_type": "regex",
            "workspace_path": self.workspace_path
        }
    
    def validate_workspace_files(self) -> Dict[str, Any]:
        """Validate workspace has searchable files
        
        Returns:
            Dictionary with validation results and file statistics
        """
        try:
            workspace_path = Path(self.workspace_path)
            
            if not workspace_path.exists():
                return {
                    'valid': False,
                    'error': f'Workspace does not exist: {workspace_path}'
                }
            
            # Count files by type
            file_stats = {}
            total_files = 0
            
            for file_path in workspace_path.rglob('*'):
                if file_path.is_file():
                    total_files += 1
                    suffix = file_path.suffix.lower()
                    file_stats[suffix] = file_stats.get(suffix, 0) + 1
            
            return {
                'valid': total_files > 0,
                'total_files': total_files,
                'file_types': file_stats,
                'workspace_path': str(workspace_path)
            }
            
        except Exception as e:
            return {
                'valid': False,
                'error': f'Error validating workspace: {e}'
            }
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get statistics about the regex search capabilities
        
        Returns:
            Dictionary with regex searcher statistics
        """
        try:
            context = self.get_project_context()
            workspace_stats = self.validate_workspace_files()
            
            return {
                **context,
                **workspace_stats,
                'searcher_ready': workspace_stats.get('valid', False),
                'ripgrep_available': self.ripgrep is not None
            }
            
        except Exception as e:
            logger.error(f"Failed to get regex search statistics: {e}")
            return {
                'error': str(e),
                'searcher_ready': False
            }