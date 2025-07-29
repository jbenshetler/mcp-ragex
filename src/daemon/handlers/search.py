"""
Search handler for socket daemon - keeps modules loaded in memory.
"""
import asyncio
import io
import contextlib
import sys
import os
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger('search-handler')


class SearchHandler:
    """Handles search commands with pre-loaded modules"""
    
    def __init__(self, shared_modules: Dict[str, Any]):
        self.shared_modules = shared_modules
        self.search_client = None
        self.search_module = None
    
    async def handle(self, args: list) -> Dict[str, Any]:
        """Handle search command"""
        # Get project data dir from environment
        project_data_dir = os.environ.get('RAGEX_PROJECT_DATA_DIR')
        if not project_data_dir:
            project_name = os.environ.get('PROJECT_NAME', 'admin')
            project_data_dir = f'/data/projects/{project_name}'
        
        # Lazy load search module
        if not self.search_module:
            logger.info("Loading search module...")
            sys.path.insert(0, '/app')
            from src.cli import search as search_module
            self.search_module = search_module
            logger.info("Search module loaded")
        
        # Create search client if needed (or if project changed)
        if not self.search_client or self._project_changed(project_data_dir):
            logger.info(f"Creating search client for project: {project_data_dir}")
            self.search_client = self.search_module.SearchClient(index_dir=project_data_dir)
            self._last_project_dir = project_data_dir
        
        # Capture stdout and stderr
        stdout_buffer = io.StringIO()
        stderr_buffer = io.StringIO()
        
        try:
            # Parse arguments using the search module's parser
            parsed_args = self.search_module.parse_args(args)
            parsed_args.index_dir = project_data_dir
            
            # Redirect stdout/stderr and run search
            with contextlib.redirect_stdout(stdout_buffer), contextlib.redirect_stderr(stderr_buffer):
                # Use the existing search client
                old_client = self.search_module.SearchClient
                self.search_module.SearchClient = lambda **kwargs: self.search_client
                
                try:
                    returncode = await self.search_module.run_search(parsed_args)
                finally:
                    # Restore original SearchClient class
                    self.search_module.SearchClient = old_client
            
            return {
                'success': returncode == 0,
                'stdout': stdout_buffer.getvalue(),
                'stderr': stderr_buffer.getvalue(),
                'returncode': returncode
            }
            
        except SystemExit as e:
            return {
                'success': e.code == 0,
                'stdout': stdout_buffer.getvalue(),
                'stderr': stderr_buffer.getvalue(),
                'returncode': e.code or 0
            }
        except Exception as e:
            logger.error(f"Search error: {e}", exc_info=True)
            return {
                'success': False,
                'stdout': stdout_buffer.getvalue(),
                'stderr': stderr_buffer.getvalue() + f"\nError: {str(e)}",
                'returncode': 1
            }
    
    def _project_changed(self, project_dir: str) -> bool:
        """Check if the project directory has changed"""
        return not hasattr(self, '_last_project_dir') or self._last_project_dir != project_dir