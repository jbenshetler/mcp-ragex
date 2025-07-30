#!/usr/bin/env python3
"""
Path mapping utilities for converting between container and host paths.

All paths stored in the system (vector store, checksums, etc.) should be host paths.
The /workspace mount is only used for filesystem operations inside the container.
"""

import os
from pathlib import Path
from typing import Optional, Union


class PathMappingError(Exception):
    """Raised when path mapping cannot be performed due to missing configuration."""
    pass


def container_to_host_path(container_path: Union[str, Path], workspace_host: Optional[str] = None) -> str:
    """
    Convert container path to host path.
    
    Examples:
        /workspace/foo/bar.py -> /home/jeff/clients/mcp-ragex/foo/bar.py
        /workspace -> /home/jeff/clients/mcp-ragex
        
    Args:
        container_path: Path from inside the container
        workspace_host: Host workspace path (defaults to WORKSPACE_PATH env var)
        
    Returns:
        Host path as string
        
    Raises:
        PathMappingError: If WORKSPACE_PATH is not available
    """
    if workspace_host is None:
        workspace_host = os.environ.get('WORKSPACE_PATH', '')
    
    if not workspace_host:
        raise PathMappingError(
            "WORKSPACE_PATH environment variable is not set. "
            "Cannot map container paths to host paths. "
            "This should be set by the ragex wrapper script."
        )
    
    container_path = str(container_path)
    
    # Handle the exact /workspace path
    if container_path == '/workspace':
        return workspace_host
    
    # Handle paths under /workspace
    if container_path.startswith('/workspace/'):
        relative_path = container_path[11:]  # Remove '/workspace/'
        return os.path.join(workspace_host, relative_path)
    
    # Not a workspace path, return as-is
    return container_path


def host_to_container_path(host_path: Union[str, Path], workspace_host: Optional[str] = None) -> str:
    """
    Convert host path to container path.
    
    Examples:
        /home/jeff/clients/mcp-ragex/foo/bar.py -> /workspace/foo/bar.py
        /home/jeff/clients/mcp-ragex -> /workspace
        
    Args:
        host_path: Path from the host system
        workspace_host: Host workspace path (defaults to WORKSPACE_PATH env var)
        
    Returns:
        Container path as string
        
    Raises:
        PathMappingError: If WORKSPACE_PATH is not available
    """
    if workspace_host is None:
        workspace_host = os.environ.get('WORKSPACE_PATH', '')
    
    if not workspace_host:
        raise PathMappingError(
            "WORKSPACE_PATH environment variable is not set. "
            "Cannot map host paths to container paths. "
            "This should be set by the ragex wrapper script."
        )
    
    host_path = str(host_path)
    workspace_host = str(workspace_host)
    
    # Normalize paths for comparison
    host_path = os.path.abspath(host_path)
    workspace_host = os.path.abspath(workspace_host)
    
    # Handle the exact workspace path
    if host_path == workspace_host:
        return '/workspace'
    
    # Handle paths under workspace
    if host_path.startswith(workspace_host + os.sep):
        relative_path = os.path.relpath(host_path, workspace_host)
        # Convert to forward slashes for consistency in container
        relative_path = relative_path.replace(os.sep, '/')
        return f'/workspace/{relative_path}'
    
    # Not under workspace, return as-is
    return host_path


def is_container_path(path: Union[str, Path]) -> bool:
    """Check if a path is a container path (starts with /workspace)."""
    return str(path).startswith('/workspace')


def is_under_workspace(path: Union[str, Path], workspace_host: Optional[str] = None) -> bool:
    """
    Check if a host path is under the workspace directory.
    
    Raises:
        PathMappingError: If WORKSPACE_PATH is not available
    """
    if workspace_host is None:
        workspace_host = os.environ.get('WORKSPACE_PATH', '')
    
    if not workspace_host:
        raise PathMappingError(
            "WORKSPACE_PATH environment variable is not set. "
            "Cannot determine workspace boundaries."
        )
    
    path = os.path.abspath(str(path))
    workspace_host = os.path.abspath(workspace_host)
    
    return path == workspace_host or path.startswith(workspace_host + os.sep)