"""
File loader for parsing and validating ignore files
"""

import os
import logging
from pathlib import Path
from typing import List, Optional, Dict, Any, Tuple
from dataclasses import dataclass, field

from .constants import IGNORE_FILENAME, MAX_IGNORE_FILE_SIZE, MAX_PATTERNS_PER_FILE

logger = logging.getLogger(__name__)


@dataclass
class ValidationError:
    """Represents a validation error in an ignore file"""
    line: int
    pattern: str
    message: str


@dataclass
class ValidationWarning:
    """Represents a validation warning in an ignore file"""
    line: int
    pattern: str
    message: str


@dataclass
class IgnoreFileInfo:
    """Information about a loaded ignore file"""
    path: Path
    patterns: List[str]
    valid_patterns: List[str]
    errors: List[ValidationError] = field(default_factory=list)
    warnings: List[ValidationWarning] = field(default_factory=list)
    stats: Dict[str, int] = field(default_factory=dict)
    
    @property
    def is_valid(self) -> bool:
        """Check if file has no errors"""
        return len(self.errors) == 0
    
    @property
    def has_warnings(self) -> bool:
        """Check if file has warnings"""
        return len(self.warnings) > 0


class IgnoreFileLoader:
    """
    Handles loading, parsing, and validating ignore files
    """
    
    def __init__(self, ignore_filename: str = IGNORE_FILENAME):
        """
        Initialize loader
        
        Args:
            ignore_filename: Name of ignore files to look for
        """
        self.ignore_filename = ignore_filename
    
    def load_file(self, file_path: Path) -> IgnoreFileInfo:
        """
        Load and validate an ignore file
        
        Args:
            file_path: Path to the ignore file
            
        Returns:
            IgnoreFileInfo with patterns and validation results
        """
        info = IgnoreFileInfo(
            path=file_path,
            patterns=[],
            valid_patterns=[],
            stats={
                'total_lines': 0,
                'empty_lines': 0,
                'comment_lines': 0,
                'pattern_lines': 0,
            }
        )
        
        # Check file exists
        if not file_path.exists():
            info.errors.append(ValidationError(
                line=0,
                pattern="",
                message=f"File not found: {file_path}"
            ))
            return info
            
        # Check file size
        try:
            file_size = file_path.stat().st_size
            if file_size > MAX_IGNORE_FILE_SIZE:
                info.errors.append(ValidationError(
                    line=0,
                    pattern="",
                    message=f"File too large: {file_size} bytes (max: {MAX_IGNORE_FILE_SIZE})"
                ))
                return info
        except Exception as e:
            info.errors.append(ValidationError(
                line=0,
                pattern="",
                message=f"Cannot stat file: {e}"
            ))
            return info
            
        # Load and parse file
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                
            info.stats['total_lines'] = len(lines)
            
            for line_num, line in enumerate(lines, 1):
                original_line = line.rstrip('\n\r')
                stripped = line.strip()
                
                # Handle empty lines
                if not stripped:
                    info.stats['empty_lines'] += 1
                    continue
                    
                # Handle comments
                if stripped.startswith('#'):
                    info.stats['comment_lines'] += 1
                    continue
                    
                info.stats['pattern_lines'] += 1
                info.patterns.append(stripped)
                
                # Validate pattern
                is_valid, validation_msg = self._validate_pattern(stripped)
                
                if is_valid:
                    info.valid_patterns.append(stripped)
                else:
                    info.errors.append(ValidationError(
                        line=line_num,
                        pattern=stripped,
                        message=validation_msg or "Invalid pattern"
                    ))
                    
                # Check for warnings
                warnings = self._check_pattern_warnings(stripped)
                for warning_msg in warnings:
                    info.warnings.append(ValidationWarning(
                        line=line_num,
                        pattern=stripped,
                        message=warning_msg
                    ))
                    
            # Check total pattern count
            if len(info.valid_patterns) > MAX_PATTERNS_PER_FILE:
                info.errors.append(ValidationError(
                    line=0,
                    pattern="",
                    message=f"Too many patterns: {len(info.valid_patterns)} (max: {MAX_PATTERNS_PER_FILE})"
                ))
                # Truncate to max
                info.valid_patterns = info.valid_patterns[:MAX_PATTERNS_PER_FILE]
                
        except Exception as e:
            info.errors.append(ValidationError(
                line=0,
                pattern="",
                message=f"Error reading file: {e}"
            ))
            
        return info
    
    def find_ignore_files(self, root_path: Path, 
                         max_depth: Optional[int] = None) -> List[Path]:
        """
        Find all ignore files under a root path
        
        Args:
            root_path: Root directory to search from
            max_depth: Maximum directory depth to search (None = unlimited)
            
        Returns:
            List of paths to ignore files, ordered from root to leaves
        """
        ignore_files = []
        
        # Check root first
        root_ignore = root_path / self.ignore_filename
        if root_ignore.exists():
            ignore_files.append(root_ignore)
            
        # Walk directory tree
        for dirpath, dirnames, filenames in os.walk(root_path):
            dirpath = Path(dirpath)
            
            # Skip root (already checked)
            if dirpath == root_path:
                continue
                
            # Check depth limit
            if max_depth is not None:
                depth = len(dirpath.relative_to(root_path).parts)
                if depth > max_depth:
                    dirnames[:] = []  # Don't recurse deeper
                    continue
                    
            # Check for ignore file
            ignore_path = dirpath / self.ignore_filename
            if ignore_path.exists():
                ignore_files.append(ignore_path)
                
        # Sort by path depth (root first)
        ignore_files.sort(key=lambda p: len(p.parts))
        
        return ignore_files
    
    def _validate_pattern(self, pattern: str) -> Tuple[bool, Optional[str]]:
        """
        Validate a single pattern
        
        Args:
            pattern: Pattern to validate
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        # Import here to avoid circular dependency
        from .rule_engine import IgnoreRuleEngine
        engine = IgnoreRuleEngine()
        return engine.validate_pattern(pattern)
    
    def _check_pattern_warnings(self, pattern: str) -> List[str]:
        """
        Check pattern for potential issues that aren't errors
        
        Args:
            pattern: Pattern to check
            
        Returns:
            List of warning messages
        """
        warnings = []
        
        # Check for backslashes (Windows paths)
        if '\\' in pattern and not pattern.startswith('\\'):
            warnings.append(
                "Pattern contains backslash. Use forward slashes for paths."
            )
            
        # Check for absolute paths
        if pattern.startswith('/') and len(pattern) > 1 and not pattern.startswith('/*'):
            warnings.append(
                f"Pattern starts with /. This only matches from root. "
                f"Did you mean '{pattern[1:]}'?"
            )
            
        # Check for overly broad patterns
        if pattern in ['*', '**', '**/*']:
            warnings.append(
                "Very broad pattern - will exclude many files"
            )
            
        # Check for trailing slashes without **
        if pattern.endswith('/') and not pattern.endswith('**/'):
            warnings.append(
                f"Consider using '{pattern}**' to match all contents"
            )
            
        # Check for common typos
        if pattern.startswith('*.') and '/' in pattern:
            warnings.append(
                "Extension pattern with path separator - this may not work as expected"
            )
            
        return warnings
    
    def merge_patterns(self, *pattern_lists: List[str]) -> List[str]:
        """
        Merge multiple pattern lists, removing duplicates while preserving order
        
        Args:
            *pattern_lists: Variable number of pattern lists
            
        Returns:
            Merged list with duplicates removed
        """
        seen = set()
        merged = []
        
        for patterns in pattern_lists:
            for pattern in patterns:
                if pattern not in seen:
                    seen.add(pattern)
                    merged.append(pattern)
                    
        return merged