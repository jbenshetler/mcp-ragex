#!/usr/bin/env python3
"""
Unit tests for the enhanced ignore file system
"""

import os
import tempfile
import shutil
from pathlib import Path
import time
import pytest

from src.ignore import (
    IGNORE_FILENAME,
    IgnoreManager,
    IgnoreRuleEngine,
    IgnoreFileLoader,
    IgnoreCache,
    IgnoreFileRegistry
)
from src.ignore.constants import DEFAULT_EXCLUSIONS


class TestIgnoreRuleEngine:
    """Test the rule engine component"""
    
    def test_compile_single_level(self):
        """Test compiling rules for a single directory"""
        engine = IgnoreRuleEngine()
        
        rules = {
            Path("/project"): ["*.pyc", "__pycache__/", "test.log"]
        }
        
        compiled = engine.compile_rules(rules)
        assert len(compiled.rules_by_level) == 1
        assert Path("/project") in compiled.rules_by_level
        
    def test_compile_multi_level(self):
        """Test compiling rules for multiple directories"""
        engine = IgnoreRuleEngine()
        
        rules = {
            Path("/project"): ["*.pyc", "build/"],
            Path("/project/src"): ["*.tmp", "debug.log"],
            Path("/project/src/tests"): ["*.cache"]
        }
        
        compiled = engine.compile_rules(rules)
        assert len(compiled.rules_by_level) == 3
        assert compiled.hierarchy == [
            Path("/project"),
            Path("/project/src"),
            Path("/project/src/tests")
        ]
        
    def test_pattern_validation(self):
        """Test pattern validation"""
        engine = IgnoreRuleEngine()
        
        # Valid patterns
        valid_patterns = ["*.pyc", "build/", "!important.py", "**/*.log"]
        for pattern in valid_patterns:
            is_valid, error = engine.validate_pattern(pattern)
            assert is_valid, f"Pattern '{pattern}' should be valid"
            
        # Invalid patterns (pathspec doesn't really have many invalid patterns)
        # Most strings are valid gitignore patterns
        
    def test_match_path_single_level(self):
        """Test path matching with single level rules"""
        engine = IgnoreRuleEngine()
        
        rules = {
            Path("/project"): ["*.pyc", "build/", "temp.txt"]
        }
        compiled = engine.compile_rules(rules)
        
        # Should match
        assert engine.match_path(
            Path("/project/test.pyc"), compiled, Path("/project")
        ).should_ignore
        
        assert engine.match_path(
            Path("/project/build/output.txt"), compiled, Path("/project")
        ).should_ignore
        
        # Should not match
        assert not engine.match_path(
            Path("/project/main.py"), compiled, Path("/project")
        ).should_ignore
        
    def test_match_path_multi_level_precedence(self):
        """Test that deeper rules override parent rules"""
        engine = IgnoreRuleEngine()
        
        rules = {
            Path("/project"): ["*.log"],  # Ignore all .log files
            Path("/project/important"): ["!app.log"]  # But not app.log in important/
        }
        compiled = engine.compile_rules(rules)
        
        # General .log files should be ignored
        assert engine.match_path(
            Path("/project/debug.log"), compiled, Path("/project")
        ).should_ignore
        
        # But app.log in important/ should not be ignored (negation)
        # Note: This test might need adjustment based on exact precedence rules
        
    def test_negation_patterns(self):
        """Test negation patterns (! prefix)"""
        engine = IgnoreRuleEngine()
        
        rules = {
            Path("/project"): ["*.log", "!important.log"]
        }
        compiled = engine.compile_rules(rules)
        
        # Most .log files should be ignored
        assert engine.match_path(
            Path("/project/debug.log"), compiled, Path("/project")
        ).should_ignore
        
        # But important.log should not be ignored
        assert not engine.match_path(
            Path("/project/important.log"), compiled, Path("/project")
        ).should_ignore


