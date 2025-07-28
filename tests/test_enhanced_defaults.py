#!/usr/bin/env python3
"""
Test the enhanced default exclusions and use_defaults option
"""

import tempfile
from pathlib import Path
import pytest

from src.ignore import IgnoreManager, IGNORE_FILENAME


def test_comprehensive_defaults(tmp_path):
    """Test that comprehensive default patterns work correctly"""
    manager = IgnoreManager(tmp_path)
    
    # Python artifacts
    assert manager.should_ignore(tmp_path / "__pycache__" / "module.pyc")
    assert manager.should_ignore(tmp_path / "dist" / "package.whl")
    assert manager.should_ignore(tmp_path / ".venv" / "bin" / "python")
    assert manager.should_ignore(tmp_path / "test.egg-info" / "PKG-INFO")
    
    # JavaScript/Node.js artifacts
    assert manager.should_ignore(tmp_path / "node_modules" / "react" / "index.js")
    assert manager.should_ignore(tmp_path / ".npm" / "cache" / "data")
    assert manager.should_ignore(tmp_path / "yarn-error.log")
    
    # React/Frontend build
    assert manager.should_ignore(tmp_path / "build" / "static" / "js" / "main.js")
    assert manager.should_ignore(tmp_path / ".next" / "server" / "pages.js")
    assert manager.should_ignore(tmp_path / "dist" / "bundle.js")
    
    # C/C++ build artifacts
    assert manager.should_ignore(tmp_path / "build" / "CMakeCache.txt")
    assert manager.should_ignore(tmp_path / "cmake-build-debug" / "output")
    assert manager.should_ignore(tmp_path / "main.o")
    assert manager.should_ignore(tmp_path / "libtest.so")
    assert manager.should_ignore(tmp_path / "app.exe")
    
    # IDE files
    assert manager.should_ignore(tmp_path / ".vscode" / "settings.json")
    assert manager.should_ignore(tmp_path / ".idea" / "modules.xml")
    
    # Media files
    assert manager.should_ignore(tmp_path / "screenshot.png")
    assert manager.should_ignore(tmp_path / "demo.mp4")
    assert manager.should_ignore(tmp_path / "presentation.pdf")
    
    # Environment files
    assert manager.should_ignore(tmp_path / ".env")
    assert manager.should_ignore(tmp_path / ".env.local")
    
    # But .env.example should NOT be ignored (negation pattern)
    assert not manager.should_ignore(tmp_path / ".env.example")
    
    # Source files should NOT be ignored
    assert not manager.should_ignore(tmp_path / "main.py")
    assert not manager.should_ignore(tmp_path / "app.js")
    assert not manager.should_ignore(tmp_path / "component.tsx")
    assert not manager.should_ignore(tmp_path / "main.cpp")


def test_disable_defaults(tmp_path):
    """Test that defaults can be disabled"""
    # Create manager without defaults
    manager = IgnoreManager(tmp_path, use_defaults=False)
    
    # Nothing should be ignored by default
    assert not manager.should_ignore(tmp_path / "__pycache__" / "module.pyc")
    assert not manager.should_ignore(tmp_path / "node_modules" / "package" / "index.js")
    assert not manager.should_ignore(tmp_path / "build" / "output.js")
    assert not manager.should_ignore(tmp_path / ".vscode" / "settings.json")


def test_custom_patterns_with_defaults(tmp_path):
    """Test adding custom patterns to defaults"""
    custom_patterns = ["*.custom", "custom_dir/**"]
    
    manager = IgnoreManager(
        tmp_path,
        default_patterns=custom_patterns,
        use_defaults=True
    )
    
    # Default patterns still work
    assert manager.should_ignore(tmp_path / "__pycache__" / "module.pyc")
    assert manager.should_ignore(tmp_path / "node_modules" / "package" / "index.js")
    
    # Custom patterns also work
    assert manager.should_ignore(tmp_path / "test.custom")
    assert manager.should_ignore(tmp_path / "custom_dir" / "file.txt")


def test_custom_patterns_without_defaults(tmp_path):
    """Test using only custom patterns"""
    custom_patterns = ["*.custom", "custom_dir/**"]
    
    manager = IgnoreManager(
        tmp_path,
        default_patterns=custom_patterns,
        use_defaults=False
    )
    
    # Default patterns should NOT work
    assert not manager.should_ignore(tmp_path / "__pycache__" / "module.pyc")
    assert not manager.should_ignore(tmp_path / "node_modules" / "package" / "index.js")
    
    # Only custom patterns work
    assert manager.should_ignore(tmp_path / "test.custom")
    assert manager.should_ignore(tmp_path / "custom_dir" / "file.txt")


def test_mcpignore_overrides_defaults(tmp_path):
    """Test that .mcpignore can override defaults with negation"""
    # Create .mcpignore that re-includes some default exclusions
    (tmp_path / IGNORE_FILENAME).write_text("""
# Re-include specific node_modules package
!node_modules/my-local-package/**

# Re-include specific build file
!build/config.json
""")
    
    manager = IgnoreManager(tmp_path)
    
    # Most node_modules still ignored
    assert manager.should_ignore(tmp_path / "node_modules" / "react" / "index.js")
    
    # But our local package is NOT ignored
    assert not manager.should_ignore(tmp_path / "node_modules" / "my-local-package" / "index.js")
    
    # Most build files still ignored
    assert manager.should_ignore(tmp_path / "build" / "output.js")
    
    # But config.json is NOT ignored
    assert not manager.should_ignore(tmp_path / "build" / "config.json")


def test_pattern_count_with_comprehensive_defaults():
    """Test that the comprehensive defaults are properly loaded"""
    with tempfile.TemporaryDirectory() as tmpdir:
        manager = IgnoreManager(tmpdir)
        
        # Get patterns at root level
        patterns = manager.get_patterns_for_path(Path(tmpdir))
        
        # Should have many patterns now
        assert len(patterns) > 100  # We added many more patterns
        
        # Check some specific patterns are present
        assert "node_modules/**" in patterns
        assert "build/**" in patterns
        assert "*.pyc" in patterns or "*.py[cod]" in patterns
        assert ".env" in patterns
        assert "!.env.example" in patterns  # Negation pattern


if __name__ == "__main__":
    pytest.main([__file__, "-v"])