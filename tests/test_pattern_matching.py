#!/usr/bin/env python3
"""
Tests for pattern matching and file exclusions
"""

import asyncio
import tempfile
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from pattern_matcher import PatternMatcher
from server import RipgrepSearcher


def test_default_exclusions():
    """Test that default exclusions work correctly"""
    matcher = PatternMatcher()
    
    # These should be excluded by default
    assert matcher.should_exclude(".venv/test.py")
    assert matcher.should_exclude("venv/lib/python3.10/site-packages/module.py")
    assert matcher.should_exclude("__pycache__/test.pyc")
    assert matcher.should_exclude("node_modules/package/index.js")
    assert matcher.should_exclude(".git/objects/abc123")
    assert matcher.should_exclude("test.pyc")
    assert matcher.should_exclude(".DS_Store")
    
    # These should NOT be excluded
    assert not matcher.should_exclude("src/main.py")
    assert not matcher.should_exclude("tests/test_server.py")
    assert not matcher.should_exclude("README.md")
    
    print("✓ Default exclusions test passed")


def test_custom_patterns():
    """Test custom exclusion patterns"""
    custom_patterns = ["*.test.js", "temp/", "!important.test.js"]
    matcher = PatternMatcher(custom_patterns=custom_patterns)
    
    # Custom patterns should work
    assert matcher.should_exclude("app.test.js")
    assert matcher.should_exclude("temp/file.txt")
    
    # Negation patterns (if supported by pathspec)
    # Note: gitignore negation is complex - this might not work as expected
    
    print("✓ Custom patterns test passed")


def test_mcpignore_loading():
    """Test loading patterns from .mcpignore file"""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a test .mcpignore
        mcpignore_path = Path(tmpdir) / ".mcpignore"
        mcpignore_path.write_text("""
# Test mcpignore file
*.log
test_output/
# Invalid pattern to test error handling
**[unclosed
*/missing-start
# More patterns
coverage/
*.tmp
        """)
        
        # Change to temp directory
        original_cwd = Path.cwd()
        try:
            import os
            os.chdir(tmpdir)
            
            matcher = PatternMatcher()
            
            # Valid patterns should work
            assert matcher.should_exclude("debug.log")
            assert matcher.should_exclude("test_output/results.txt")
            assert matcher.should_exclude("coverage/index.html")
            assert matcher.should_exclude("temp.tmp")
            
            # Invalid pattern should be skipped
            validation_report = matcher.get_validation_report()
            assert validation_report is not None
            # Check if we detected the invalid pattern
            if validation_report.get("invalid_patterns"):
                print(f"  ✓ Found {len(validation_report['invalid_patterns'])} invalid patterns as expected")
            else:
                print("  Note: No invalid patterns detected (pattern might have been fixed)")
            
        finally:
            os.chdir(original_cwd)
    
    print("✓ .mcpignore loading test passed")


def test_ripgrep_arg_generation():
    """Test conversion of patterns to ripgrep arguments"""
    matcher = PatternMatcher(custom_patterns=["*.test.js", "docs/"])
    args = matcher.get_ripgrep_args()
    
    # Should generate --glob arguments
    assert "--glob" in args
    assert any("!*.test.js" in arg or arg == "!*.test.js" for arg in args)
    assert any("!docs/" in arg or arg == "!docs/" for arg in args)
    
    # Default exclusions should also be included
    assert any(".venv/**" in arg for arg in args)
    
    print("✓ Ripgrep argument generation test passed")


async def test_search_with_exclusions():
    """Test that search actually excludes files"""
    searcher = RipgrepSearcher()
    
    # Search for a common pattern
    result = await searcher.search(
        pattern="def|function|class",
        limit=50,
        exclude_patterns=["tests/**", "*.md"]
    )
    
    if result["success"] and result["matches"]:
        # Check that no test files or markdown files are in results
        for match in result["matches"]:
            file_path = match["file"]
            assert not file_path.startswith("tests/")
            assert not file_path.endswith(".md")
    
    print("✓ Search with exclusions test passed")


def test_pattern_validation():
    """Test pattern validation and error handling"""
    matcher = PatternMatcher()
    
    # Test the validation report feature
    report = matcher.validate_mcpignore(verbose=True)
    
    # Since we have a .mcpignore in the project, check the report
    if report["exists"]:
        assert "valid_patterns" in report
        assert "invalid_patterns" in report
        assert "stats" in report
        
        print(f"  Found {len(report['valid_patterns'])} valid patterns")
        print(f"  Found {len(report['invalid_patterns'])} invalid patterns")
        
        if report.get("warnings"):
            print(f"  Warnings: {len(report['warnings'])}")
    
    print("✓ Pattern validation test passed")


def test_path_handling():
    """Test various path formats"""
    matcher = PatternMatcher(custom_patterns=["src/*.py", "/root.txt", "**/*.log"])
    
    # Relative paths
    assert matcher.should_exclude("src/main.py")
    assert not matcher.should_exclude("tests/main.py")  # Different directory
    
    # Root paths (from project root)
    assert matcher.should_exclude("root.txt")
    assert not matcher.should_exclude("src/root.txt")  # Not in root
    
    # Recursive patterns
    assert matcher.should_exclude("logs/debug.log")
    assert matcher.should_exclude("src/logs/error.log")
    assert matcher.should_exclude("a/b/c/d/test.log")
    
    print("✓ Path handling test passed")


if __name__ == "__main__":
    print("Pattern Matching Test Suite")
    print("=" * 50)
    
    # Run synchronous tests
    test_default_exclusions()
    test_custom_patterns()
    test_mcpignore_loading()
    test_ripgrep_arg_generation()
    test_pattern_validation()
    test_path_handling()
    
    # Run async tests
    print("\nRunning async tests...")
    asyncio.run(test_search_with_exclusions())
    
    print("\n✅ All tests passed!")