"""
Backward compatibility wrapper for PatternMatcher
"""

from pathlib import Path
from typing import List, Optional, Dict, Any

from ..pattern_matcher import PatternMatcher
from .manager import IgnoreManager
from .constants import DEFAULT_EXCLUSIONS
from src.utils import get_logger

logger = get_logger(__name__)


class EnhancedPatternMatcher(PatternMatcher):
    """
    Drop-in replacement for PatternMatcher using the new ignore system
    
    This provides backward compatibility while using the enhanced
    multi-level ignore file system under the hood.
    """
    
    def __init__(self, custom_patterns: Optional[List[str]] = None):
        """
        Initialize enhanced pattern matcher
        
        Args:
            custom_patterns: Additional patterns to include (from API)
        """
        # Initialize parent for compatibility
        # We override most methods, so parent init is minimal
        self._validation_report = None
        self.working_directory = Path.cwd()
        self.patterns = []  # Will be populated by ignore manager
        self.spec = None  # Not used in enhanced version
        
        # Custom patterns from API
        self._custom_patterns = custom_patterns or []
        
        # Initialize the enhanced ignore manager
        self._init_ignore_manager()
        
    def _init_ignore_manager(self):
        """Initialize the enhanced ignore manager"""
        # Combine default patterns with custom patterns
        all_default_patterns = DEFAULT_EXCLUSIONS.copy()
        if self._custom_patterns:
            all_default_patterns.extend(self._custom_patterns)
            
        # Create ignore manager - always use defaults for backward compatibility
        self._ignore_manager = IgnoreManager(
            root_path=self.working_directory,
            default_patterns=self._custom_patterns,  # Custom patterns are added to defaults
            auto_discover=True,
            use_defaults=True  # Always use defaults for compatibility
        )
        
        # Update patterns list for compatibility
        self.patterns = self._ignore_manager.get_patterns_for_path(self.working_directory)
        
    def set_working_directory(self, working_directory: str):
        """
        Set the working directory for .gitignore file lookup
        
        Args:
            working_directory: Path to the working directory
        """
        self.working_directory = Path(working_directory)
        logger.debug(f"Set working directory to: {self.working_directory}")
        
        # Reinitialize ignore manager with new directory
        self._init_ignore_manager()
        
    def should_exclude(self, file_path: str) -> bool:
        """
        Check if a file should be excluded based on patterns
        
        Args:
            file_path: Path to check (relative or absolute)
            
        Returns:
            True if file should be excluded, False otherwise
        """
        return self._ignore_manager.should_ignore(file_path)
        
    def get_ripgrep_args(self) -> List[str]:
        """
        Convert patterns to ripgrep --glob arguments
        
        Returns:
            List of ripgrep arguments for exclusion
        """
        args = []
        
        # Get all patterns that apply at root level
        patterns = self._ignore_manager.get_patterns_for_path(self.working_directory)
        
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
        """Get detailed validation report from .gitignore parsing"""
        # Get validation for all ignore files
        all_reports = self._ignore_manager.validate_all()
        
        # Find the root .gitignore file
        root_ignore = self.working_directory / self._ignore_manager.ignore_filename
        
        if root_ignore in all_reports:
            info = all_reports[root_ignore]
            return {
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
            
        return None
        
    def validate_gitignore(self, verbose: bool = False) -> Dict[str, Any]:
        """
        Validate .gitignore file and return detailed report
        
        Args:
            verbose: Include detailed pattern analysis
            
        Returns:
            Validation report with patterns, errors, and suggestions
        """
        # Get all validation reports
        all_reports = self._ignore_manager.validate_all()
        
        # Build combined report
        gitignore_path = self.working_directory / self._ignore_manager.ignore_filename
        
        if gitignore_path not in all_reports:
            return {
                "exists": False,
                "path": str(gitignore_path),
                "error": "File not found"
            }
            
        info = all_reports[gitignore_path]
        
        report = {
            "exists": True,
            "path": str(gitignore_path),
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
            "warnings": [
                {
                    "line": warn.line,
                    "pattern": warn.pattern,
                    "warning": warn.message
                }
                for warn in info.warnings
            ] if verbose else [],
            "suggestions": [],  # Could add suggestions based on warnings
            "stats": info.stats
        }
        
        # Add suggestions in verbose mode
        if verbose and info.warnings:
            for warn in info.warnings:
                if "Consider using" in warn.message:
                    report["suggestions"].append({
                        "line": warn.line,
                        "pattern": warn.pattern,
                        "suggestion": warn.message
                    })
                    
        return report
        
    # Additional methods for enhanced functionality
    
    def reload_ignore_files(self):
        """Reload all ignore files (useful after external changes)"""
        self._ignore_manager.reload_all()
        self.patterns = self._ignore_manager.get_patterns_for_path(self.working_directory)
        
    def notify_file_changed(self, file_path: str):
        """
        Notify the system that an ignore file has changed
        
        Args:
            file_path: Path to the changed ignore file
        """
        self._ignore_manager.notify_file_changed(file_path)
        # Update patterns for compatibility
        self.patterns = self._ignore_manager.get_patterns_for_path(self.working_directory)
