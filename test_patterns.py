#!/usr/bin/env python3
"""Test script to debug pattern matching"""

import os
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from pattern_matcher import PatternMatcher

# Test from the user's directory
test_dir = "/home/jeff/clients/search/contextsearch/opensearch/scripts/docmanager"
os.chdir(test_dir)

# Create pattern matcher
pm = PatternMatcher()
pm.set_working_directory(test_dir)

print(f"Working directory: {pm.working_directory}")
print(f"Total patterns: {len(pm.patterns)}")
print(f"Default patterns: {len(pm.DEFAULT_EXCLUSIONS)}")
print(f"Patterns: {pm.patterns}")

# Manually simulate what the indexer does
print(f"\nManual file discovery:")
path = Path(test_dir)
supported_extensions = {'.py', '.js', '.jsx', '.ts', '.tsx'}

all_files = []
for ext in supported_extensions:
    for file_path in path.rglob(f"*{ext}"):
        if not pm.should_exclude(str(file_path)):
            all_files.append(file_path)

print(f"Found {len(all_files)} files")

# Count by extension
file_counts = {}
for file in all_files:
    ext = file.suffix
    file_counts[ext] = file_counts.get(ext, 0) + 1

print("File breakdown:")
for ext, count in sorted(file_counts.items()):
    print(f"  {ext}: {count}")

# Show first few files of each type
print("\nSample files:")
for ext in ['.py', '.js', '.jsx', '.ts']:
    matching_files = [f for f in all_files if f.suffix == ext]
    if matching_files:
        print(f"{ext}: {len(matching_files)} files")
        for i, f in enumerate(matching_files[:3]):
            print(f"  {i+1}. {f}")
        if len(matching_files) > 3:
            print(f"  ... and {len(matching_files) - 3} more")