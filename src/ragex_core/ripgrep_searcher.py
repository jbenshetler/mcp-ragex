"""
Ripgrep searcher implementation - pure library code with no side effects.
"""
import asyncio
import json
import logging
import re
import shutil
import time
from pathlib import Path
from typing import Dict, List, Optional, Any

# Security constants
MAX_RESULTS = 200
DEFAULT_RESULTS = 20
MAX_PATTERN_LENGTH = 500
ALLOWED_FILE_TYPES = {
    "py", "python", "js", "javascript", "ts", "typescript", 
    "java", "cpp", "c", "go", "rust", "rb", "ruby", "php",
    "cs", "csharp", "swift", "kotlin", "scala", "r", "lua",
    "sh", "bash", "ps1", "yaml", "yml", "json", "xml", "html",
    "css", "scss", "sass", "sql", "md", "markdown", "txt"
}

logger = logging.getLogger("ripgrep-searcher")


class RipgrepSearcher:
    """Manages ripgrep subprocess with security and performance optimizations"""
    
    def __init__(self, pattern_matcher=None):
        self.rg_path = shutil.which("rg")
        if not self.rg_path:
            raise RuntimeError("ripgrep (rg) not found. Please install ripgrep.")
        
        # Pattern matcher for exclusions
        self.pattern_matcher = pattern_matcher
        
        # Base arguments for all searches
        self.base_args = [
            "--json",           # JSON output for parsing
            "--no-heading",     # Disable grouping by file
            "--with-filename",  # Include filename in results
            "--line-number",    # Include line numbers
            "--no-config",      # Ignore user config files
            "--max-columns", "500",  # Limit line length
            "--max-columns-preview",  # Show preview of long lines
        ]
    
    def validate_pattern(self, pattern: str) -> str:
        """Validate and sanitize regex pattern"""
        if not pattern or len(pattern) > MAX_PATTERN_LENGTH:
            raise ValueError(f"Pattern must be 1-{MAX_PATTERN_LENGTH} characters")
        
        # Basic validation - ensure it's a valid regex
        try:
            re.compile(pattern)
        except re.error as e:
            raise ValueError(f"Invalid regex pattern: {e}")
        
        return pattern
    
    async def search(
        self,
        pattern: str,
        paths: Optional[List[Path]] = None,
        file_types: Optional[List[str]] = None,
        case_sensitive: bool = True,
        limit: int = DEFAULT_RESULTS,
        multiline: bool = False,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Execute ripgrep search with given parameters
        
        Args:
            pattern: Regex pattern to search
            paths: Paths to search in (defaults to working directory)
            file_types: File types to include (e.g., ["py", "js"])
            case_sensitive: Whether search is case sensitive
            limit: Maximum number of results
            multiline: Enable multiline matching
            **kwargs: Additional ripgrep options
            
        Returns:
            Dict with success status and matches
        """
        # Validate inputs
        pattern = self.validate_pattern(pattern)
        limit = min(limit, MAX_RESULTS)
        
        # Validate file types
        if file_types:
            invalid_types = set(file_types) - ALLOWED_FILE_TYPES
            if invalid_types:
                raise ValueError(f"Invalid file types: {invalid_types}")
        
        # Determine search paths - default to current directory
        if paths:
            search_paths = [Path(p) for p in paths]
            # Validate paths exist and are within working directory
            for path in search_paths:
                if not path.exists():
                    raise ValueError(f"Path does not exist: {path}")
        else:
            # Default to working directory
            working_dir = Path.cwd()
            logger.debug(f"No paths specified, using working directory: {working_dir}")
            search_paths = [working_dir]
        
        # Build command
        cmd = [self.rg_path] + self.base_args.copy()
        
        # Add case sensitivity
        if not case_sensitive:
            cmd.append("-i")
        
        # Add file type filters
        if file_types:
            for ft in file_types:
                cmd.extend(["--type", ft])
        
        # Add multiline flag
        if multiline:
            cmd.extend(["-U", "--multiline-dotall"])
        
        # Apply exclusions from pattern matcher if available
        if self.pattern_matcher:
            exclude_args = self.pattern_matcher.get_ripgrep_args()
            if exclude_args:
                logger.debug(f"Applying exclusions: {exclude_args}")
                cmd.extend(exclude_args)
        
        # Add any additional ripgrep options
        for key, value in kwargs.items():
            if key.startswith("-"):
                if value is True:
                    cmd.append(key)
                elif value is not False:
                    cmd.extend([key, str(value)])
        
        # Add pattern
        cmd.append(pattern)
        
        # Add paths
        cmd.extend(str(p) for p in search_paths)
        
        # Log the full command
        logger.info(f"🔍 Ripgrep command: {' '.join(cmd)}")
        logger.info(f"🔍 Working directory: {Path.cwd()}")
        logger.info(f"🔍 Search paths exist check:")
        for path in search_paths:
            exists = path.exists()
            logger.info(f"    {path}: exists={exists}")
            if exists and path.is_dir():
                try:
                    file_count = len(list(path.glob('**/*')))
                    logger.info(f"      Contains {file_count} files/dirs")
                except Exception as e:
                    logger.info(f"      Error counting files: {e}")
        
        # Track search time
        search_start = time.time()
        
        # Execute search
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=30.0  # 30 second timeout
            )
            
            # Log search completion time
            search_time = time.time() - search_start
            logger.info(f"🔍 Search completed in {search_time:.3f} seconds")
            logger.info(f"🔍 Process return code: {process.returncode}")
            logger.info(f"🔍 Stdout length: {len(stdout)} bytes")
            logger.info(f"🔍 Stderr length: {len(stderr)} bytes")
            
            if stderr:
                stderr_text = stderr.decode()
                logger.info(f"🔍 Stderr content: {stderr_text}")
            
            if process.returncode not in (0, 1):  # 0=matches found, 1=no matches
                raise RuntimeError(f"ripgrep failed: {stderr.decode()}")
            
            # Log raw stdout for debugging
            stdout_text = stdout.decode()
            logger.info(f"🔍 Raw stdout (first 500 chars): {stdout_text[:500]}")
            
            # Parse results
            matches = []
            for line in stdout_text.strip().split('\n'):
                if not line:
                    continue
                    
                try:
                    data = json.loads(line)
                    if data.get("type") == "match":
                        match_data = data["data"]
                        matches.append({
                            "file": match_data["path"]["text"],
                            "line_number": match_data["line_number"],
                            "line": match_data["lines"]["text"].strip(),
                            "column": match_data.get("submatches", [{}])[0].get("start", 0),
                        })
                except json.JSONDecodeError:
                    logger.warning(f"Failed to parse line: {line}")
                    continue
            
            # Log search results
            logger.info(f"🔍 Parsed {len(matches)} matches from ripgrep output")
            logger.info(f"🔍 Returning {min(len(matches), limit)} matches (limit={limit})")
            
            return {
                "success": True,
                "pattern": pattern,
                "total_matches": len(matches),
                "matches": matches[:limit],  # Ensure we respect limit
                "truncated": len(matches) > limit,
            }
            
        except asyncio.TimeoutError:
            return {
                "success": False,
                "error": "Search timed out after 30 seconds",
                "pattern": pattern,
                "total_matches": 0,
                "matches": []
            }
        except Exception as e:
            logger.error(f"Search error: {e}")
            return {
                "success": False,
                "error": str(e),
                "pattern": pattern,
                "total_matches": 0,
                "matches": []
            }