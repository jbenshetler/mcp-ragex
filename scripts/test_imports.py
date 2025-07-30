#!/usr/bin/env python3
"""Test script to verify imports work in Docker environment"""

import sys
import os
from pathlib import Path

print(f"Python: {sys.version}")
print(f"Working directory: {os.getcwd()}")
print(f"Script location: {__file__}")
print(f"PYTHONPATH: {os.environ.get('PYTHONPATH', 'Not set')}")
print()

# Add parent directory to path like smart_index.py does
script_dir = Path(__file__).parent
ragex_dir = script_dir.parent
sys.path.insert(0, str(ragex_dir))
print(f"Added to sys.path: {ragex_dir}")
print()

# Try imports one by one
print("Testing imports...")

try:
    from src.ragex_core.file_checksum import calculate_file_checksum, scan_workspace_files
    print("✓ file_checksum imported successfully")
except ImportError as e:
    print(f"✗ file_checksum import failed: {e}")

try:
    from src.ragex_core.project_utils import (
        find_existing_project_root, 
        generate_project_id,
        get_project_checksum,
        update_project_checksum,
        load_project_metadata
    )
    print("✓ project_utils imported successfully")
except ImportError as e:
    print(f"✗ project_utils import failed: {e}")

try:
    from src.ragex_core.pattern_matcher import PatternMatcher
    print("✓ pattern_matcher imported successfully")
except ImportError as e:
    print(f"✗ pattern_matcher import failed: {e}")

print()
print("sys.path contents:")
for i, path in enumerate(sys.path):
    print(f"  [{i}] {path}")