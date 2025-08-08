"""
Rule engine for pattern compilation and matching with multi-level support
"""

from pathlib import Path
from typing import List, Dict, Optional, Set, Tuple
from dataclasses import dataclass

import pathspec
from src.utils import get_logger

logger = get_logger(__name__)


@dataclass
class MatchResult:
    """Result of matching a path against ignore rules"""
    should_ignore: bool
    matched_pattern: Optional[str] = None
    matched_file: Optional[Path] = None
    rule_level: int = 0  # Higher numbers = more specific (deeper) rules


@dataclass
class CompiledRules:
    """Compiled rules organized by directory level"""
    rules_by_level: Dict[Path, pathspec.PathSpec]
    pattern_origins: Dict[str, Path]  # Maps patterns to their source file
    hierarchy: List[Path]  # Ordered from root to most specific
    patterns_by_level: Dict[Path, List[str]]  # Original patterns for each level


class IgnoreRuleEngine:
    """
    Handles pattern compilation and path matching with multi-level precedence
    """
    
    def __init__(self):
        self._compiled_cache: Dict[str, pathspec.PathSpec] = {}
    
    def compile_rules(self, rules_by_level: Dict[Path, List[str]]) -> CompiledRules:
        """
        Compile multi-level rules into efficient matcher
        
        Args:
            rules_by_level: Dictionary mapping directory paths to their patterns
            
        Returns:
            CompiledRules object with compiled patterns
        """
        compiled_rules = {}
        pattern_origins = {}
        
        # Sort paths by depth (root first)
        sorted_paths = sorted(rules_by_level.keys(), key=lambda p: len(p.parts))
        
        for path in sorted_paths:
            patterns = rules_by_level[path]
            if not patterns:
                continue
                
            try:
                # Compile patterns for this level
                spec = self._compile_patterns(patterns)
                if spec:
                    compiled_rules[path] = spec
                    # Track which file each pattern came from
                    for pattern in patterns:
                        pattern_origins[pattern] = path
                        
            except Exception as e:
                logger.error(f"Failed to compile patterns for {path}: {e}")
                
        return CompiledRules(
            rules_by_level=compiled_rules,
            pattern_origins=pattern_origins,
            hierarchy=sorted_paths,
            patterns_by_level=rules_by_level
        )
    
    def match_path(self, path: Path, compiled_rules: CompiledRules, 
                   base_path: Path) -> MatchResult:
        """
        Match path against compiled rules with precedence
        
        Args:
            path: Path to check (absolute or relative)
            compiled_rules: Compiled rules from compile_rules()
            base_path: Base path for resolving relative paths
            
        Returns:
            MatchResult with decision and matched pattern info
        """
        # Convert to absolute path if needed
        if not path.is_absolute():
            path = base_path / path
            
        # Find all applicable rule files (from root to path's parent)
        applicable_rules = []
        current = path.parent
        
        while current >= base_path:
            if current in compiled_rules.rules_by_level:
                applicable_rules.append(current)
            if current == base_path:
                break
            current = current.parent
            
        # Apply rules from most general to most specific
        # Later rules can override earlier ones
        matched_pattern = None
        matched_file = None
        should_ignore = False
        rule_level = 0
        
        for rule_path in sorted(applicable_rules):
            spec = compiled_rules.rules_by_level[rule_path]
            
            # Get relative path from rule directory
            try:
                rel_path = path.relative_to(rule_path)
            except ValueError:
                continue
                
            # Check if path matches any pattern at this level
            if spec.match_file(str(rel_path)):
                should_ignore = True
                matched_file = rule_path
                rule_level = len(rule_path.parts)
                
                # Find which specific pattern matched
                # This is more expensive but useful for debugging
                # Note: PathSpec doesn't expose the original patterns directly
                # so we'll track them separately or skip this for now
                matched_pattern = f"(matched at {rule_path})"
                        
        # Handle negation patterns (! prefix)
        # These are processed in order and can re-include files
        for rule_path in sorted(applicable_rules):
            if rule_path not in compiled_rules.patterns_by_level:
                continue
                
            patterns = compiled_rules.patterns_by_level[rule_path]
            try:
                rel_path = path.relative_to(rule_path)
            except ValueError:
                continue
                
            # Check negation patterns
            for pattern in patterns:
                if pattern.startswith('!'):
                    # Remove ! and check if it matches
                    include_pattern = pattern[1:]
                    include_spec = pathspec.PathSpec.from_lines('gitwildmatch', [include_pattern])
                    if include_spec.match_file(str(rel_path)):
                        should_ignore = False
                        matched_pattern = pattern
                        matched_file = rule_path
                        rule_level = len(rule_path.parts)
                        
        return MatchResult(
            should_ignore=should_ignore,
            matched_pattern=matched_pattern,
            matched_file=matched_file,
            rule_level=rule_level
        )
    
    def validate_pattern(self, pattern: str) -> Tuple[bool, Optional[str]]:
        """
        Validate a single pattern
        
        Args:
            pattern: Pattern to validate
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            # Handle negation
            test_pattern = pattern[1:] if pattern.startswith('!') else pattern
            pathspec.PathSpec.from_lines('gitwildmatch', [test_pattern])
            return True, None
        except Exception as e:
            return False, str(e)
    
    def get_effective_patterns(self, path: Path, compiled_rules: CompiledRules,
                             base_path: Path) -> List[str]:
        """
        Get all patterns that would apply to a given path
        
        Args:
            path: Path to check
            compiled_rules: Compiled rules
            base_path: Base path
            
        Returns:
            List of patterns in order of precedence
        """
        patterns = []
        
        # Find applicable rule files
        current = path if path.is_dir() else path.parent
        while current >= base_path:
            if current in compiled_rules.patterns_by_level:
                patterns.extend(compiled_rules.patterns_by_level[current])
            if current == base_path:
                break
            current = current.parent
            
        return patterns
    
    def _compile_patterns(self, patterns: List[str]) -> Optional[pathspec.PathSpec]:
        """
        Compile a list of patterns with caching
        
        Args:
            patterns: List of gitignore-style patterns
            
        Returns:
            Compiled PathSpec or None if no valid patterns
        """
        if not patterns:
            return None
            
        # Create cache key from patterns
        cache_key = '\n'.join(sorted(patterns))
        
        # Check cache
        if cache_key in self._compiled_cache:
            return self._compiled_cache[cache_key]
            
        # Validate and compile patterns
        valid_patterns = []
        for pattern in patterns:
            is_valid, error = self.validate_pattern(pattern)
            if is_valid:
                valid_patterns.append(pattern)
            else:
                logger.warning(f"Skipping invalid pattern '{pattern}': {error}")
                
        if not valid_patterns:
            return None
            
        try:
            spec = pathspec.PathSpec.from_lines('gitwildmatch', valid_patterns)
            self._compiled_cache[cache_key] = spec
            return spec
        except Exception as e:
            logger.error(f"Failed to compile patterns: {e}")
            return None
    
    def clear_cache(self):
        """Clear the compiled pattern cache"""
        self._compiled_cache.clear()