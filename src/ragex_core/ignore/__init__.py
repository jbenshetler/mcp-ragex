"""
Ignore file processing module for MCP-RAGex

This module provides a flexible, multi-level ignore file system that supports:
- Multiple .rgignore files at different directory levels
- Hot reloading via external change notifications
- Central filename configuration for easy migration
- Performance optimizations with caching
"""

from .constants import IGNORE_FILENAME
from .manager import IgnoreManager
from .rule_engine import IgnoreRuleEngine
from .file_loader import IgnoreFileLoader
from .cache import IgnoreCache
from .registry import IgnoreFileRegistry
from .init import init_ignore_file, generate_ignore_content

__all__ = [
    'IGNORE_FILENAME',
    'IgnoreManager',
    'IgnoreRuleEngine',
    'IgnoreFileLoader',
    'IgnoreCache',
    'IgnoreFileRegistry',
    'init_ignore_file',
    'generate_ignore_content',
]
