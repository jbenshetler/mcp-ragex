"""
Main ignore manager API for multi-level ignore file support with hot reloading
"""

import os
import logging
from pathlib import Path
from typing import List, Dict, Optional, Union, Set
import threading

from .constants import IGNORE_FILENAME, DEFAULT_EXCLUSIONS, MAX_CACHE_SIZE
from .rule_engine import IgnoreRuleEngine, CompiledRules
from .file_loader import IgnoreFileLoader, IgnoreFileInfo
from .cache import IgnoreCache
from .registry import IgnoreFileRegistry

logger = logging.getLogger(__name__)


class IgnoreManager:
    """
    Main API for ignore file management with multi-level support and hot reloading
    """
    
    def __init__(self,
                 root_path: Union[str, Path],
                 default_patterns: Optional[List[str]] = None,
                 cache_size: int = MAX_CACHE_SIZE,
                 auto_discover: bool = True,
                 use_defaults: bool = True):
        """
        Initialize the ignore manager
        
        Args:
            root_path: Root directory to manage
            default_patterns: Custom default exclusions (adds to DEFAULT_EXCLUSIONS if use_defaults=True)
            cache_size: LRU cache size for path decisions
            auto_discover: Automatically discover and load ignore files on init
            use_defaults: Whether to include DEFAULT_EXCLUSIONS (can be disabled for minimal setup)
        """
        self.root_path = Path(root_path).resolve()
        self.ignore_filename = IGNORE_FILENAME
        
        # Handle default patterns
        if use_defaults:
            self.default_patterns = DEFAULT_EXCLUSIONS.copy()
            if default_patterns:
                # Add custom patterns to defaults
                self.default_patterns.extend(default_patterns)
        else:
            # Use only custom patterns (or empty if none provided)
            self.default_patterns = default_patterns or []
        
        # Initialize components
        self._rule_engine = IgnoreRuleEngine()
        self._file_loader = IgnoreFileLoader(self.ignore_filename)
        self._cache = IgnoreCache(cache_size)
        self._registry = IgnoreFileRegistry()
        
        # Thread safety
        self._lock = threading.RLock()
        
        # Compiled rules
        self._compiled_rules: Optional[CompiledRules] = None
        
        # Auto-discover ignore files
        if auto_discover:
            self._load_ignore_files()
    
    def should_ignore(self, path: Union[str, Path]) -> bool:
        """
        Check if a path should be ignored
        
        Args:
            path: Path to check (relative or absolute)
            
        Returns:
            True if path should be ignored, False otherwise
        """
        path = Path(path)
        
        # Check cache first
        cached_decision = self._cache.get_decision(path)
        if cached_decision is not None:
            return cached_decision
            
        with self._lock:
            # Double-check cache inside lock
            cached_decision = self._cache.get_decision(path)
            if cached_decision is not None:
                return cached_decision
                
            # No compiled rules means nothing to ignore (except defaults)
            if not self._compiled_rules:
                return False
                
            # Match against rules
            result = self._rule_engine.match_path(
                path, self._compiled_rules, self.root_path
            )
            
            # Get all ignore files that could affect this path
            ignore_files = set(self._registry.get_files_for_path(path, self.root_path))
            
            # Cache the decision
            self._cache.cache_decision(path, result.should_ignore, ignore_files)
            
            logger.debug(
                f"Ignore check for {path}: {result.should_ignore} "
                f"(matched: {result.matched_pattern} from {result.matched_file})"
            )
            
            return result.should_ignore
    
    def notify_file_changed(self, file_path: Union[str, Path]):
        """
        Handle external notification of ignore file change
        
        Args:
            file_path: Path to the changed ignore file
        """
        file_path = Path(file_path).resolve()
        
        logger.info(f"Received change notification for: {file_path}")
        
        # Check if it's an ignore file
        if file_path.name != self.ignore_filename:
            logger.debug(f"Not an ignore file: {file_path}")
            return
            
        with self._lock:
            # Invalidate caches
            self._cache.invalidate_ignore_file(file_path)
            
            # Reload the specific file
            self.reload_file(file_path)
    
    def reload_file(self, file_path: Union[str, Path]):
        """
        Reload a specific ignore file and update rules
        
        Args:
            file_path: Path to the ignore file to reload
        """
        file_path = Path(file_path).resolve()
        
        with self._lock:
            logger.info(f"Reloading ignore file: {file_path}")
            
            # Check if file exists
            if not file_path.exists():
                # File was deleted - unregister it
                self._registry.unregister_file(file_path)
            else:
                # Reload the file
                file_info = self._file_loader.load_file(file_path)
                self._registry.register_file(file_info)
                
                # Log any errors or warnings
                if file_info.errors:
                    for error in file_info.errors:
                        logger.error(
                            f"{file_path}:{error.line}: {error.message}"
                        )
                if file_info.warnings:
                    for warning in file_info.warnings:
                        logger.warning(
                            f"{file_path}:{warning.line}: {warning.message}"
                        )
                        
            # Recompile all rules
            self._recompile_rules()
    
    def reload_all(self):
        """Reload all ignore files"""
        with self._lock:
            logger.info("Reloading all ignore files")
            self._load_ignore_files()
    
    def get_patterns_for_path(self, path: Union[str, Path]) -> List[str]:
        """
        Get all patterns that affect a path
        
        Args:
            path: Path to check
            
        Returns:
            List of patterns in order of precedence
        """
        path = Path(path)
        
        with self._lock:
            if not self._compiled_rules:
                return self.default_patterns.copy()
                
            patterns = self._rule_engine.get_effective_patterns(
                path, self._compiled_rules, self.root_path
            )
            
            # Prepend default patterns
            return self.default_patterns + patterns
    
    def validate_all(self) -> Dict[Path, IgnoreFileInfo]:
        """
        Validate all ignore files
        
        Returns:
            Dictionary mapping file paths to their validation info
        """
        with self._lock:
            result = {}
            for file_path in self._registry.get_all_files():
                info = self._registry.get_file_info(file_path)
                if info:
                    result[file_path] = info
            return result
    
    def get_ignore_files(self) -> List[Path]:
        """
        Get list of all discovered ignore files
        
        Returns:
            List of paths to ignore files
        """
        with self._lock:
            return self._registry.get_all_files()
    
    def get_stats(self) -> Dict[str, any]:
        """
        Get comprehensive statistics
        
        Returns:
            Dictionary with various statistics
        """
        with self._lock:
            return {
                'root_path': str(self.root_path),
                'ignore_filename': self.ignore_filename,
                'default_patterns': len(self.default_patterns),
                'registry': self._registry.get_stats(),
                'cache': self._cache.get_stats(),
                'compiled': self._compiled_rules is not None
            }
    
    def _load_ignore_files(self):
        """Load all ignore files under root path"""
        logger.info(f"Discovering ignore files under: {self.root_path}")
        
        # Clear existing data
        self._registry.clear()
        self._cache.clear()
        
        # Find all ignore files
        ignore_files = self._file_loader.find_ignore_files(self.root_path)
        
        # Note: Warning about missing ignore files is now handled at a higher level
        # by PatternMatcher.check_ignore_file() to avoid duplicate warnings
        
        logger.info(f"Found {len(ignore_files)} ignore files")
        
        # Load each file
        for file_path in ignore_files:
            file_info = self._file_loader.load_file(file_path)
            self._registry.register_file(file_info)
            
            # Log any errors or warnings
            if file_info.errors:
                for error in file_info.errors:
                    logger.error(
                        f"{file_path}:{error.line}: {error.message}"
                    )
            if file_info.warnings:
                for warning in file_info.warnings:
                    logger.warning(
                        f"{file_path}:{warning.line}: {warning.message}"
                    )
                    
        # Compile all rules
        self._recompile_rules()
    
    def _recompile_rules(self):
        """Recompile all rules from registered files"""
        rules_by_level = {}
        
        # Add default patterns at root level
        rules_by_level[self.root_path] = self.default_patterns.copy()
        
        # Add patterns from each ignore file
        for file_path in self._registry.get_all_files():
            file_info = self._registry.get_file_info(file_path)
            if file_info and file_info.valid_patterns:
                # Use the directory containing the ignore file as the level
                level_path = file_path.parent
                if level_path not in rules_by_level:
                    rules_by_level[level_path] = []
                rules_by_level[level_path].extend(file_info.valid_patterns)
                
        # Compile all rules
        self._compiled_rules = self._rule_engine.compile_rules(rules_by_level)
        
        logger.info(
            f"Compiled {len(rules_by_level)} rule sets with "
            f"{sum(len(patterns) for patterns in rules_by_level.values())} total patterns"
        )