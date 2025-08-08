#!/usr/bin/env python3
"""Handler for rm (remove project) command"""

import fnmatch
import os
import shutil
from pathlib import Path
from typing import Dict, Any, List

from src.ragex_core.project_utils import get_project_info
from src.utils import get_logger

logger = get_logger(__name__)


class RmHandler:
    """Handles rm commands with glob pattern support"""
    
    def __init__(self, shared_modules: Dict[str, Any]):
        self.shared_modules = shared_modules
        self.data_dir = Path('/data/projects')
        self.user_id = os.getuid()
    
    async def handle(self, args: list) -> Dict[str, Any]:
        """Handle rm command"""
        try:
            if not args:
                return {
                    'success': False,
                    'stdout': '',
                    'stderr': 'Error: Project ID or pattern required\n',
                    'returncode': 1
                }
            
            pattern = args[0]
            
            # Find matching projects
            matched_projects = self._find_matching_projects(pattern)
            
            if not matched_projects:
                # Return exit code 2 when no matches found
                return {
                    'success': False,
                    'stdout': '',
                    'stderr': '',
                    'returncode': 2
                }
            
            # Remove all matched projects
            removed_count = 0
            output_lines = []
            
            for project_name, project_id, project_path in matched_projects:
                project_dir = self.data_dir / project_id
                if project_dir.exists():
                    shutil.rmtree(project_dir)
                    output_lines.append(f"🗑️  Removed: {project_name} ({project_id})")
                    removed_count += 1
                    logger.info(f"Removed project: {project_id}")
            
            output = "\n".join(output_lines) + "\n"
            
            return {
                'success': True,
                'stdout': output,
                'stderr': '',
                'returncode': 0
            }
            
        except Exception as e:
            logger.error(f"Remove project error: {e}", exc_info=True)
            return {
                'success': False,
                'stdout': '',
                'stderr': f"Error: {str(e)}\n",
                'returncode': 1
            }
    
    def _find_matching_projects(self, pattern: str) -> List[tuple]:
        """Find projects matching the given pattern
        
        Pattern can be:
        - Exact project ID (e.g., ragex_1000_abc123...)
        - Project name glob pattern (e.g., "my-*", "*-test")
        
        Returns list of (project_name, project_id, project_path) tuples
        """
        matched = []
        
        if not self.data_dir.exists():
            return matched
        
        # Check if pattern looks like a project ID
        if pattern.startswith('ragex_') and '_' in pattern[6:]:
            # Direct project ID - check if it exists and belongs to user
            project_dir = self.data_dir / pattern
            if project_dir.exists():
                # Verify it belongs to current user
                user_prefix = f"ragex_{self.user_id}_"
                if pattern.startswith(user_prefix):
                    project_info = get_project_info(pattern, self.data_dir.parent)
                    if project_info:
                        project_name, workspace_path = project_info
                        matched.append((project_name, pattern, workspace_path))
                    else:
                        # Allow removal of orphaned projects (missing metadata)
                        logger.warning(f"Project {pattern} exists but has no metadata")
                        matched.append((f"orphaned-{pattern}", pattern, Path("unknown")))
            return matched
        
        # Otherwise treat as a name pattern
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
                
                # Check if name matches pattern
                if fnmatch.fnmatch(project_name, pattern):
                    matched.append((project_name, project_id, workspace_path))
            else:
                logger.warning(f"Project {project_id} has no metadata")
        
        return matched