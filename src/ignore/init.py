"""
Initialize .mcpignore files with sensible defaults
"""

import os
from pathlib import Path
from typing import Optional, List
from datetime import datetime

from .constants import IGNORE_FILENAME, DEFAULT_EXCLUSIONS


def generate_ignore_content(custom_patterns: Optional[List[str]] = None,
                          include_defaults: bool = True,
                          minimal: bool = False) -> str:
    """
    Generate content for a .mcpignore file
    
    Args:
        custom_patterns: Additional patterns to include
        include_defaults: Whether to include comprehensive defaults
        minimal: Generate minimal file with just essential patterns
        
    Returns:
        Content for .mcpignore file
    """
    lines = []
    
    # Header
    lines.extend([
        f"# {IGNORE_FILENAME} - MCP-RageX ignore patterns",
        f"# Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "#",
        "# This file uses gitignore syntax to exclude files from code analysis.",
        "# Patterns are matched relative to the location of this file.",
        "# Use ! to negate patterns and re-include files.",
        "",
    ])
    
    if minimal:
        # Minimal set of patterns
        lines.extend([
            "# Minimal exclusions",
            "# -----------------",
            "",
            "# Version control",
            ".git/",
            "",
            "# Python",
            "__pycache__/",
            "*.pyc",
            ".venv/",
            "venv/",
            "",
            "# Node.js",
            "node_modules/",
            "",
            "# Build artifacts",
            "build/",
            "dist/",
            "",
            "# IDE",
            ".vscode/",
            ".idea/",
            "",
            "# OS",
            ".DS_Store",
            "Thumbs.db",
            "",
        ])
    elif include_defaults:
        # Group patterns by category for better organization
        categories = {
            "Python": [],
            "JavaScript/TypeScript/Node.js": [],
            "React/Frontend build": [],
            "C/C++ build artifacts": [],
            "IDE and editors": [],
            "OS files": [],
            "Logs and databases": [],
            "Testing": [],
            "Temporary files": [],
            "Version control": [],
            "Documentation build": [],
            "Environment files": [],
            "Archives": [],
            "Media files": [],
        }
        
        # Categorize default patterns
        for pattern in DEFAULT_EXCLUSIONS:
            if any(p in pattern for p in ['.venv', 'venv/', '__pycache__', '.py', '.egg', 'pip-', '.tox', '.mypy', '.pytest', '.coverage', '.hypothesis']):
                categories["Python"].append(pattern)
            elif any(p in pattern for p in ['node_modules', 'npm-', 'yarn-', '.npm', '.yarn', '.pnp', 'tsconfig', '.tsbuildinfo']):
                categories["JavaScript/TypeScript/Node.js"].append(pattern)
            elif any(p in pattern for p in ['.next', '.nuxt', '.cache', '.parcel', '.webpack', '.vuepress', '.docusaurus', '.serverless', 'public/build']):
                categories["React/Frontend build"].append(pattern)
            elif any(p in pattern for p in ['cmake', 'CMake', '.o', '.obj', '.a', '.lib', '.so', '.dylib', '.dll', '.exe', '.out', '.app']) and pattern != ".so":
                categories["C/C++ build artifacts"].append(pattern)
            elif any(p in pattern for p in ['.vscode', '.idea', '.swp', '.swo', '.project', '.classpath', '.settings', 'sublime']):
                categories["IDE and editors"].append(pattern)
            elif any(p in pattern for p in ['.DS_Store', 'Thumbs.db', 'Desktop.ini', '$RECYCLE.BIN', 'ehthumbs']):
                categories["OS files"].append(pattern)
            elif any(p in pattern for p in ['.log', 'logs/', '.sqlite', '.db']):
                categories["Logs and databases"].append(pattern)
            elif any(p in pattern for p in ['.nyc', 'coverage/', '.lcov', '.grunt']):
                categories["Testing"].append(pattern)
            elif any(p in pattern for p in ['.tmp', '.temp', '.bak', '.backup', '.old']):
                categories["Temporary files"].append(pattern)
            elif any(p in pattern for p in ['.git/', '.svn/', '.hg/', '.bzr/']):
                categories["Version control"].append(pattern)
            elif any(p in pattern for p in ['docs/_build', 'site/', '_site/', '.jekyll', '.sass-cache']):
                categories["Documentation build"].append(pattern)
            elif any(p in pattern for p in ['.env']):
                categories["Environment files"].append(pattern)
            elif any(p in pattern for p in ['.zip', '.tar', '.gz', '.tgz', '.rar', '.7z']):
                categories["Archives"].append(pattern)
            elif any(p in pattern for p in ['.jpg', '.jpeg', '.png', '.gif', '.ico', '.pdf', '.mov', '.mp4', '.mp3', '.wav']):
                categories["Media files"].append(pattern)
            elif pattern in ['build/**', 'dist/**', 'out/**']:
                categories["React/Frontend build"].append(pattern)
            elif pattern == "*.so":
                # .so appears in both Python and C/C++
                categories["Python"].append(pattern)
                categories["C/C++ build artifacts"].append(pattern)
        
        # Write categorized patterns
        for category, patterns in categories.items():
            if patterns:
                lines.extend([
                    f"# {category}",
                    f"# {'-' * len(category)}",
                ])
                for pattern in sorted(set(patterns)):  # Remove duplicates and sort
                    lines.append(pattern)
                lines.append("")
    
    # Custom patterns section
    if custom_patterns:
        lines.extend([
            "# Custom patterns",
            "# ---------------",
        ])
        for pattern in custom_patterns:
            lines.append(pattern)
        lines.append("")
    
    # Footer with helpful information
    lines.extend([
        "# Additional patterns for your project",
        "# -----------------------------------",
        "# Add your project-specific patterns below:",
        "#",
        "# Examples:",
        "# data/raw/**           # Large data files",
        "# *.pkl                 # Model files",
        "# secrets/**            # Sensitive files",
        "# !important.log        # Exception - don't ignore this",
        "#",
        "# Multi-level .mcpignore:",
        "# You can create .mcpignore files in subdirectories to override parent rules.",
        "# Deeper files take precedence over parent directory rules.",
        "",
    ])
    
    return '\n'.join(lines)


