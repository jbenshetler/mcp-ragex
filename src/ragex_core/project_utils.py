#!/usr/bin/env python3
"""
Project utilities for ragex.

Handles project detection, ID generation, and metadata management.
"""

import hashlib
import json
import logging
import os
from pathlib import Path
from typing import Optional, Dict, Any

logger = logging.getLogger("project-utils")


def get_project_data_dir() -> str:
    """
    Get the project data directory from environment.
    
    Checks RAGEX_PROJECT_DATA_DIR first, then falls back to PROJECT_NAME.
    
    Returns:
        Project data directory path
    """
    project_data_dir = os.environ.get('RAGEX_PROJECT_DATA_DIR')
    if not project_data_dir:
        project_name = os.environ.get('PROJECT_NAME', 'admin')
        project_data_dir = f'/data/projects/{project_name}'
    return project_data_dir


def get_chroma_db_path(project_data_dir: Optional[str] = None) -> Path:
    """
    Get the ChromaDB path for a project.
    
    Args:
        project_data_dir: Optional project data directory. If not provided,
                         will be determined from environment variables.
    
    Returns:
        Path to ChromaDB directory
    """
    if project_data_dir is None:
        project_data_dir = get_project_data_dir()
    return Path(project_data_dir) / "chroma_db"


def generate_project_id(workspace_path: str, user_id: str) -> str:
    """
    Generate consistent project ID from workspace path and user.
    
    Args:
        workspace_path: Absolute path to workspace
        user_id: User ID (typically UID)
        
    Returns:
        Project ID string like "ragex_1000_8375a7fda539e891"
    """
    # Ensure absolute path for consistency
    abs_path = str(Path(workspace_path).resolve())
    
    # Create hash from user:path combination
    project_hash = hashlib.sha256(f"{user_id}:{abs_path}".encode()).hexdigest()[:16]
    
    return f"ragex_{user_id}_{project_hash}"


def find_existing_project_root(current_path: Path, user_id: str, data_dir: Path = Path("/data")) -> Optional[Path]:
    """
    Walk up directory tree looking for existing indexed project.
    
    Args:
        current_path: Directory to start search from
        user_id: User ID for project isolation
        data_dir: Base data directory (default: /data)
        
    Returns:
        Path to project root if found, None otherwise
    """
    path = current_path.resolve()
    projects_dir = data_dir / "projects"
    
    # Walk up directory tree
    while path != path.parent:  # Not at filesystem root
        # Generate project ID for this path
        project_id = generate_project_id(str(path), user_id)
        project_data_dir = projects_dir / project_id
        
        # Check if project info exists
        project_info_path = project_data_dir / "project_info.json"
        if project_info_path.exists():
            logger.info(f"Found existing project at: {path}")
            return path
            
        # Move up one directory
        path = path.parent
    
    return None


def load_project_metadata(project_id: str, data_dir: Path = Path("/data")) -> Optional[Dict[str, Any]]:
    """
    Load project metadata from JSON file.
    
    Args:
        project_id: Project identifier
        data_dir: Base data directory
        
    Returns:
        Project metadata dict or None if not found
    """
    project_info_path = data_dir / "projects" / project_id / "project_info.json"
    
    try:
        if project_info_path.exists():
            with open(project_info_path, 'r') as f:
                return json.load(f)
    except Exception as e:
        logger.error(f"Failed to load project metadata: {e}")
    
    return None


def save_project_metadata(project_id: str, metadata: Dict[str, Any], data_dir: Path = Path("/data")) -> bool:
    """
    Save project metadata to JSON file.
    
    Args:
        project_id: Project identifier  
        metadata: Metadata dictionary to save
        data_dir: Base data directory
        
    Returns:
        True if saved successfully, False otherwise
    """
    project_dir = data_dir / "projects" / project_id
    project_info_path = project_dir / "project_info.json"
    
    try:
        # Ensure directory exists
        project_dir.mkdir(parents=True, exist_ok=True)
        
        # Write metadata
        with open(project_info_path, 'w') as f:
            json.dump(metadata, f, indent=2)
            
        return True
        
    except Exception as e:
        logger.error(f"Failed to save project metadata: {e}")
        return False


def update_project_metadata(project_id: str, updates: Dict[str, Any], data_dir: Path = Path("/data")) -> bool:
    """
    Update project metadata with new values.
    
    Args:
        project_id: Project identifier
        updates: Dictionary of updates to apply
        data_dir: Base data directory
        
    Returns:
        True if updated successfully
    """
    # Load existing metadata
    metadata = load_project_metadata(project_id, data_dir) or {}
    
    # Apply updates
    metadata.update(updates)
    
    # Save back
    return save_project_metadata(project_id, metadata, data_dir)


