#!/usr/bin/env python3
"""Handler for ls (list projects) command"""

import fnmatch
import logging
import os
import shutil
import sys
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

from src.ragex_core.project_utils import get_project_info, load_project_metadata

logger = logging.getLogger(__name__)


class LsHandler:
    """Handles ls commands with column formatting and glob filtering"""
    
    def __init__(self, shared_modules: Dict[str, Any]):
        self.shared_modules = shared_modules
        self.data_dir = Path('/data/projects')
        self.user_id = os.getuid()
    
    async def handle(self, args: list) -> Dict[str, Any]:
        """Handle ls command"""
        try:
            # Parse arguments
            pattern = None
            long_format = False
            
            for arg in args:
                if arg == '-l' or arg == '--long':
                    long_format = True
                elif not arg.startswith('-'):
                    pattern = arg
            
            # Get all projects for current user
            projects = self._get_user_projects(pattern)
            
            if not projects:
                # Return exit code 2 when no matches found
                return {
                    'success': False,
                    'stdout': '',
                    'stderr': '',
                    'returncode': 2
                }
            
            # Format output
            if long_format:
                output = self._format_long_output(projects)
            else:
                output = self._format_basic_output(projects)
            
            return {
                'success': True,
                'stdout': output,
                'stderr': '',
                'returncode': 0
            }
            
        except Exception as e:
            logger.error(f"List projects error: {e}", exc_info=True)
            return {
                'success': False,
                'stdout': '',
                'stderr': str(e),
                'returncode': 1
            }
    
    def _get_user_projects(self, pattern: Optional[str] = None) -> List[Tuple[str, str, Path]]:
        """Get projects for current user with optional pattern filtering
        
        Returns list of (project_name, project_id, project_path) tuples
        """
        projects = []
        
        if not self.data_dir.exists():
            return projects
        
        # Look for projects matching ragex_{uid}_*
        user_prefix = f"ragex_{self.user_id}_"
        
        for project_dir in self.data_dir.iterdir():
            if not project_dir.is_dir():
                continue
                
            project_id = project_dir.name
            if not project_id.startswith(user_prefix):
                continue
            
            # Get project metadata using centralized function
            project_info = get_project_info(project_id, self.data_dir.parent)
            if project_info:
                project_name, workspace_path = project_info
                
                # Apply pattern filter if provided
                if pattern and not fnmatch.fnmatch(project_name, pattern):
                    continue
                
                projects.append((project_name, project_id, workspace_path))
            else:
                # Log warning for projects without metadata
                logger.warning(f"Project {project_id} has no metadata (no project_info.json or workspace_path.txt)")
        
        # Sort by project name
        projects.sort(key=lambda x: x[0])
        return projects
    
    def _format_basic_output(self, projects: List[Tuple[str, str, Path]]) -> str:
        """Format basic output with PROJECT NAME, PROJECT ID, and PATH columns"""
        if not projects:
            return ""
        
        # Calculate column widths
        name_width = max(len(p[0]) for p in projects)
        name_width = max(name_width, 20)  # Minimum 20 chars
        id_width = 30  # Fixed width for project IDs
        
        # Get terminal width
        terminal_width = shutil.get_terminal_size((80, 20)).columns
        path_width = terminal_width - name_width - id_width - 6  # Account for spacing
        
        # Build output
        lines = []
        
        # Header
        header = f"{'PROJECT NAME':<{name_width}}  {'PROJECT ID':<{id_width}}  PATH"
        lines.append(header)
        lines.append("-" * min(terminal_width, len(header) + 20))
        
        # Projects
        for name, project_id, path in projects:
            path_str = str(path)
            # Truncate path if needed
            if len(path_str) > path_width and path_width > 10:
                path_str = "..." + path_str[-(path_width-3):]
            
            line = f"{name:<{name_width}}  {project_id:<{id_width}}  {path_str}"
            lines.append(line)
        
        return "\n".join(lines) + "\n"
    
    def _format_long_output(self, projects: List[Tuple[str, str, Path]]) -> str:
        """Format long output with additional MODEL and INDEXED columns"""
        if not projects:
            return ""
        
        # Gather additional info for each project
        extended_projects = []
        for name, project_id, path in projects:
            model = self._get_project_model(project_id)
            indexed = self._is_project_indexed(project_id)
            extended_projects.append((name, project_id, model, indexed, path))
        
        # Calculate column widths
        name_width = max(len(p[0]) for p in extended_projects)
        name_width = max(name_width, 20)  # Minimum 20 chars
        id_width = 30  # Fixed width for project IDs
        model_width = 10
        indexed_width = 8
        
        # Get terminal width
        terminal_width = shutil.get_terminal_size((120, 20)).columns
        path_width = terminal_width - name_width - id_width - model_width - indexed_width - 10
        
        # Build output
        lines = []
        
        # Header
        header = f"{'PROJECT NAME':<{name_width}}  {'PROJECT ID':<{id_width}}  {'MODEL':<{model_width}}  {'INDEXED':<{indexed_width}}  PATH"
        lines.append(header)
        lines.append("-" * min(terminal_width, len(header) + 20))
        
        # Projects
        for name, project_id, model, indexed, path in extended_projects:
            path_str = str(path)
            # Truncate path if needed
            if len(path_str) > path_width and path_width > 10:
                path_str = "..." + path_str[-(path_width-3):]
            
            indexed_str = "yes" if indexed else "no"
            line = f"{name:<{name_width}}  {project_id:<{id_width}}  {model:<{model_width}}  {indexed_str:<{indexed_width}}  {path_str}"
            lines.append(line)
        
        return "\n".join(lines) + "\n"
    
    def _get_project_model(self, project_id: str) -> str:
        """Get the embedding model used for a project"""
        # Use centralized metadata loading
        metadata = load_project_metadata(project_id, self.data_dir.parent)
        if metadata:
            return metadata.get('embedding_model', 'fast')
        
        # Check for model info in old format
        model_file = self.data_dir / project_id / 'embedding_model.txt'
        if model_file.exists():
            try:
                return model_file.read_text().strip()
            except Exception as e:
                logger.warning(f"Failed to read embedding_model.txt for {project_id}: {e}")
        
        # Default to 'fast' if not specified
        return "fast"
    
    def _is_project_indexed(self, project_id: str) -> bool:
        """Check if project has a ChromaDB index"""
        chroma_path = self.data_dir / project_id / 'chroma_db'
        if not chroma_path.exists():
            return False
        
        # Check if it contains actual data
        sqlite_db = chroma_path / 'chroma.sqlite3'
        return sqlite_db.exists() and sqlite_db.stat().st_size > 0