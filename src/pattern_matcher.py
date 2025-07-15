#!/usr/bin/env python3
"""
Pattern matching for file exclusions using gitignore-style patterns
"""

import logging
from pathlib import Path
from typing import List, Optional, Dict, Any, Tuple

import pathspec

logger = logging.getLogger("pattern-matcher")


class PatternMatcher:
    """Handles gitignore-style pattern matching for file exclusions"""
    
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
        self.patterns = self._load_all_patterns(custom_patterns)
        self.spec = self._compile_patterns(self.patterns)
    
    def _load_all_patterns(self, custom_patterns: Optional[List[str]]) -> List[str]:
        """Load patterns in priority order"""
        all_patterns = []
        
        # 1. Start with defaults
        all_patterns.extend(self.DEFAULT_EXCLUSIONS)
        
        # 2. Add .mcpignore patterns if file exists
        mcpignore_patterns = self._read_mcpignore()
        all_patterns.extend(mcpignore_patterns)
        
        # 3. Add any custom patterns from API
        if custom_patterns:
            all_patterns.extend(custom_patterns)
        
        # Remove duplicates while preserving order
        seen = set()
        unique_patterns = []
        for pattern in all_patterns:
            if pattern not in seen:
                seen.add(pattern)
                unique_patterns.append(pattern)
        
        logger.info(f"Loaded {len(unique_patterns)} unique exclusion patterns")
        logger.debug(f"All patterns: {unique_patterns}")
        return unique_patterns
    
    def _read_mcpignore(self) -> List[str]:
        """Read and validate patterns from .mcpignore file"""
        mcpignore_path = self.working_directory / ".mcpignore"
        if not mcpignore_path.exists():
            return []
        
        valid_patterns = []
        invalid_patterns = []
        warnings = []
        
        try:
            logger.info(f"Reading .mcpignore from: {mcpignore_path}")
            with open(mcpignore_path, 'r', encoding='utf-8') as f:
                for line_num, line in enumerate(f, 1):
                    original_line = line.rstrip('\n\r')
                    line = line.strip()
                    
                    # Skip empty lines and comments
                    if not line or line.startswith('#'):
                        continue
                    
                    # Check for common mistakes
                    if '\\' in line and not line.startswith('\\'):
                        warnings.append(
                            f"Line {line_num}: Pattern '{line}' contains backslash. "
                            "Use forward slashes for paths."
                        )
                    
                    if line.startswith('/') and len(line) > 1 and not line.startswith('/*'):
                        warnings.append(
                            f"Line {line_num}: Pattern '{line}' starts with /. "
                            "This only matches from the root. Did you mean '{line[1:]}'?"
                        )
                    
                    # Validate pattern
                    try:
                        # Test if pattern is valid by creating a temporary PathSpec
                        pathspec.PathSpec.from_lines('gitwildmatch', [line])
                        valid_patterns.append(line)
                        logger.debug(f"Added .mcpignore pattern: {line}")
                    except (pathspec.patterns.GitWildMatchPatternError, ValueError) as e:
                        invalid_patterns.append((line_num, line, str(e)))
                        logger.warning(
                            f".mcpignore line {line_num}: Invalid pattern '{line}' - {e}"
                        )
        
        except Exception as e:
            logger.error(f"Error reading .mcpignore: {e}")
            return []
        
        # Log warnings
        for warning in warnings:
            logger.warning(f".mcpignore: {warning}")
        
        # Log summary if there were errors
        if invalid_patterns:
            logger.warning(
                f"Found {len(invalid_patterns)} invalid patterns in .mcpignore, "
                f"continuing with {len(valid_patterns)} valid patterns"
            )
        
        # Store validation report for later use
        self._validation_report = {
            "valid_count": len(valid_patterns),
            "invalid_patterns": invalid_patterns,
            "warnings": warnings,
        }
        
        return valid_patterns
    
    def _compile_patterns(self, patterns: List[str]) -> Optional[pathspec.PathSpec]:
        """Compile patterns with individual error handling"""
        if not patterns:
            return None
        
        valid_patterns = []
        for pattern in patterns:
            try:
                # Validate each pattern individually
                pathspec.PathSpec.from_lines('gitwildmatch', [pattern])
                valid_patterns.append(pattern)
            except (pathspec.patterns.GitWildMatchPatternError, ValueError) as e:
                logger.warning(f"Skipping invalid pattern '{pattern}': {e}")
        
        if valid_patterns:
            try:
                return pathspec.PathSpec.from_lines('gitwildmatch', valid_patterns)
            except Exception as e:
                logger.error(f"Failed to compile patterns: {e}")
                return None
        return None
    
    def set_working_directory(self, working_directory: str):
        """
        Set the working directory for .mcpignore file lookup
        
        Args:
            working_directory: Path to the working directory
        """
        self.working_directory = Path(working_directory)
        logger.info(f"Set working directory to: {self.working_directory}")
        
        # Reload patterns with new working directory
        self.patterns = self._load_all_patterns(None)
        self.spec = self._compile_patterns(self.patterns)
        
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
        if not self.spec:
            return False
        
        # Convert to relative path from working directory
        try:
            path = Path(file_path)
            if path.is_absolute():
                path = path.relative_to(self.working_directory)
            
            # Check if path matches any exclusion pattern
            result = self.spec.match_file(str(path))
            logger.debug(f"Exclusion check for {path}: {result}")
            return result
        except Exception as e:
            logger.debug(f"Error checking exclusion for {file_path}: {e}")
            return False
    
    def get_ripgrep_args(self) -> List[str]:
        """
        Convert patterns to ripgrep --glob arguments
        
        Returns:
            List of ripgrep arguments for exclusion
        """
        args = []
        
        for pattern in self.patterns:
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
        mcpignore_path = Path.cwd() / ".mcpignore"
        if not mcpignore_path.exists():
            return {
                "exists": False,
                "path": str(mcpignore_path),
                "error": "File not found"
            }
        
        report = {
            "exists": True,
            "path": str(mcpignore_path),
            "valid_patterns": [],
            "invalid_patterns": [],
            "warnings": [],
            "suggestions": [],
            "stats": {
                "total_lines": 0,
                "comment_lines": 0,
                "empty_lines": 0,
                "pattern_lines": 0,
            }
        }
        
        try:
            with open(mcpignore_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            report["stats"]["total_lines"] = len(lines)
            
            for line_num, line in enumerate(lines, 1):
                original_line = line.rstrip('\n\r')
                stripped = line.strip()
                
                if not stripped:
                    report["stats"]["empty_lines"] += 1
                    continue
                
                if stripped.startswith('#'):
                    report["stats"]["comment_lines"] += 1
                    continue
                
                report["stats"]["pattern_lines"] += 1
                
                # Validate pattern
                try:
                    pathspec.PathSpec.from_lines('gitwildmatch', [stripped])
                    report["valid_patterns"].append({
                        "line": line_num,
                        "pattern": stripped
                    })
                except Exception as e:
                    report["invalid_patterns"].append({
                        "line": line_num,
                        "pattern": stripped,
                        "error": str(e)
                    })
                
                # Additional checks for verbose mode
                if verbose:
                    # Check for absolute paths
                    if stripped.startswith('/') and len(stripped) > 1:
                        report["warnings"].append({
                            "line": line_num,
                            "pattern": stripped,
                            "warning": "Absolute path - only matches from repository root"
                        })
                    
                    # Check for Windows-style paths
                    if '\\' in stripped and not stripped.startswith('\\'):
                        report["warnings"].append({
                            "line": line_num,
                            "pattern": stripped,
                            "warning": "Contains backslash - use forward slashes"
                        })
                    
                    # Check for overly broad patterns
                    if stripped in ['*', '**', '**/*']:
                        report["warnings"].append({
                            "line": line_num,
                            "pattern": stripped,
                            "warning": "Very broad pattern - will exclude many files"
                        })
                    
                    # Suggest improvements
                    if stripped.endswith('/') and not stripped.endswith('**/'):
                        report["suggestions"].append({
                            "line": line_num,
                            "pattern": stripped,
                            "suggestion": f"Consider using '{stripped}**' to match all contents"
                        })
        
        except Exception as e:
            report["error"] = f"Failed to read file: {e}"
        
        return report