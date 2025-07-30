#!/usr/bin/env python3
"""
File checksum calculation and comparison for incremental indexing.

This module provides utilities for calculating SHA256 checksums of individual files
and comparing current vs stored checksums to determine what needs to be re-indexed.
"""

import hashlib
import logging
from pathlib import Path
from typing import Dict, List, Tuple, Set

from .path_mapping import container_to_host_path, is_container_path

logger = logging.getLogger("file-checksum")


def calculate_file_checksum(file_path: Path) -> str:
    """
    Calculate SHA256 checksum of a single file.
    
    Args:
        file_path: Path to the file
        
    Returns:
        Hex string of SHA256 hash
        
    Raises:
        IOError: If file cannot be read
    """
    hasher = hashlib.sha256()
    
    try:
        with open(file_path, 'rb') as f:
            while chunk := f.read(8192):  # 8KB chunks
                hasher.update(chunk)
        return hasher.hexdigest()
    except Exception as e:
        logger.error(f"Failed to calculate checksum for {file_path}: {e}")
        raise


def scan_workspace_files(workspace_path: Path, ignore_manager) -> Dict[str, str]:
    """
    Scan workspace and calculate checksums for all non-ignored files.
    
    Args:
        workspace_path: Root directory to scan
        ignore_manager: IgnoreManager instance for filtering
        
    Returns:
        Dictionary mapping file paths to their checksums.
        When running in container, paths are converted to host paths.
        {file_path: checksum}
    """
    results = {}
    file_count = 0
    
    logger.info(f"Scanning workspace for files: {workspace_path}")
    
    try:
        for file_path in workspace_path.rglob('*'):
            # Skip directories
            if not file_path.is_file():
                continue
                
            # Skip if ignored
            if ignore_manager.should_ignore(str(file_path)):
                continue
            
            # Calculate checksum and determine storage path
            try:
                checksum = calculate_file_checksum(file_path)
                
                # Convert to host path if we're in a container
                storage_path = str(file_path)
                if is_container_path(storage_path):
                    storage_path = container_to_host_path(storage_path)
                
                results[storage_path] = checksum
                file_count += 1
                
                if file_count % 100 == 0:
                    logger.debug(f"Processed {file_count} files...")
                    
            except Exception as e:
                logger.warning(f"Skipping file {file_path}: {e}")
                continue
    
    except Exception as e:
        logger.error(f"Error scanning workspace {workspace_path}: {e}")
        raise
    
    logger.info(f"Scanned {file_count} files in workspace")
    return results


def compare_checksums(current: Dict[str, str], stored: Dict[str, str]) -> Tuple[List[str], List[str], List[str]]:
    """
    Compare current vs stored checksums to find changes.
    
    Args:
        current: Current file checksums {file_path: checksum}
        stored: Previously stored checksums {file_path: checksum}
        
    Returns:
        Tuple of (added_files, removed_files, modified_files)
        - added_files: Files in current but not in stored
        - removed_files: Files in stored but not in current  
        - modified_files: Files with different checksums
    """
    current_files = set(current.keys())
    stored_files = set(stored.keys())
    
    # Files that exist now but didn't before
    added = list(current_files - stored_files)
    
    # Files that existed before but don't now
    removed = list(stored_files - current_files)
    
    # Files that exist in both but have different checksums
    modified = []
    for file_path in current_files & stored_files:
        if current[file_path] != stored[file_path]:
            modified.append(file_path)
    
    logger.info(f"Checksum comparison: +{len(added)} ~{len(modified)} -{len(removed)} files")
    
    return added, removed, modified


def get_changed_files(workspace_path: Path, ignore_manager, stored_checksums: Dict[str, str]) -> Tuple[List[str], List[str], List[str]]:
    """
    Convenience function to scan workspace and compare with stored checksums.
    
    Args:
        workspace_path: Root directory to scan
        ignore_manager: IgnoreManager instance for filtering
        stored_checksums: Previously stored checksums
        
    Returns:
        Tuple of (added_files, removed_files, modified_files)
    """
    current_checksums = scan_workspace_files(workspace_path, ignore_manager)
    return compare_checksums(current_checksums, stored_checksums)


# Performance optimization helpers

def should_recompute_checksum(file_path: Path, cached_size: int, cached_mtime: float) -> bool:
    """
    Check if file stats changed before expensive checksum calculation.
    
    This is an optimization to avoid reading files that haven't changed
    based on size and modification time.
    
    Args:
        file_path: Path to check
        cached_size: Previously stored file size
        cached_mtime: Previously stored modification time
        
    Returns:
        True if checksum should be recalculated, False if cached value is likely valid
    """
    try:
        stat = file_path.stat()
        return (stat.st_size != cached_size or 
                abs(stat.st_mtime - cached_mtime) > 0.1)  # Allow small float precision differences
    except OSError:
        # File doesn't exist or can't be accessed
        return True


def scan_workspace_files_optimized(workspace_path: Path, ignore_manager, 
                                 cached_info: Dict[str, Tuple[int, float, str]]) -> Dict[str, str]:
    """
    Optimized version that skips checksum calculation for unchanged files.
    
    Args:
        workspace_path: Root directory to scan
        ignore_manager: IgnoreManager instance for filtering
        cached_info: Previously cached file info {file_path: (size, mtime, checksum)}
        
    Returns:
        Dictionary mapping file paths to their checksums.
        When running in container, paths are converted to host paths.
    """
    results = {}
    files_processed = 0
    files_skipped = 0
    
    logger.info(f"Scanning workspace with optimization: {workspace_path}")
    
    for file_path in workspace_path.rglob('*'):
        if not file_path.is_file() or ignore_manager.should_ignore(str(file_path)):
            continue
            
        # Convert to host path if we're in a container
        storage_path = str(file_path)
        if is_container_path(storage_path):
            storage_path = container_to_host_path(storage_path)
        
        try:
            # Check if we have cached info and file hasn't changed
            if storage_path in cached_info:
                cached_size, cached_mtime, cached_checksum = cached_info[storage_path]
                
                if not should_recompute_checksum(file_path, cached_size, cached_mtime):
                    # File unchanged, use cached checksum
                    results[storage_path] = cached_checksum
                    files_skipped += 1
                    continue
            
            # File is new or changed, calculate checksum
            checksum = calculate_file_checksum(file_path)
            results[storage_path] = checksum
            files_processed += 1
            
        except Exception as e:
            logger.warning(f"Skipping file {file_path}: {e}")
            continue
    
    logger.info(f"Processed {files_processed} files, skipped {files_skipped} unchanged files")
    return results
