#!/usr/bin/env python3
"""
Project name resolution for ragex commands.

Resolves human-readable project names to project IDs for use in commands.
"""

import json
import sys
from pathlib import Path
from typing import List, Optional, Tuple


class ProjectNotFoundError(Exception):
    """Raised when no project matches the given identifier."""
    pass


class AmbiguousProjectError(Exception):
    """Raised when multiple projects match the given identifier."""
    pass


class ProjectResolver:
    """Resolves project names to project IDs with uniqueness validation."""
    
    def __init__(self, projects_dir: Path = Path('/data/projects')):
        self.projects_dir = projects_dir
    
    def resolve_project_identifier(self, identifier: str) -> str:
        """
        Resolve a project identifier (name or ID) to a unique project ID.
        
        Args:
            identifier: Project name or project ID
            
        Returns:
            Project ID if unique match found
            
        Raises:
            ProjectNotFoundError: No projects match the identifier
            AmbiguousProjectError: Multiple projects match the identifier
        """
        # First, check if it's already a valid project ID
        if self._is_valid_project_id(identifier):
            return identifier
        
        # Search by project name
        matches = self._find_projects_by_name(identifier)
        
        if len(matches) == 0:
            available_projects = self._get_available_projects()
            available_list = "\n".join([f"  {name} [{pid}]" for name, pid in available_projects])
            raise ProjectNotFoundError(
                f"No project found with name '{identifier}'\n\n"
                f"Available projects:\n{available_list}"
            )
        elif len(matches) == 1:
            return matches[0][1]  # Return project ID
        else:
            # Multiple matches - show full context
            match_list = "\n".join([f"  {pid} ({path})" for name, pid, path in matches])
            id_list = "\n".join([f"  ragex log {pid}" for name, pid, path in matches])
            raise AmbiguousProjectError(
                f"Multiple projects found with name '{identifier}':\n{match_list}\n\n"
                f"Use the full project ID instead:\n{id_list}"
            )
    
    def _is_valid_project_id(self, identifier: str) -> bool:
        """Check if identifier is already a valid project ID."""
        project_dir = self.projects_dir / identifier
        return project_dir.exists() and project_dir.is_dir()
    
    def _find_projects_by_name(self, name: str) -> List[Tuple[str, str, str]]:
        """
        Find all projects that have the given display name.
        
        Returns:
            List of (display_name, project_id, workspace_path) tuples
        """
        matches = []
        
        if not self.projects_dir.exists():
            return matches
        
        for project_dir in self.projects_dir.glob('*/'):
            project_id = project_dir.name
            info_file = project_dir / 'project_info.json'
            
            if info_file.exists():
                try:
                    info = json.loads(info_file.read_text())
                    workspace_basename = info.get('workspace_basename', '')
                    workspace_path = info.get('workspace_path', 'unknown')
                    
                    # Check basename match
                    if workspace_basename == name:
                        matches.append((workspace_basename, project_id, workspace_path))
                    # Also check path basename for old projects
                    elif workspace_path != 'unknown' and workspace_path:
                        path_basename = Path(workspace_path).name
                        if path_basename == name:
                            matches.append((path_basename, project_id, workspace_path))
                            
                except (json.JSONDecodeError, OSError):
                    continue
        
        return matches
    
    def _get_available_projects(self) -> List[Tuple[str, str]]:
        """
        Get all available projects with their display names.
        
        Returns:
            List of (display_name, project_id) tuples
        """
        projects = []
        
        if not self.projects_dir.exists():
            return projects
        
        for project_dir in self.projects_dir.glob('*/'):
            project_id = project_dir.name
            info_file = project_dir / 'project_info.json'
            
            if info_file.exists():
                try:
                    info = json.loads(info_file.read_text())
                    workspace_basename = info.get('workspace_basename', '')
                    workspace_path = info.get('workspace_path', 'unknown')
                    
                    # Use basename if available, otherwise try path basename
                    if workspace_basename:
                        display_name = workspace_basename
                    elif workspace_path != 'unknown' and workspace_path:
                        display_name = Path(workspace_path).name
                    else:
                        display_name = project_id
                    
                    projects.append((display_name, project_id))
                    
                except (json.JSONDecodeError, OSError):
                    # Fallback to project ID
                    projects.append((project_id, project_id))
            else:
                # No metadata, use project ID
                projects.append((project_id, project_id))
        
        return sorted(projects)


def main():
    """Command-line interface for project resolution."""
    if len(sys.argv) != 2:
        print("Usage: python -m src.ragex_core.project_resolver <identifier>", file=sys.stderr)
        sys.exit(1)
    
    identifier = sys.argv[1]
    resolver = ProjectResolver()
    
    try:
        project_id = resolver.resolve_project_identifier(identifier)
        print(project_id)
    except (ProjectNotFoundError, AmbiguousProjectError) as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"ERROR: Unexpected error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()