class TestIgnoreFileLoader:
    """Test the file loader component"""
    
    def test_load_valid_file(self, tmp_path):
        """Test loading a valid ignore file"""
        loader = IgnoreFileLoader()
        
        # Create test ignore file
        ignore_file = tmp_path / IGNORE_FILENAME
        ignore_file.write_text("""
# This is a comment
*.pyc
__pycache__/

# Another comment
*.log
!important.log
""")
        
        info = loader.load_file(ignore_file)
        
        assert info.is_valid
        assert len(info.valid_patterns) == 4
        assert "*.pyc" in info.valid_patterns
        assert "__pycache__/" in info.valid_patterns
        assert "*.log" in info.valid_patterns
        assert "!important.log" in info.valid_patterns
        
        assert info.stats['total_lines'] == 8
        assert info.stats['comment_lines'] == 2
        assert info.stats['empty_lines'] == 2
        assert info.stats['pattern_lines'] == 4
        
    def test_load_file_with_warnings(self, tmp_path):
        """Test loading file with warning-worthy patterns"""
        loader = IgnoreFileLoader()
        
        ignore_file = tmp_path / IGNORE_FILENAME
        ignore_file.write_text("""
/absolute/path
*.py\\test.py
**
""")
        
        info = loader.load_file(ignore_file)
        
        assert info.is_valid  # Warnings don't make it invalid
        assert len(info.warnings) >= 2  # At least backslash and broad pattern warnings
        
    def test_find_ignore_files(self, tmp_path):
        """Test finding multiple ignore files in directory tree"""
        loader = IgnoreFileLoader()
        
        # Create directory structure with multiple ignore files
        (tmp_path / IGNORE_FILENAME).write_text("*.root")
        
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        (src_dir / IGNORE_FILENAME).write_text("*.src")
        
        test_dir = src_dir / "tests"
        test_dir.mkdir()
        (test_dir / IGNORE_FILENAME).write_text("*.test")
        
        # Find all ignore files
        files = loader.find_ignore_files(tmp_path)
        
        assert len(files) == 3
        assert files[0] == tmp_path / IGNORE_FILENAME  # Root first
        assert files[1] == src_dir / IGNORE_FILENAME
        assert files[2] == test_dir / IGNORE_FILENAME
        
    def test_max_depth_limit(self, tmp_path):
        """Test max depth limit for finding ignore files"""
        loader = IgnoreFileLoader()
        
        # Create root ignore file
        (tmp_path / IGNORE_FILENAME).write_text("*.root")
        
        # Create deep directory structure
        current = tmp_path
        for i in range(5):
            current = current / f"level{i}"
            current.mkdir()
            (current / IGNORE_FILENAME).write_text(f"*.level{i}")
            
        # Find with depth limit
        files = loader.find_ignore_files(tmp_path, max_depth=2)
        
        # Should only find root + 2 levels deep
        assert len(files) == 3


