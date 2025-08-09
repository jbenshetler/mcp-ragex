#!/usr/bin/env python3
"""
Parallel symbol extraction using tree-sitter with true multiprocessing
Provides significant performance improvements for large codebases
"""

import asyncio
import logging
import multiprocessing as mp
import os
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any, Callable
from functools import partial

try:
    from .tree_sitter_enhancer import TreeSitterEnhancer, Symbol
    from .ragex_core.pattern_matcher import PatternMatcher
    from .ragex_core.path_mapping import container_to_host_path, is_container_path
except ImportError:
    from src.tree_sitter_enhancer import TreeSitterEnhancer, Symbol
    from src.ragex_core.pattern_matcher import PatternMatcher
    from src.ragex_core.path_mapping import container_to_host_path, is_container_path

logger = logging.getLogger("parallel-symbol-extractor")

@dataclass
class ExtractionTask:
    """Represents a single file extraction task"""
    file_path: str
    include_docs_and_comments: bool
    file_size: int = 0
    language: Optional[str] = None

@dataclass
class ExtractionResult:
    """Result from extracting symbols from a file"""
    file_path: str
    symbols: List[Dict[str, Any]]
    success: bool
    error: Optional[str] = None
    processing_time: float = 0.0

@dataclass  
class BatchResult:
    """Result from processing a batch of files"""
    results: List[ExtractionResult]
    worker_id: int
    processing_time: float
    files_processed: int

class ProgressTracker:
    """Thread-safe progress tracking for parallel extraction"""
    
    def __init__(self, total_files: int):
        self.total_files = total_files
        self.completed_files = 0
        self.failed_files = 0
        self.start_time = time.time()
        self._lock = mp.Lock()
        
    def update(self, completed: int = 0, failed: int = 0):
        """Update progress counters"""
        with self._lock:
            self.completed_files += completed
            self.failed_files += failed
            
    def get_progress(self) -> Dict[str, Any]:
        """Get current progress information"""
        with self._lock:
            elapsed = time.time() - self.start_time
            total_processed = self.completed_files + self.failed_files
            rate = total_processed / elapsed if elapsed > 0 else 0
            
            return {
                "total_files": self.total_files,
                "completed_files": self.completed_files,
                "failed_files": self.failed_files,
                "progress_percent": (total_processed / self.total_files * 100) if self.total_files > 0 else 0,
                "elapsed_time": elapsed,
                "processing_rate": rate,
                "estimated_remaining": (self.total_files - total_processed) / rate if rate > 0 else 0
            }

def _init_worker():
    """Initialize worker process with optimized tree-sitter enhancer"""
    global worker_enhancer
    # Import shared parser pool here to avoid import issues
    try:
        from .shared_parser_pool import get_worker_pool
    except ImportError:
        from src.shared_parser_pool import get_worker_pool
    
    # Initialize the worker pool first
    pool = get_worker_pool()
    
    # Create enhancer with shared parsers
    worker_enhancer = TreeSitterEnhancer()
    logger.debug(f"Worker {os.getpid()} initialized with shared parser pool")

def _extract_symbols_worker(tasks: List[ExtractionTask]) -> BatchResult:
    """Worker function to extract symbols from a batch of files"""
    worker_id = os.getpid()
    start_time = time.time()
    results = []
    
    logger.debug(f"Worker {worker_id} processing {len(tasks)} files")
    
    for task in tasks:
        task_start = time.time()
        try:
            # Use the worker's enhancer instance
            symbols = asyncio.run(worker_enhancer.extract_symbols(
                task.file_path, 
                task.include_docs_and_comments
            ))
            
            # Convert Symbol objects to dictionaries for serialization
            symbol_dicts = []
            for symbol in symbols:
                if hasattr(symbol, 'to_dict'):
                    symbol_dicts.append(symbol.to_dict())
                else:
                    # Handle case where symbol is already a dict
                    symbol_dicts.append(symbol if isinstance(symbol, dict) else asdict(symbol))
            
            result = ExtractionResult(
                file_path=task.file_path,
                symbols=symbol_dicts,
                success=True,
                processing_time=time.time() - task_start
            )
            
        except Exception as e:
            logger.warning(f"Worker {worker_id} failed to process {task.file_path}: {e}")
            result = ExtractionResult(
                file_path=task.file_path,
                symbols=[],
                success=False,
                error=str(e),
                processing_time=time.time() - task_start
            )
            
        results.append(result)
    
    total_time = time.time() - start_time
    logger.debug(f"Worker {worker_id} completed {len(tasks)} files in {total_time:.2f}s")
    
    return BatchResult(
        results=results,
        worker_id=worker_id,
        processing_time=total_time,
        files_processed=len(tasks)
    )

