"""
Registry for tracking loaded ignore files and their relationships
"""

from pathlib import Path
from typing import Dict, List, Optional, Set
from dataclasses import dataclass, field
import threading

from .file_loader import IgnoreFileInfo
from src.utils import get_logger

logger = get_logger(__name__)


@dataclass
class RegistryEntry:
    """Entry for a registered ignore file"""
    file_info: IgnoreFileInfo
    affects_paths: Set[Path] = field(default_factory=set)
    last_modified: Optional[float] = None


class IgnoreFileRegistry:
    """
    Tracks loaded ignore files and their hierarchical relationships
    """
    
    def __init__(self):
        """Initialize registry"""
        self._files: Dict[Path, RegistryEntry] = {}
        self._hierarchy: Dict[Path, List[Path]] = {}  # dir -> list of ignore files
        self._lock = threading.Lock()
    
    def register_file(self, file_info: IgnoreFileInfo):
        """
        Register an ignore file
        
        Args:
            file_info: Information about the ignore file
        """
        with self._lock:
            file_path = file_info.path
            
            # Get last modified time
            last_modified = None
            try:
                if file_path.exists():
                    last_modified = file_path.stat().st_mtime
            except Exception as e:
                logger.warning(f"Could not stat {file_path}: {e}")
            
            # Create registry entry
            entry = RegistryEntry(
                file_info=file_info,
                last_modified=last_modified
            )
            
            # Register the file
            self._files[file_path] = entry
            
            # Update hierarchy
            parent_dir = file_path.parent
            if parent_dir not in self._hierarchy:
                self._hierarchy[parent_dir] = []
            if file_path not in self._hierarchy[parent_dir]:
                self._hierarchy[parent_dir].append(file_path)
                # Sort by filename for consistent ordering
                self._hierarchy[parent_dir].sort()
            
            logger.debug(f"Registered ignore file: {file_path}")
    
    def unregister_file(self, file_path: Path):
        """
        Remove an ignore file from registry
        
        Args:
            file_path: Path to the ignore file
        """
        with self._lock:
            # Remove from files
            if file_path in self._files:
                del self._files[file_path]
                
            # Remove from hierarchy
            parent_dir = file_path.parent
            if parent_dir in self._hierarchy:
                self._hierarchy[parent_dir] = [
                    p for p in self._hierarchy[parent_dir] if p != file_path
                ]
                if not self._hierarchy[parent_dir]:
                    del self._hierarchy[parent_dir]
                    
            logger.debug(f"Unregistered ignore file: {file_path}")
    
    def get_file_info(self, file_path: Path) -> Optional[IgnoreFileInfo]:
        """
        Get information about a registered ignore file
        
        Args:
            file_path: Path to the ignore file
            
        Returns:
            IgnoreFileInfo or None if not registered
        """
        with self._lock:
            entry = self._files.get(file_path)
            return entry.file_info if entry else None
    
    def get_files_for_path(self, path: Path, root_path: Path) -> List[Path]:
        """
        Get all ignore files that affect a given path
        
        Args:
            path: Path to check
            root_path: Root directory of the project
            
        Returns:
            List of ignore file paths, ordered from root to most specific
        """
        with self._lock:
            ignore_files = []
            
            # Start from the path (or its parent if it's a file)
            current = path if path.is_dir() else path.parent
            
            # Walk up to root, collecting ignore files
            while current >= root_path:
                # Check if this directory has ignore files
                if current in self._hierarchy:
                    ignore_files.extend(self._hierarchy[current])
                    
                if current == root_path:
                    break
                current = current.parent
                
            # Also check root if not already included
            if root_path in self._hierarchy and current != root_path:
                ignore_files.extend(self._hierarchy[root_path])
                
            # Remove duplicates and sort by depth (root first)
            seen = set()
            unique_files = []
            for file_path in sorted(set(ignore_files), key=lambda p: len(p.parts)):
                if file_path not in seen:
                    seen.add(file_path)
                    unique_files.append(file_path)
                    
            return unique_files
    
    def get_all_files(self) -> List[Path]:
        """
        Get all registered ignore files
        
        Returns:
            List of all ignore file paths
        """
        with self._lock:
            return list(self._files.keys())
    
    def has_file_changed(self, file_path: Path) -> bool:
        """
        Check if a registered file has changed on disk
        
        Args:
            file_path: Path to check
            
        Returns:
            True if file has changed or doesn't exist
        """
        with self._lock:
            entry = self._files.get(file_path)
            if not entry:
                return False
                
            # Check if file still exists
            if not file_path.exists():
                return True
                
            # Check modification time
            try:
                current_mtime = file_path.stat().st_mtime
                return current_mtime != entry.last_modified
            except Exception:
                return True
    
    def get_stats(self) -> Dict[str, int]:
        """
        Get registry statistics
        
        Returns:
            Dictionary with registry stats
        """
        with self._lock:
            total_patterns = sum(
                len(entry.file_info.valid_patterns) 
                for entry in self._files.values()
            )
            
            directories_with_ignore = len(self._hierarchy)
            
            files_with_errors = sum(
                1 for entry in self._files.values()
                if entry.file_info.errors
            )
            
            files_with_warnings = sum(
                1 for entry in self._files.values()
                if entry.file_info.warnings
            )
            
            return {
                'total_files': len(self._files),
                'total_patterns': total_patterns,
                'directories_with_ignore': directories_with_ignore,
                'files_with_errors': files_with_errors,
                'files_with_warnings': files_with_warnings
            }
    
    def clear(self):
        """Clear the registry"""
        with self._lock:
            self._files.clear()
            self._hierarchy.clear()