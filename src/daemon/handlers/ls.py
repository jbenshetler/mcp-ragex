#!/usr/bin/env python3
"""Handler for ls (list projects) command"""

import fnmatch
import os
import shutil
import sys
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

from src.ragex_core.project_utils import get_project_info, load_project_metadata
from src.ragex_core.constants import ADMIN_PROJECT_NAME, ADMIN_WORKSPACE_PATH
from src.utils import get_logger

logger = get_logger(__name__)


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
            show_all = False
            human_readable = False
            
            for arg in args:
                if arg == '-l' or arg == '--long':
                    long_format = True
                elif arg == '-a' or arg == '--all':
                    show_all = True
                elif arg == '-h' or arg == '--human-readable':
                    human_readable = True
                elif not arg.startswith('-'):
                    pattern = arg
            
            # Get all projects for current user
            projects = self._get_user_projects(pattern, show_all)
            
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
                output = self._format_long_output(projects, human_readable)
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
    
    def _get_user_projects(self, pattern: Optional[str] = None, show_all: bool = False) -> List[Tuple[str, str, Path]]:
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
                
                # Skip admin projects unless -a flag is used
                if not show_all and (project_name == ADMIN_PROJECT_NAME or str(workspace_path) == ADMIN_WORKSPACE_PATH):
                    continue
                
                # Apply pattern filter if provided
                if pattern and not fnmatch.fnmatch(project_name, pattern):
                    continue
                
                projects.append((project_name, project_id, workspace_path))
            else:
                # Log warning for projects without metadata
                logger.warning(f"Project {project_id} has no metadata (no project_info.json or workspace_path.txt)")
        
        # Sort by project name
        projects.sort(key=lambda x: x[0])
        
        # Ensure unique project names by adding suffixes
        projects = self._ensure_unique_names(projects)
        
        return projects
    
    def _ensure_unique_names(self, projects: List[Tuple[str, str, Path]]) -> List[Tuple[str, str, Path]]:
        """Ensure all project names are unique by adding suffixes where needed
        
        Args:
            projects: List of (project_name, project_id, project_path) tuples
            
        Returns:
            List with unique project names, suffixed as needed (_001, _002, etc.)
        """
        name_counts = {}
        unique_projects = []
        
        # First pass: count occurrences of each name
        for name, _, _ in projects:
            name_counts[name] = name_counts.get(name, 0) + 1
        
        # Track how many times we've seen each base name
        name_seen = {}
        
        # Second pass: add suffixes where needed
        for name, project_id, path in projects:
            if name_counts[name] > 1:
                # This name appears multiple times, add suffix
                count = name_seen.get(name, 0)
                name_seen[name] = count + 1
                
                if count > 0:  # First occurrence keeps original name
                    unique_name = f"{name}_{count:03d}"
                else:
                    unique_name = name
            else:
                # Name is already unique
                unique_name = name
            
            unique_projects.append((unique_name, project_id, path))
        
        return unique_projects
    
    def _format_basic_output(self, projects: List[Tuple[str, str, Path]]) -> str:
        """Format basic output with PROJECT NAME, PROJECT ID, and PATH columns"""
        if not projects:
            return ""
        
        # Calculate column widths
        name_width = max(len(p[0]) for p in projects)
        name_width = max(name_width, 20)  # Minimum 20 chars
        id_width = 30  # Fixed width for project IDs
        
        # Build output
        lines = []
        
        # Header
        header = f"{'PROJECT NAME':<{name_width}}  {'PROJECT ID':<{id_width}}  PATH"
        lines.append(header)
        lines.append("-" * len(header))
        
        # Projects - let paths go as far as needed (left aligned)
        for name, project_id, path in projects:
            path_str = str(path)
            line = f"{name:<{name_width}}  {project_id:<{id_width}}  {path_str}"
            lines.append(line)
        
        return "\n".join(lines) + "\n"
    
    def _format_long_output(self, projects: List[Tuple[str, str, Path]], human_readable: bool = False) -> str:
        """Format long output with additional MODEL, INDEXED, SYMBOLS, and SIZE columns"""
        if not projects:
            return ""
        
        # Gather additional info for each project
        extended_projects = []
        for name, project_id, path in projects:
            model = self._get_project_model(project_id)
            indexed = self._is_project_indexed(project_id)
            symbols = self._get_project_symbols_count(project_id) if indexed else 0
            size = self._get_project_index_size(project_id, human_readable) if indexed else "0"
            extended_projects.append((name, project_id, model, indexed, symbols, size, path))
        
        # Calculate column widths
        name_width = max(len(p[0]) for p in extended_projects)
        name_width = max(name_width, 20)  # Minimum 20 chars
        id_width = 30  # Fixed width for project IDs
        model_width = 10
        indexed_width = 8
        symbols_width = 8
        size_width = 12
        
        # Build output
        lines = []
        
        # Header
        header = f"{'PROJECT NAME':<{name_width}}  {'PROJECT ID':<{id_width}}  {'MODEL':<{model_width}}  {'INDEXED':<{indexed_width}}  {'SYMBOLS':<{symbols_width}}  {'SIZE':<{size_width}}  PATH"
        lines.append(header)
        lines.append("-" * len(header))
        
        # Projects - let paths go as far as needed (left aligned)
        for name, project_id, model, indexed, symbols, size, path in extended_projects:
            path_str = str(path)
            indexed_str = "yes" if indexed else "no"
            symbols_str = str(symbols) if indexed else "-"
            size_str = str(size) if indexed else "-"
            line = f"{name:<{name_width}}  {project_id:<{id_width}}  {model:<{model_width}}  {indexed_str:<{indexed_width}}  {symbols_str:<{symbols_width}}  {size_str:<{size_width}}  {path_str}"
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
    
    def _get_project_symbols_count(self, project_id: str) -> int:
        """Get the number of symbols indexed for a project"""
        try:
            # Import ChromaDB client
            import chromadb
            from chromadb.config import Settings
            
            # Get project's ChromaDB path
            chroma_path = self.data_dir / project_id / 'chroma_db'
            if not chroma_path.exists():
                return 0
            
            # Connect to ChromaDB
            client = chromadb.PersistentClient(
                path=str(chroma_path),
                settings=Settings(allow_reset=True, anonymized_telemetry=False)
            )
            
            # Get the collection (use default name)
            collection_name = "code_embeddings"  # Default collection name
            try:
                collection = client.get_collection(collection_name)
                return collection.count()
            except Exception:
                # Collection doesn't exist or is empty
                return 0
                
        except Exception as e:
            logger.warning(f"Failed to get symbols count for {project_id}: {e}")
            return 0
    
    def _get_project_index_size(self, project_id: str, human_readable: bool = False) -> str:
        """Get the size of the project's index in bytes"""
        try:
            chroma_path = self.data_dir / project_id / 'chroma_db'
            if not chroma_path.exists():
                return "0"
            
            # Calculate directory size
            total_size = 0
            for file_path in chroma_path.rglob('*'):
                if file_path.is_file():
                    total_size += file_path.stat().st_size
            
            if human_readable:
                return self._format_bytes(total_size)
            else:
                return str(total_size)
                
        except Exception as e:
            logger.warning(f"Failed to get index size for {project_id}: {e}")
            return "0"
    
    def _format_bytes(self, size_bytes: int) -> str:
        """Format bytes in human-readable format (like bintools ls)"""
        if size_bytes == 0:
            return "0B"
        
        # Define size units
        units = ['B', 'K', 'M', 'G', 'T', 'P']
        unit_index = 0
        size = float(size_bytes)
        
        # Convert to appropriate unit
        while size >= 1024.0 and unit_index < len(units) - 1:
            size /= 1024.0
            unit_index += 1
        
        # Format with appropriate precision
        if unit_index == 0:  # Bytes
            return f"{int(size)}B"
        elif size >= 100:
            return f"{int(size)}{units[unit_index]}"
        elif size >= 10:
            return f"{size:.1f}{units[unit_index]}"
        else:
            return f"{size:.2f}{units[unit_index]}"