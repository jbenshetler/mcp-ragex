"""
Caching system for ignore decisions and compiled patterns
"""

from pathlib import Path
from typing import Dict, Optional, Set, Tuple, List
from collections import OrderedDict
import threading

from .constants import MAX_CACHE_SIZE
from src.utils import get_logger

logger = get_logger(__name__)


class LRUCache:
    """Thread-safe LRU cache implementation"""
    
    def __init__(self, max_size: int):
        self.max_size = max_size
        self._cache: OrderedDict = OrderedDict()
        self._lock = threading.Lock()
        self._hits = 0
        self._misses = 0
    
    def get(self, key: str) -> Optional[any]:
        """Get value from cache"""
        with self._lock:
            if key in self._cache:
                # Move to end (most recently used)
                self._cache.move_to_end(key)
                self._hits += 1
                return self._cache[key]
            self._misses += 1
            return None
    
    def put(self, key: str, value: any):
        """Put value in cache"""
        with self._lock:
            if key in self._cache:
                # Update and move to end
                self._cache[key] = value
                self._cache.move_to_end(key)
            else:
                # Add new entry
                self._cache[key] = value
                # Remove oldest if over capacity
                if len(self._cache) > self.max_size:
                    self._cache.popitem(last=False)
    
    def invalidate(self, key: str):
        """Remove key from cache"""
        with self._lock:
            self._cache.pop(key, None)
    
    def invalidate_prefix(self, prefix: str):
        """Remove all keys starting with prefix"""
        with self._lock:
            keys_to_remove = [k for k in self._cache if k.startswith(prefix)]
            for key in keys_to_remove:
                self._cache.pop(key, None)
    
    def clear(self):
        """Clear entire cache"""
        with self._lock:
            self._cache.clear()
            self._hits = 0
            self._misses = 0
    
    def get_stats(self) -> Dict[str, int]:
        """Get cache statistics"""
        with self._lock:
            total = self._hits + self._misses
            hit_rate = (self._hits / total * 100) if total > 0 else 0
            return {
                'size': len(self._cache),
                'max_size': self.max_size,
                'hits': self._hits,
                'misses': self._misses,
                'hit_rate': hit_rate
            }


class IgnoreCache:
    """
    Caching system for ignore decisions and compiled patterns
    """
    
    def __init__(self, max_size: int = MAX_CACHE_SIZE):
        """
        Initialize cache
        
        Args:
            max_size: Maximum number of entries in each cache
        """
        # Cache for path -> ignore decision
        self._path_cache = LRUCache(max_size)
        
        # Cache for directory -> list of ignore files
        self._dir_cache = LRUCache(max_size // 10)  # Smaller cache for directories
        
        # Track which ignore files affect which cached paths
        self._file_dependencies: Dict[Path, Set[str]] = {}
        self._dep_lock = threading.Lock()
    
    def get_decision(self, path: Path) -> Optional[bool]:
        """
        Get cached ignore decision for a path
        
        Args:
            path: Path to check
            
        Returns:
            Cached decision or None if not cached
        """
        return self._path_cache.get(str(path))
    
    def cache_decision(self, path: Path, should_ignore: bool, 
                      ignore_files: Optional[Set[Path]] = None):
        """
        Cache an ignore decision
        
        Args:
            path: Path that was checked
            should_ignore: Decision for this path
            ignore_files: Set of ignore files that influenced this decision
        """
        path_str = str(path)
        self._path_cache.put(path_str, should_ignore)
        
        # Track dependencies
        if ignore_files:
            with self._dep_lock:
                for ignore_file in ignore_files:
                    if ignore_file not in self._file_dependencies:
                        self._file_dependencies[ignore_file] = set()
                    self._file_dependencies[ignore_file].add(path_str)
    
    def get_ignore_files(self, directory: Path) -> Optional[List[Path]]:
        """
        Get cached list of ignore files for a directory
        
        Args:
            directory: Directory to check
            
        Returns:
            Cached list of ignore files or None
        """
        return self._dir_cache.get(str(directory))
    
    def cache_ignore_files(self, directory: Path, ignore_files: List[Path]):
        """
        Cache the list of ignore files for a directory
        
        Args:
            directory: Directory that was scanned
            ignore_files: List of ignore files found
        """
        self._dir_cache.put(str(directory), ignore_files)
    
    def invalidate_path(self, path: Path):
        """
        Invalidate cache for a specific path and its descendants
        
        Args:
            path: Path to invalidate
        """
        path_str = str(path)
        
        # Invalidate the exact path
        self._path_cache.invalidate(path_str)
        
        # Invalidate all descendants
        self._path_cache.invalidate_prefix(path_str + "/")
        
        # If it's a directory, invalidate directory cache
        if path.is_dir():
            self._dir_cache.invalidate(path_str)
            self._dir_cache.invalidate_prefix(path_str + "/")
    
    def invalidate_ignore_file(self, ignore_file: Path):
        """
        Invalidate all cached decisions that depend on a specific ignore file
        
        Args:
            ignore_file: Path to the ignore file that changed
        """
        with self._dep_lock:
            # Get all paths that depend on this ignore file
            dependent_paths = self._file_dependencies.get(ignore_file, set())
            
            # Invalidate each dependent path
            for path_str in dependent_paths:
                self._path_cache.invalidate(path_str)
                
            # Clear the dependency tracking for this file
            if ignore_file in self._file_dependencies:
                del self._file_dependencies[ignore_file]
                
        # Also invalidate directory cache for the ignore file's directory
        self._dir_cache.invalidate(str(ignore_file.parent))
    
    def clear(self):
        """Clear all caches"""
        self._path_cache.clear()
        self._dir_cache.clear()
        with self._dep_lock:
            self._file_dependencies.clear()
    
    def get_stats(self) -> Dict[str, Dict[str, int]]:
        """
        Get cache statistics
        
        Returns:
            Dictionary with stats for each cache type
        """
        with self._dep_lock:
            dep_count = sum(len(deps) for deps in self._file_dependencies.values())
            
        return {
            'path_cache': self._path_cache.get_stats(),
            'dir_cache': self._dir_cache.get_stats(),
            'dependencies': {
                'tracked_files': len(self._file_dependencies),
                'total_dependencies': dep_count
            }
        }