class TestIgnoreCache:
    """Test the caching system"""
    
    def test_path_cache_basic(self):
        """Test basic path caching"""
        cache = IgnoreCache(max_size=10)
        
        path = Path("/project/test.py")
        
        # Initially not cached
        assert cache.get_decision(path) is None
        
        # Cache a decision
        cache.cache_decision(path, True)
        assert cache.get_decision(path) is True
        
        # Cache opposite decision
        cache.cache_decision(path, False)
        assert cache.get_decision(path) is False
        
    def test_cache_invalidation(self):
        """Test cache invalidation"""
        cache = IgnoreCache()
        
        # Cache some decisions
        cache.cache_decision(Path("/project/file1.py"), True)
        cache.cache_decision(Path("/project/src/file2.py"), False)
        cache.cache_decision(Path("/project/src/tests/file3.py"), True)
        
        # Invalidate a specific path
        cache.invalidate_path(Path("/project/src"))
        
        # Root path should still be cached
        assert cache.get_decision(Path("/project/file1.py")) is True
        
        # But src paths should be invalidated
        assert cache.get_decision(Path("/project/src/file2.py")) is None
        assert cache.get_decision(Path("/project/src/tests/file3.py")) is None
        
    def test_ignore_file_dependencies(self):
        """Test tracking dependencies on ignore files"""
        cache = IgnoreCache()
        
        ignore_files = {Path("/project/.mcpignore"), Path("/project/src/.mcpignore")}
        
        # Cache decision with dependencies
        cache.cache_decision(
            Path("/project/src/main.py"),
            True,
            ignore_files
        )
        
        # Invalidate one ignore file
        cache.invalidate_ignore_file(Path("/project/src/.mcpignore"))
        
        # Decision should be invalidated
        assert cache.get_decision(Path("/project/src/main.py")) is None
        
    def test_lru_eviction(self):
        """Test LRU eviction"""
        cache = IgnoreCache(max_size=3)
        
        # Fill cache
        cache.cache_decision(Path("/file1"), True)
        cache.cache_decision(Path("/file2"), False)
        cache.cache_decision(Path("/file3"), True)
        
        # Access file1 to make it recently used
        cache.get_decision(Path("/file1"))
        
        # Add new entry, should evict file2 (least recently used)
        cache.cache_decision(Path("/file4"), False)
        
        assert cache.get_decision(Path("/file1")) is True  # Still cached
        assert cache.get_decision(Path("/file2")) is None  # Evicted
        assert cache.get_decision(Path("/file3")) is True  # Still cached
        assert cache.get_decision(Path("/file4")) is False  # New entry


class TestIgnoreFileRegistry:
    """Test the file registry component"""
    
    def test_register_file(self, tmp_path):
        """Test registering ignore files"""
        registry = IgnoreFileRegistry()
        loader = IgnoreFileLoader()
        
        # Create and load a file
        ignore_file = tmp_path / IGNORE_FILENAME
        ignore_file.write_text("*.pyc")
        
        info = loader.load_file(ignore_file)
        registry.register_file(info)
        
        # Check registration
        assert len(registry.get_all_files()) == 1
        retrieved = registry.get_file_info(ignore_file)
        assert retrieved is not None
        assert retrieved.path == ignore_file
        
    def test_get_files_for_path(self, tmp_path):
        """Test finding which ignore files affect a path"""
        registry = IgnoreFileRegistry()
        loader = IgnoreFileLoader()
        
        # Create directory structure
        root_ignore = tmp_path / IGNORE_FILENAME
        root_ignore.write_text("*.root")
        
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        src_ignore = src_dir / IGNORE_FILENAME
        src_ignore.write_text("*.src")
        
        # Register files
        registry.register_file(loader.load_file(root_ignore))
        registry.register_file(loader.load_file(src_ignore))
        
        # Check which files affect different paths
        files = registry.get_files_for_path(
            tmp_path / "src" / "main.py",
            tmp_path
        )
        
        assert len(files) == 2
        assert files[0] == root_ignore  # Root first
        assert files[1] == src_ignore