class ParallelSymbolExtractor:
    """Parallel symbol extractor using ProcessPoolExecutor"""
    
    def __init__(self, max_workers: Optional[int] = None, pattern_matcher: Optional[PatternMatcher] = None, config: Optional['ParallelConfig'] = None):
        """
        Initialize parallel symbol extractor
        
        Args:
            max_workers: Maximum number of worker processes. If None, uses optimal detection
            pattern_matcher: Pattern matcher for file exclusions
            config: Optional configuration object. If None, uses optimal auto-detection
        """
        # Import config here to avoid circular imports
        try:
            from .parallel_config import get_optimal_config
        except ImportError:
            from src.parallel_config import get_optimal_config
        
        # Use provided config or get optimal configuration
        if config is None:
            config = get_optimal_config()
        
        # Override max_workers if explicitly provided
        if max_workers is not None:
            config.max_workers = max_workers
        
        self.config = config
        self.max_workers = config.max_workers
        self.pattern_matcher = pattern_matcher or PatternMatcher()
        self.enhancer = TreeSitterEnhancer(pattern_matcher)  # Fallback for sequential processing
        
        # Configuration from config object
        self.min_batch_size = config.min_batch_size
        self.max_batch_size = config.max_batch_size
        self.target_batch_time = config.target_batch_time
        
        logger.info(f"Initialized parallel extractor with {self.max_workers} workers (config: batch {self.min_batch_size}-{self.max_batch_size}, target {self.target_batch_time}s)")
    
    def _get_file_info(self, file_path: str) -> Tuple[int, Optional[str]]:
        """Get file size and language for task planning"""
        try:
            size = Path(file_path).stat().st_size
            ext = Path(file_path).suffix.lower()
            lang = {
                ".py": "python",
                ".js": "javascript", 
                ".jsx": "javascript",
                ".ts": "typescript",
                ".tsx": "tsx"
            }.get(ext)
            return size, lang
        except Exception:
            return 0, None
    
    def _create_batches(self, tasks: List[ExtractionTask]) -> List[List[ExtractionTask]]:
        """Create optimal batches for parallel processing"""
        if not tasks:
            return []
        
        # Sort tasks by language first, then by file size (largest first)
        tasks.sort(key=lambda t: (t.language or "", -t.file_size))
        
        batches = []
        current_batch = []
        current_batch_size = 0
        
        for task in tasks:
            # Estimate processing time based on file size (rough heuristic)
            estimated_time = max(0.1, task.file_size / 50000)  # ~50KB per 0.1s
            
            # Start new batch if current would be too large or different language
            if (current_batch and 
                (len(current_batch) >= self.max_batch_size or
                 current_batch_size + estimated_time > self.target_batch_time or
                 (task.language and current_batch[-1].language != task.language))):
                
                batches.append(current_batch)
                current_batch = []
                current_batch_size = 0
            
            current_batch.append(task)
            current_batch_size += estimated_time
            
            # Ensure minimum batch size unless we're at the end
            if len(current_batch) >= self.min_batch_size:
                remaining_tasks = len(tasks) - len(batches) * self.max_batch_size - len(current_batch)
                if remaining_tasks == 0 or current_batch_size >= self.target_batch_time:
                    batches.append(current_batch)
                    current_batch = []
                    current_batch_size = 0
        
        # Add remaining tasks
        if current_batch:
            batches.append(current_batch)
        
        logger.debug(f"Created {len(batches)} batches from {len(tasks)} tasks")
        return batches
    
    async def extract_symbols_parallel(
        self, 
        file_paths: List[str], 
        include_docs_and_comments: bool = False,
        progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None
    ) -> List[ExtractionResult]:
        """
        Extract symbols from multiple files in parallel
        
        Args:
            file_paths: List of file paths to process
            include_docs_and_comments: Whether to include documentation and comments
            progress_callback: Optional callback for progress updates
            
        Returns:
            List of extraction results
        """
        start_time = time.time()
        
        # Filter out excluded files
        valid_paths = []
        for path in file_paths:
            if not self.pattern_matcher.should_exclude(path):
                # Check if file has supported language
                lang = self.enhancer._get_language(path)
                if lang:
                    valid_paths.append(path)
                else:
                    logger.debug(f"Skipping unsupported file: {path}")
            else:
                logger.debug(f"Excluding file: {path}")
        
        if not valid_paths:
            logger.info("No valid files to process")
            return []
        
        logger.info(f"Processing {len(valid_paths)} files with {self.max_workers} workers")
        
        # Create extraction tasks
        tasks = []
        for path in valid_paths:
            size, lang = self._get_file_info(path)
            task = ExtractionTask(
                file_path=path,
                include_docs_and_comments=include_docs_and_comments,
                file_size=size,
                language=lang
            )
            tasks.append(task)
        
        # Create optimal batches
        batches = self._create_batches(tasks)
        
        # Initialize progress tracking
        progress_tracker = ProgressTracker(len(valid_paths))
        
        # Process batches in parallel
        all_results = []
        
        if len(batches) == 1:
            # Single batch - run sequentially to avoid process overhead
            logger.debug("Single batch detected, running sequentially")
            batch_tasks = batches[0]
            for task in batch_tasks:
                try:
                    symbols = await self.enhancer.extract_symbols(
                        task.file_path, 
                        task.include_docs_and_comments
                    )
                    
                    symbol_dicts = []
                    for symbol in symbols:
                        if hasattr(symbol, 'to_dict'):
                            symbol_dicts.append(symbol.to_dict())
                        else:
                            symbol_dicts.append(symbol if isinstance(symbol, dict) else asdict(symbol))
                    
                    result = ExtractionResult(
                        file_path=task.file_path,
                        symbols=symbol_dicts,
                        success=True
                    )
                    progress_tracker.update(completed=1)
                    
                except Exception as e:
                    logger.warning(f"Failed to process {task.file_path}: {e}")
                    result = ExtractionResult(
                        file_path=task.file_path,
                        symbols=[],
                        success=False,
                        error=str(e)
                    )
                    progress_tracker.update(failed=1)
                
                all_results.append(result)
                
                # Report progress
                if progress_callback:
                    progress_callback(progress_tracker.get_progress())
        
        else:
            # Multiple batches - use parallel processing
            with ProcessPoolExecutor(
                max_workers=self.max_workers,
                initializer=_init_worker
            ) as executor:
                
                # Submit all batches
                future_to_batch = {}
                for i, batch in enumerate(batches):
                    future = executor.submit(_extract_symbols_worker, batch)
                    future_to_batch[future] = i
                
                # Process completed batches
                for future in as_completed(future_to_batch):
                    batch_idx = future_to_batch[future]
                    
                    try:
                        batch_result = future.result()
                        all_results.extend(batch_result.results)
                        
                        # Update progress
                        completed = sum(1 for r in batch_result.results if r.success)
                        failed = sum(1 for r in batch_result.results if not r.success)
                        progress_tracker.update(completed=completed, failed=failed)
                        
                        logger.debug(f"Batch {batch_idx} completed: {batch_result.files_processed} files in {batch_result.processing_time:.2f}s")
                        
                    except Exception as e:
                        logger.error(f"Batch {batch_idx} failed: {e}")
                        # Mark all files in this batch as failed
                        batch_size = len(batches[batch_idx])
                        progress_tracker.update(failed=batch_size)
                        
                        # Add failed results for all files in the batch
                        for task in batches[batch_idx]:
                            all_results.append(ExtractionResult(
                                file_path=task.file_path,
                                symbols=[],
                                success=False,
                                error=f"Batch processing failed: {e}"
                            ))
                    
                    # Report progress
                    if progress_callback:
                        progress_callback(progress_tracker.get_progress())
        
        total_time = time.time() - start_time
        successful = sum(1 for r in all_results if r.success)
        failed = len(all_results) - successful
        
        logger.info(f"Parallel extraction completed: {successful} successful, {failed} failed in {total_time:.2f}s")
        
        return all_results
    
    async def extract_symbols_from_files(
        self,
        file_paths: List[str],
        include_docs_and_comments: bool = False
    ) -> List[Symbol]:
        """
        Compatibility method that returns Symbol objects like the original enhancer
        
        Args:
            file_paths: List of file paths to process  
            include_docs_and_comments: Whether to include documentation and comments
            
        Returns:
            List of Symbol objects from all files
        """
        results = await self.extract_symbols_parallel(file_paths, include_docs_and_comments)
        
        all_symbols = []
        for result in results:
            if result.success:
                # Convert dict results back to Symbol objects
                for symbol_dict in result.symbols:
                    symbol = Symbol(**symbol_dict)
                    all_symbols.append(symbol)
        
        return all_symbols