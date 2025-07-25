#!/usr/bin/env python3
"""
Test the hybrid approach with warnings and init functionality
"""

import os
import tempfile
from pathlib import Path
import logging
import pytest

from src.ignore import IgnoreManager, IGNORE_FILENAME, init_ignore_file, generate_ignore_content


class TestHybridApproach:
    """Test the hybrid approach with warnings and file generation"""
    
    def test_warning_when_no_mcpignore(self, tmp_path, caplog):
        """Test that warning is shown when no .mcpignore exists"""
        # Ensure no .mcpignore exists
        assert not (tmp_path / IGNORE_FILENAME).exists()
        
        # Create manager with default logging
        with caplog.at_level(logging.WARNING):
            manager = IgnoreManager(tmp_path)
        
        # Check warning was logged
        assert any(
            "No .mcpignore found" in record.message and 
            "ragex init" in record.message
            for record in caplog.records
        )
        
        # But manager still works with defaults
        assert manager.should_ignore(tmp_path / "__pycache__" / "test.pyc")
    
    def test_no_warning_when_mcpignore_exists(self, tmp_path, caplog):
        """Test that no warning is shown when .mcpignore exists"""
        # Create .mcpignore
        (tmp_path / IGNORE_FILENAME).write_text("*.test")
        
        # Create manager
        with caplog.at_level(logging.WARNING):
            manager = IgnoreManager(tmp_path)
        
        # No warning about missing file
        assert not any(
            "No .mcpignore found" in record.message
            for record in caplog.records
        )
    
    def test_warning_disabled_by_env_var(self, tmp_path, caplog, monkeypatch):
        """Test that warning can be disabled by environment variable"""
        # Test various false values
        for false_value in ['false', 'False', 'FALSE', '0', 'no', 'off']:
            # Clear any previous logs
            caplog.clear()
            
            # Set environment variable
            monkeypatch.setenv('RAGEX_IGNOREFILE_WARNING', false_value)
            
            # Create manager
            with caplog.at_level(logging.WARNING):
                manager = IgnoreManager(tmp_path)
            
            # No warning should be logged
            assert not any(
                "No .mcpignore found" in record.message
                for record in caplog.records
            ), f"Warning shown with RAGEX_IGNOREFILE_WARNING={false_value}"
    
    def test_warning_enabled_by_default(self, tmp_path, caplog, monkeypatch):
        """Test that warning is enabled by default or with non-false values"""
        # Test default (no env var)
        monkeypatch.delenv('RAGEX_IGNOREFILE_WARNING', raising=False)
        
        with caplog.at_level(logging.WARNING):
            manager = IgnoreManager(tmp_path)
        
        assert any(
            "No .mcpignore found" in record.message
            for record in caplog.records
        )
        
        # Test with 'true' value
        caplog.clear()
        monkeypatch.setenv('RAGEX_IGNOREFILE_WARNING', 'true')
        
        with caplog.at_level(logging.WARNING):
            manager = IgnoreManager(tmp_path)
        
        assert any(
            "No .mcpignore found" in record.message
            for record in caplog.records
        )
    
    def test_no_warning_when_no_defaults(self, tmp_path, caplog):
        """Test that no warning when use_defaults=False"""
        # Create manager without defaults
        with caplog.at_level(logging.WARNING):
            manager = IgnoreManager(tmp_path, use_defaults=False)
        
        # No warning about missing file (because no defaults to inform about)
        assert not any(
            "No .mcpignore found" in record.message
            for record in caplog.records
        )


