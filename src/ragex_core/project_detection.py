"""
Project detection utilities for auto-detecting projects from current working directory.
"""

import os
import logging
from pathlib import Path
from typing import Optional, Dict

from .constants import WORKSPACE_MOUNT
from .project_utils import (
    find_existing_project_root, 
    generate_project_id, 
    load_project_metadata,
    get_project_data_dir_for_id
)

logger = logging.getLogger("project-detection")


def detect_project_from_cwd() -> Optional[Dict[str, str]]:
    """
    Detect project from current working directory.
    
    This function works both inside and outside the container:
    - Inside container: Code is mounted at /workspace, WORKSPACE_PATH has host path
    - Outside container: Uses current directory directly
    
    Returns:
        Dict with project_id, project_name, project_data_dir, project_root
        None if no project found
    """
    # Get current working directory
    cwd = Path.cwd()
    logger.debug(f"Detecting project from CWD: {cwd}")
    
    # Get user ID
    user_id = os.environ.get('DOCKER_USER_ID', str(os.getuid()))
    logger.debug(f"User ID: {user_id}")
    
    # Determine the host path to use for project detection
    host_workspace_path = os.environ.get('WORKSPACE_PATH')
    
    if host_workspace_path:
        # Running in container with WORKSPACE_PATH set
        logger.debug(f"WORKSPACE_PATH set: {host_workspace_path}")
        
        # Check if we're in the workspace mount
        workspace_path = Path(WORKSPACE_MOUNT)
        if str(cwd).startswith(str(workspace_path)):
            # Calculate relative path from workspace root
            try:
                rel_path = cwd.relative_to(workspace_path)
                if str(rel_path) == '.':
                    current_host_path = Path(host_workspace_path)
                else:
                    current_host_path = Path(host_workspace_path) / rel_path
                logger.debug(f"In container workspace, host path: {current_host_path}")
            except ValueError:
                current_host_path = Path(host_workspace_path)
        else:
            # Not in workspace mount, but WORKSPACE_PATH is set
            # This could be a daemon command that doesn't need workspace
            logger.debug("Not in workspace mount, using WORKSPACE_PATH directly")
            current_host_path = Path(host_workspace_path)
    else:
        # No WORKSPACE_PATH - likely running outside container
        # Use current directory as-is
        logger.debug("No WORKSPACE_PATH set, using current directory")
        current_host_path = cwd
    
    logger.debug(f"Using host path for detection: {current_host_path}")
    
    # Find project using host path
    project_root = find_existing_project_root(current_host_path, user_id)
    if not project_root:
        logger.debug(f"No indexed project found for {current_host_path}")
        return None
    
    logger.debug(f"Found project root: {project_root}")
    
    # Generate project ID from host path
    project_id = generate_project_id(str(project_root), user_id)
    project_data_dir = get_project_data_dir_for_id(project_id)
    
    # Load project metadata
    metadata = load_project_metadata(project_id)
    if metadata:
        # Use project_name if available, otherwise fall back to workspace_basename
        project_name = metadata.get('project_name', metadata.get('workspace_basename', 'unknown'))
    else:
        project_name = Path(project_root).name
    
    result = {
        'project_id': project_id,
        'project_name': project_name,
        'project_data_dir': project_data_dir,
        'project_root': str(project_root),
        'host_path': str(current_host_path)
    }
    
    logger.info(f"Detected project: {project_name} (ID: {project_id})")
    return result