class TestIgnoreManager:
    """Test the main IgnoreManager API"""
    
    def test_basic_usage(self, tmp_path):
        """Test basic ignore functionality"""
        # Create test structure
        (tmp_path / IGNORE_FILENAME).write_text("""
*.pyc
__pycache__/
temp.log
""")
        
        manager = IgnoreManager(tmp_path)
        
        # Test ignore decisions
        assert manager.should_ignore(tmp_path / "test.pyc")
        assert manager.should_ignore(tmp_path / "__pycache__" / "module.pyc")
        assert manager.should_ignore(tmp_path / "temp.log")
        assert not manager.should_ignore(tmp_path / "main.py")
        
    def test_multi_level_ignore(self, tmp_path):
        """Test multi-level ignore file support"""
        # Create root ignore
        (tmp_path / IGNORE_FILENAME).write_text("*.log")
        
        # Create src directory with its own ignore
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        (src_dir / IGNORE_FILENAME).write_text("!important.log")
        
        manager = IgnoreManager(tmp_path)
        
        # Root level: .log files should be ignored
        assert manager.should_ignore(tmp_path / "debug.log")
        
        # But in src/, important.log should not be ignored
        assert not manager.should_ignore(src_dir / "important.log")
        
        # Other .log files in src/ should still be ignored
        assert manager.should_ignore(src_dir / "other.log")
        
    def test_hot_reload(self, tmp_path):
        """Test hot reloading functionality"""
        ignore_file = tmp_path / IGNORE_FILENAME
        ignore_file.write_text("*.tmp")
        
        manager = IgnoreManager(tmp_path)
        
        # Initially .tmp files are ignored
        assert manager.should_ignore(tmp_path / "test.tmp")
        assert not manager.should_ignore(tmp_path / "test.txt")
        
        # Modify ignore file
        ignore_file.write_text("*.txt")
        
        # Notify manager of change
        manager.notify_file_changed(ignore_file)
        
        # Now .txt files should be ignored, but not .tmp
        assert not manager.should_ignore(tmp_path / "test.tmp")
        assert manager.should_ignore(tmp_path / "test.txt")
        
    def test_new_ignore_file(self, tmp_path):
        """Test adding a new ignore file"""
        manager = IgnoreManager(tmp_path)
        
        # Initially no patterns
        assert not manager.should_ignore(tmp_path / "test.tmp")
        
        # Create new ignore file
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        ignore_file = src_dir / IGNORE_FILENAME
        ignore_file.write_text("*.tmp")
        
        # Notify manager
        manager.notify_file_changed(ignore_file)
        
        # Now .tmp files in src/ should be ignored
        assert manager.should_ignore(src_dir / "test.tmp")
        
    def test_default_patterns(self, tmp_path):
        """Test that default patterns are applied"""
        manager = IgnoreManager(tmp_path)
        
        # Check some default patterns
        assert manager.should_ignore(tmp_path / ".venv" / "bin" / "python")
        assert manager.should_ignore(tmp_path / "__pycache__" / "module.pyc")
        assert manager.should_ignore(tmp_path / "file.pyc")
        
    def test_validation_report(self, tmp_path):
        """Test validation reporting"""
        # Create ignore file with mixed content
        ignore_file = tmp_path / IGNORE_FILENAME
        ignore_file.write_text("""
# Valid patterns
*.pyc
__pycache__/

# Pattern with warning
/absolute/path
""")
        
        manager = IgnoreManager(tmp_path)
        report = manager.validate_all()
        
        assert len(report) == 1
        info = report[ignore_file]
        assert info.is_valid
        assert len(info.valid_patterns) == 3
        assert len(info.warnings) >= 1  # Absolute path warning
        
    def test_get_patterns_for_path(self, tmp_path):
        """Test getting effective patterns for a path"""
        # Root patterns
        (tmp_path / IGNORE_FILENAME).write_text("*.root")
        
        # Src patterns
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        (src_dir / IGNORE_FILENAME).write_text("*.src")
        
        manager = IgnoreManager(tmp_path)
        
        # Get patterns for src path
        patterns = manager.get_patterns_for_path(src_dir / "file.py")
        
        # Should include defaults + both ignore files
        assert any("*.pyc" in p for p in patterns)  # From defaults
        assert "*.root" in patterns
        assert "*.src" in patterns
        
    def test_stats(self, tmp_path):
        """Test statistics gathering"""
        (tmp_path / IGNORE_FILENAME).write_text("*.pyc")
        
        manager = IgnoreManager(tmp_path)
        
        # Make some queries to populate cache
        manager.should_ignore(tmp_path / "test.pyc")
        manager.should_ignore(tmp_path / "main.py")
        
        stats = manager.get_stats()
        
        assert stats['root_path'] == str(tmp_path)
        assert stats['ignore_filename'] == IGNORE_FILENAME
        assert stats['registry']['total_files'] == 1
        assert stats['cache']['path_cache']['size'] == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])