class TestInitIgnoreFile:
    """Test the init_ignore_file functionality"""
    
    def test_create_comprehensive_file(self, tmp_path):
        """Test creating comprehensive .mcpignore"""
        created = init_ignore_file(tmp_path)
        assert created
        
        ignore_path = tmp_path / IGNORE_FILENAME
        assert ignore_path.exists()
        
        content = ignore_path.read_text()
        
        # Check header
        assert "MCP-RageX ignore patterns" in content
        assert "Generated on" in content
        
        # Check comprehensive patterns are included
        assert "__pycache__/" in content
        assert "node_modules/" in content
        assert "build/" in content
        assert ".vscode/" in content
        
        # Check organization by category
        assert "# Python" in content
        assert "# JavaScript/TypeScript/Node.js" in content
        assert "# C/C++ build artifacts" in content
    
    def test_create_minimal_file(self, tmp_path):
        """Test creating minimal .mcpignore"""
        created = init_ignore_file(tmp_path, minimal=True)
        assert created
        
        content = (tmp_path / IGNORE_FILENAME).read_text()
        
        # Check minimal content
        assert "# Minimal exclusions" in content
        assert "__pycache__/" in content
        assert "node_modules/" in content
        
        # Should not have extensive categorization
        assert "# JavaScript/TypeScript/Node.js" not in content
    
    def test_no_overwrite_by_default(self, tmp_path):
        """Test that existing file is not overwritten by default"""
        ignore_path = tmp_path / IGNORE_FILENAME
        ignore_path.write_text("# Original content\n*.custom")
        
        created = init_ignore_file(tmp_path)
        assert not created
        
        # Original content preserved
        content = ignore_path.read_text()
        assert "# Original content" in content
        assert "*.custom" in content
    
    def test_force_overwrite(self, tmp_path):
        """Test force overwrite of existing file"""
        ignore_path = tmp_path / IGNORE_FILENAME
        ignore_path.write_text("# Original content")
        
        created = init_ignore_file(tmp_path, force=True)
        assert created
        
        # Original content replaced
        content = ignore_path.read_text()
        assert "# Original content" not in content
        assert "MCP-RageX ignore patterns" in content
    
    def test_custom_patterns(self, tmp_path):
        """Test adding custom patterns"""
        custom = ["data/**", "*.secret", "!important.secret"]
        created = init_ignore_file(tmp_path, custom_patterns=custom)
        assert created
        
        content = (tmp_path / IGNORE_FILENAME).read_text()
        
        # Check custom patterns section
        assert "# Custom patterns" in content
        assert "data/**" in content
        assert "*.secret" in content
        assert "!important.secret" in content
    
    def test_generate_content_categories(self):
        """Test that patterns are properly categorized"""
        content = generate_ignore_content(include_defaults=True)
        
        # Check all major categories are present
        categories = [
            "# Python",
            "# JavaScript/TypeScript/Node.js", 
            "# React/Frontend build",
            "# C/C++ build artifacts",
            "# IDE and editors",
            "# OS files",
            "# Environment files",
        ]
        
        for category in categories:
            assert category in content, f"Missing category: {category}"
        
        # Check patterns are under correct categories
        lines = content.split('\n')
        
        # Find Python section and verify Python patterns follow
        python_idx = lines.index("# Python")
        assert any(".venv" in lines[i] for i in range(python_idx, python_idx + 20))
        assert any("__pycache__" in lines[i] for i in range(python_idx, python_idx + 20))
    
    def test_environment_file_exceptions(self):
        """Test that .env.example is not ignored"""
        content = generate_ignore_content(include_defaults=True)
        
        # Should have .env ignored but .env.example not ignored
        assert ".env" in content
        assert "!.env.example" in content
        assert "!.env.template" in content


class TestHybridIntegration:
    """Test the full hybrid approach integration"""
    
    def test_workflow_no_file_then_init(self, tmp_path, caplog):
        """Test typical workflow: warning → init → no warning"""
        # Step 1: Create manager, see warning
        with caplog.at_level(logging.WARNING):
            manager1 = IgnoreManager(tmp_path)
        
        assert any("ragex init" in record.message for record in caplog.records)
        
        # Step 2: Run init
        created = init_ignore_file(tmp_path)
        assert created
        
        # Step 3: Create new manager, no warning
        caplog.clear()
        with caplog.at_level(logging.WARNING):
            manager2 = IgnoreManager(tmp_path)
        
        assert not any(
            "No .mcpignore found" in record.message
            for record in caplog.records
        )
        
        # Both managers should work identically
        test_path = tmp_path / "test.pyc"
        assert manager1.should_ignore(test_path) == manager2.should_ignore(test_path)
    
    def test_generated_file_matches_defaults(self, tmp_path):
        """Test that generated file produces same behavior as in-memory defaults"""
        # Manager with in-memory defaults
        manager_memory = IgnoreManager(tmp_path)
        
        # Create .mcpignore file
        init_ignore_file(tmp_path)
        
        # Manager reading from file
        manager_file = IgnoreManager(tmp_path)
        
        # Test various paths - results should match
        test_paths = [
            "__pycache__/test.pyc",
            "node_modules/package/index.js",
            "build/output.o",
            ".vscode/settings.json",
            "main.py",  # Should NOT be ignored
            "app.js",   # Should NOT be ignored
        ]
        
        for path in test_paths:
            test_path = tmp_path / path
            assert manager_memory.should_ignore(test_path) == manager_file.should_ignore(test_path), \
                f"Mismatch for {path}"


def test_cli_integration(tmp_path, monkeypatch):
    """Test the CLI script integration"""
    # Change to temp directory
    monkeypatch.chdir(tmp_path)
    
    # Import and run the CLI
    from scripts.ragex_init import main
    import sys
    
    # Test creating file
    sys.argv = ['ragex_init']
    result = main()
    assert result == 0
    assert (tmp_path / IGNORE_FILENAME).exists()
    
    # Test already exists
    sys.argv = ['ragex_init']
    result = main()
    assert result == 1  # Should fail
    
    # Test force overwrite
    sys.argv = ['ragex_init', '--force']
    result = main()
    assert result == 0
    
    # Test minimal
    sys.argv = ['ragex_init', '--force', '--minimal']
    result = main()
    assert result == 0
    content = (tmp_path / IGNORE_FILENAME).read_text()
    assert "# Minimal exclusions" in content


if __name__ == "__main__":
    pytest.main([__file__, "-v"])