#!/usr/bin/env python3
"""
Pattern matching for file exclusions using gitignore-style patterns

This module now uses the enhanced ignore system internally while maintaining
backward compatibility with the original API.
"""

import logging
import os
from pathlib import Path
from typing import List, Optional, Dict, Any, Tuple, Union

import pathspec

# Import the enhanced ignore system
try:
    from src.ignore import IgnoreManager, IGNORE_FILENAME
    from src.ignore.constants import DEFAULT_EXCLUSIONS as ENHANCED_DEFAULT_EXCLUSIONS
except ImportError:
    from .ignore import IgnoreManager, IGNORE_FILENAME
    from .ignore.constants import DEFAULT_EXCLUSIONS as ENHANCED_DEFAULT_EXCLUSIONS

logger = logging.getLogger("pattern-matcher")


class PatternMatcher:
    """
    Handles gitignore-style pattern matching for file exclusions
    
    This class now uses the enhanced ignore system internally while maintaining
    backward compatibility. All the new features (multi-level .mcpignore files,
    comprehensive defaults, hot reloading) are available through this class.
    """
    
    @classmethod
    def check_ignore_file(cls, directory: Union[str, Path]) -> bool:
        """
        Check if an ignore file exists in the given directory and warn if not.
        
        Args:
            directory: Directory to check for ignore file
            
        Returns:
            True if ignore file exists, False otherwise
        """
        directory = Path(directory)
        ignore_file = directory / IGNORE_FILENAME
        
        if not ignore_file.exists():
            # Check environment variable
            warn_env = os.environ.get('RAGEX_IGNOREFILE_WARNING', 'true').lower()
            should_warn = warn_env not in ('false', '0', 'no', 'off')
            
            if should_warn:
                logger.warning(
                    f"No {IGNORE_FILENAME} found at {directory}. "
                    f"Using built-in default exclusions. "
                    f"Run 'ragex init' to create {IGNORE_FILENAME} with defaults. "
                    f"Set RAGEX_IGNOREFILE_WARNING=false to disable this warning."
                )
            return False
        return True
    
    # Keep old defaults for reference/compatibility
    # The enhanced system has much more comprehensive defaults
    DEFAULT_EXCLUSIONS = [
        ".venv/**",
        "venv/**",
        "__pycache__/**",
        "*.pyc",
        ".git/**",
        "node_modules/**",
        ".mypy_cache/**",
        ".pytest_cache/**",
        ".tox/**",
        ".coverage",
        "*.log",
        ".DS_Store",
        "Thumbs.db",
        "*.swp",
        "*.swo",
        "*~",
    ]
    
    def __init__(self, custom_patterns: Optional[List[str]] = None):
        """
        Initialize pattern matcher with default and custom patterns
        
        Args:
            custom_patterns: Additional patterns to include (from API)
        """
        self._validation_report = None
        self.working_directory = Path.cwd()  # Default to current working directory
        self._custom_patterns = custom_patterns or []
        
        # Initialize the enhanced ignore manager
        self._init_ignore_manager()
        
        # For backward compatibility, populate these attributes
        self.patterns = self._get_all_patterns()
        self.spec = None  # No longer used, but kept for compatibility
        
    def _init_ignore_manager(self):
        """Initialize the enhanced ignore manager"""
        # Create ignore manager with custom patterns added to defaults
        self._ignore_manager = IgnoreManager(
            root_path=self.working_directory,
            default_patterns=self._custom_patterns,  # These are added to defaults
            auto_discover=True,
            use_defaults=True  # Always use comprehensive defaults
        )
    
    def _get_all_patterns(self) -> List[str]:
        """Get all patterns for backward compatibility"""
        # Get patterns that apply at the working directory level
        patterns = self._ignore_manager.get_patterns_for_path(self.working_directory)
        
        # Also populate validation report if we have a root .mcpignore
        self._read_mcpignore()
        
        return patterns
    
    def _load_all_patterns(self, custom_patterns: Optional[List[str]]) -> List[str]:
        """
        Load patterns in priority order
        
        This method is kept for backward compatibility but now just returns
        the patterns from the enhanced ignore manager.
        """
        return self._get_all_patterns()
    
    def _read_mcpignore(self) -> List[str]:
        """
        Read and validate patterns from .mcpignore file
        
        This method is kept for backward compatibility. The enhanced system
        handles all .mcpignore reading internally with multi-level support.
        """
        # Get validation report from the enhanced system
        all_reports = self._ignore_manager.validate_all()
        mcpignore_path = self.working_directory / IGNORE_FILENAME
        
        if mcpignore_path in all_reports:
            info = all_reports[mcpignore_path]
            
            # Convert to old validation report format
            self._validation_report = {
                "valid_count": len(info.valid_patterns),
                "invalid_patterns": [
                    (err.line, err.pattern, err.message)
                    for err in info.errors
                ],
                "warnings": [
                    f"Line {warn.line}: {warn.message}"
                    for warn in info.warnings
                ],
            }
            
            return info.valid_patterns
        
        return []
    
    def _compile_patterns(self, patterns: List[str]) -> Optional[pathspec.PathSpec]:
        """
        Compile patterns with individual error handling
        
        This method is kept for backward compatibility but is no longer used
        internally. The enhanced system handles pattern compilation.
        """
        # The enhanced system handles all pattern compilation
        # This is kept for compatibility but returns None
        return None
    
    def set_working_directory(self, working_directory: str):
        """
        Set the working directory for .mcpignore file lookup
        
        Args:
            working_directory: Path to the working directory
        """
        self.working_directory = Path(working_directory)
        logger.debug(f"Set working directory to: {self.working_directory}")
        
        # Reinitialize the enhanced ignore manager with new directory
        self._init_ignore_manager()
        
        # Update patterns for backward compatibility
        self.patterns = self._get_all_patterns()
        
        # Debug: Show what patterns were loaded
        logger.debug(f"Reloaded patterns: {self.patterns}")
    
    def should_exclude(self, file_path: str) -> bool:
        """
        Check if a file should be excluded based on patterns
        
        Args:
            file_path: Path to check (relative or absolute)
            
        Returns:
            True if file should be excluded, False otherwise
        """
        # Use the enhanced ignore manager
        return self._ignore_manager.should_ignore(file_path)
    
    def get_ripgrep_args(self) -> List[str]:
        """
        Convert patterns to ripgrep --glob arguments
        
        Returns:
            List of ripgrep arguments for exclusion
        """
        args = []
        
        # Get all patterns from the enhanced system
        patterns = self._get_all_patterns()
        
        for pattern in patterns:
            # Handle negation patterns (ripgrep uses ! prefix for exclusion)
            if pattern.startswith('!'):
                # Double negation: include this pattern
                args.extend(['--glob', pattern[1:]])
            else:
                # Normal exclusion
                args.extend(['--glob', f'!{pattern}'])
        
        return args
    
    def get_validation_report(self) -> Optional[Dict[str, Any]]:
        """Get detailed validation report from .mcpignore parsing"""
        return self._validation_report
    
    def validate_mcpignore(self, verbose: bool = False) -> Dict[str, Any]:
        """
        Validate .mcpignore file and return detailed report
        
        Args:
            verbose: Include detailed pattern analysis
            
        Returns:
            Validation report with patterns, errors, and suggestions
        """
        # Get all validation reports from the enhanced system
        all_reports = self._ignore_manager.validate_all()
        
        # Get the root .mcpignore report
        mcpignore_path = self.working_directory / IGNORE_FILENAME
        
        if mcpignore_path not in all_reports:
            return {
                "exists": False,
                "path": str(mcpignore_path),
                "error": "File not found"
            }
        
        info = all_reports[mcpignore_path]
        
        # Build report in the old format for backward compatibility
        report = {
            "exists": True,
            "path": str(mcpignore_path),
            "valid_patterns": [
                {"line": i+1, "pattern": p}
                for i, p in enumerate(info.valid_patterns)
            ],
            "invalid_patterns": [
                {
                    "line": err.line,
                    "pattern": err.pattern,
                    "error": err.message
                }
                for err in info.errors
            ],
            "warnings": [],
            "suggestions": [],
            "stats": info.stats
        }
        
        # Add warnings and suggestions in verbose mode
        if verbose and info.warnings:
            for warn in info.warnings:
                report["warnings"].append({
                    "line": warn.line,
                    "pattern": warn.pattern,
                    "warning": warn.message
                })
                
                # Extract suggestions from warning messages
                if "Consider using" in warn.message:
                    report["suggestions"].append({
                        "line": warn.line,
                        "pattern": warn.pattern,
                        "suggestion": warn.message
                    })
        
        return report
    
    # Additional methods for enhanced functionality
    
    def reload_ignore_files(self):
        """
        Reload all ignore files (useful after external changes)
        
        This exposes the hot-reload functionality of the enhanced system.
        """
        self._ignore_manager.reload_all()
        self.patterns = self._get_all_patterns()
        logger.info("Reloaded all ignore files")
    
    def notify_file_changed(self, file_path: str):
        """
        Notify the system that an ignore file has changed
        
        This enables hot-reloading when ignore files are modified.
        
        Args:
            file_path: Path to the changed ignore file
        """
        self._ignore_manager.notify_file_changed(file_path)
        # Update patterns for backward compatibility
        self.patterns = self._get_all_patterns()
        logger.info(f"Reloaded patterns after change to: {file_path}")