def init_ignore_file(path: Path,
                    force: bool = False,
                    minimal: bool = False,
                    custom_patterns: Optional[List[str]] = None) -> bool:
    """
    Initialize a .mcpignore file at the specified path
    
    Args:
        path: Directory where to create .mcpignore
        force: Overwrite existing file
        minimal: Create minimal file instead of comprehensive
        custom_patterns: Additional patterns to include
        
    Returns:
        True if file was created, False if already exists and not forced
    """
    ignore_path = path / IGNORE_FILENAME
    
    # Check if file exists
    if ignore_path.exists() and not force:
        return False
    
    # Generate content
    content = generate_ignore_content(
        custom_patterns=custom_patterns,
        include_defaults=not minimal,
        minimal=minimal
    )
    
    # Write file
    ignore_path.write_text(content, encoding='utf-8')
    return True


def create_init_command():
    """
    Create a command-line interface for initializing .mcpignore files
    
    This would be integrated into the main ragex CLI
    """
    import argparse
    
    parser = argparse.ArgumentParser(
        description=f'Initialize {IGNORE_FILENAME} with sensible defaults'
    )
    parser.add_argument(
        'path',
        nargs='?',
        default='.',
        help='Directory where to create .mcpignore (default: current directory)'
    )
    parser.add_argument(
        '--force', '-f',
        action='store_true',
        help='Overwrite existing .mcpignore file'
    )
    parser.add_argument(
        '--minimal', '-m',
        action='store_true',
        help='Create minimal .mcpignore with essential patterns only'
    )
    parser.add_argument(
        '--add', '-a',
        action='append',
        dest='patterns',
        help='Add custom pattern (can be used multiple times)'
    )
    
    return parser


# Example CLI integration
if __name__ == "__main__":
    # This would be integrated into the main ragex command
    parser = create_init_command()
    args = parser.parse_args()
    
    path = Path(args.path)
    if not path.is_dir():
        print(f"Error: {path} is not a directory")
        exit(1)
    
    created = init_ignore_file(
        path=path,
        force=args.force,
        minimal=args.minimal,
        custom_patterns=args.patterns
    )
    
    ignore_path = path / IGNORE_FILENAME
    if created:
        print(f"Created {ignore_path}")
        if args.minimal:
            print("Generated minimal .mcpignore file")
        else:
            print("Generated comprehensive .mcpignore with default exclusions")
    else:
        print(f"{ignore_path} already exists. Use --force to overwrite.")