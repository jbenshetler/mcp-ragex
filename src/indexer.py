#!/usr/bin/env python3
"""
Code indexer for building semantic search index
"""

import os
import asyncio
from pathlib import Path
from typing import List, Dict, Optional, Any, Callable, Union
import logging
from tqdm import tqdm
import warnings

# Suppress the specific FutureWarning about encoder_attention_mask
warnings.filterwarnings("ignore", message=".*encoder_attention_mask.*is deprecated.*", category=FutureWarning)

from src.tree_sitter_enhancer import TreeSitterEnhancer
from src.embedding_manager import EmbeddingManager
from src.vector_store import CodeVectorStore
from src.pattern_matcher import PatternMatcher

logger = logging.getLogger("code-indexer")


from src.embedding_config import EmbeddingConfig


class CodeIndexer:
    """Indexes code for semantic search"""
    
    def __init__(self, 
                 persist_directory: Optional[str] = None,
                 model_name: Optional[str] = None,
                 config: Optional[Union[EmbeddingConfig, str]] = None):
        """Initialize the indexer with components
        
        Args:
            persist_directory: Directory for ChromaDB storage (uses config default if not specified)
            model_name: Sentence transformer model to use (deprecated, use config)
            config: EmbeddingConfig instance or preset name ("fast", "balanced", "accurate")
        """
        logger.info("Initializing CodeIndexer")
        
        # Handle configuration
        if config is not None:
            if isinstance(config, str):
                self.config = EmbeddingConfig(preset=config)
            elif isinstance(config, EmbeddingConfig):
                self.config = config
            else:
                raise ValueError(f"config must be EmbeddingConfig or preset name, got {type(config)}")
        elif model_name is not None:
            # Legacy support
            logger.warning("Using model_name parameter is deprecated, use config instead")
            from .embedding_config import ModelConfig
            self.config = EmbeddingConfig(custom_model=ModelConfig(
                model_name=model_name,
                dimensions=384,
                max_seq_length=256,
                batch_size=32
            ))
        else:
            self.config = EmbeddingConfig()
        
        # Override persist directory if provided
        if persist_directory:
            self.config._persist_directory = persist_directory
        
        # Initialize components with shared config
        try:
            self.tree_sitter = TreeSitterEnhancer()
        except Exception as e:
            logger.warning(f"Tree-sitter enhancer disabled due to: {e}")
            self.tree_sitter = None
        self.embedder = EmbeddingManager(config=self.config)
        self.vector_store = CodeVectorStore(config=self.config)
        self.pattern_matcher = PatternMatcher()
        
        # Supported file extensions
        self.supported_extensions = {
            '.py': 'python',
            '.js': 'javascript',
            '.jsx': 'javascript',
            '.ts': 'typescript',
            '.tsx': 'typescript'
        }
    
    def find_code_files(self, paths: List[str]) -> List[Path]:
        """Find all code files in the given paths
        
        Args:
            paths: List of paths to search
            
        Returns:
            List of code file paths
        """
        all_files = []
        
        for path_str in paths:
            path = Path(path_str).resolve()
            
            if path.is_file():
                # Single file
                if path.suffix in self.supported_extensions:
                    all_files.append(path)
            elif path.is_dir():
                # Set pattern matcher working directory to the directory being indexed
                # This ensures patterns like .venv/** work correctly
                self.pattern_matcher.set_working_directory(str(path))
                
                # Directory - search recursively
                for ext in self.supported_extensions:
                    for file_path in path.rglob(f"*{ext}"):
                        if not self.pattern_matcher.should_exclude(str(file_path)):
                            all_files.append(file_path)
        
        # Remove duplicates while preserving order
        seen = set()
        unique_files = []
        for f in all_files:
            if f not in seen:
                seen.add(f)
                unique_files.append(f)
        
        return unique_files
    
    async def extract_symbols_from_file(self, file_path: Path) -> List[Dict]:
        """Extract symbols from a single file
        
        Args:
            file_path: Path to the file
            
        Returns:
            List of symbol dictionaries
        """
        try:
            # Read file content
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Determine language
            language = self.supported_extensions.get(file_path.suffix, 'unknown')
            
            # Extract symbols using Tree-sitter
            # Include comments and docstrings for semantic search
            symbols = await self.tree_sitter.extract_symbols(str(file_path), include_docs_and_comments=True)
            
            # Convert Symbol objects to dictionaries
            symbol_dicts = []
            for symbol in symbols:
                # Convert Symbol object to dictionary
                symbol_dict = {
                    'name': symbol.name,
                    'type': symbol.type,
                    'file': str(file_path),
                    'line': symbol.line,
                    'end_line': symbol.end_line,
                    'column': symbol.column,
                    'parent': symbol.parent,
                    'signature': symbol.signature,
                    'docstring': symbol.docstring,
                    'language': language,
                    'code': symbol.code if hasattr(symbol, 'code') else ''
                }
                
                # Get code content if we have position info
                if hasattr(symbol, 'start_byte') and hasattr(symbol, 'end_byte'):
                    symbol_dict['code'] = content[symbol.start_byte:symbol.end_byte]
                elif not symbol_dict['code'] and symbol.line and symbol.end_line:
                    # Extract code based on line numbers
                    lines = content.split('\n')
                    start_idx = max(0, symbol.line - 1)
                    end_idx = min(len(lines), symbol.end_line)
                    symbol_dict['code'] = '\n'.join(lines[start_idx:end_idx])
                
                symbol_dicts.append(symbol_dict)
            
            return symbol_dicts
            
        except Exception as e:
            logger.error(f"Failed to extract symbols from {file_path}: {e}")
            return []
    
    async def index_codebase(self, 
                           paths: List[str], 
                           force: bool = False,
                           progress_callback: Optional[Callable] = None) -> Dict[str, Any]:
        """Index an entire codebase for semantic search
        
        Args:
            paths: List of paths to index
            force: Force reindexing even if index exists
            progress_callback: Optional callback for progress updates
            
        Returns:
            Dictionary with indexing statistics
        """
        # Check for ignore file in the first directory path (if any directories provided)
        for path_str in paths:
            path = Path(path_str).resolve()
            if path.is_dir():
                # Check and warn once for the top-level directory being indexed
                PatternMatcher.check_ignore_file(path)
                break
        
        # Check if index exists
        stats = self.vector_store.get_statistics()
        if not force and stats['total_symbols'] > 0:
            logger.info(f"Index already exists with {stats['total_symbols']} symbols")
            return {
                "status": "existing",
                "symbols_indexed": stats['total_symbols'],
                "files_processed": stats['unique_files']
            }
        
        # Clear existing index if forcing
        if force and stats['total_symbols'] > 0:
            logger.info("Clearing existing index")
            self.vector_store.clear()
        
        # Find all code files
        logger.info(f"Searching for code files in: {paths}")
        all_files = self.find_code_files(paths)
        logger.info(f"Found {len(all_files)} code files to index")
        
        if not all_files:
            return {
                "status": "no_files",
                "symbols_indexed": 0,
                "files_processed": 0
            }
        
        # Extract symbols from all files
        all_symbols = []
        failed_files = []
        
        # Process files with progress bar
        with tqdm(total=len(all_files), desc="Extracting symbols") as pbar:
            for file_path in all_files:
                symbols = await self.extract_symbols_from_file(file_path)
                
                if symbols:
                    all_symbols.extend(symbols)
                    status = "success"
                else:
                    failed_files.append(str(file_path))
                    status = "failed"
                
                # Update progress
                pbar.update(1)
                
                # Call progress callback if provided
                if progress_callback:
                    await progress_callback(str(file_path), status)
        
        logger.info(f"Extracted {len(all_symbols)} symbols from {len(all_files) - len(failed_files)} files")
        
        if not all_symbols:
            return {
                "status": "no_symbols",
                "symbols_indexed": 0,
                "files_processed": len(all_files),
                "failed_files": failed_files
            }
        
        # Create embeddings
        logger.info("Creating embeddings for symbols")
        embeddings = self.embedder.embed_code_symbols(
            all_symbols,
            batch_size=32,
            show_progress=True
        )
        
        # Store in vector database
        logger.info("Storing embeddings in vector database")
        result = self.vector_store.add_symbols(all_symbols, embeddings)
        
        return {
            "status": "complete",
            "symbols_indexed": len(all_symbols),
            "files_processed": len(all_files) - len(failed_files),
            "failed_files": failed_files,
            "total_in_store": result['total']
        }
    
    async def get_index_statistics(self) -> Dict[str, Any]:
        """Get detailed statistics about the index
        
        Returns:
            Dictionary with index statistics
        """
        stats = self.vector_store.get_statistics()
        
        # Add more detailed breakdowns
        if stats['total_symbols'] > 0:
            # Count different symbol types
            type_counts = stats.get('types', {})
            
            stats.update({
                'function_count': type_counts.get('function', 0),
                'class_count': type_counts.get('class', 0),
                'method_count': type_counts.get('method', 0),
                'variable_count': type_counts.get('variable', 0),
            })
            
            # Estimate index size
            index_path = Path(stats['persist_directory'])
            if index_path.exists():
                # Calculate directory size
                total_size = sum(f.stat().st_size for f in index_path.rglob('*') if f.is_file())
                stats['index_size_mb'] = total_size / (1024 * 1024)
        
        return stats
    
    async def update_file(self, file_path: str) -> Dict[str, Any]:
        """Update index for a single file
        
        Args:
            file_path: Path to the file to update
            
        Returns:
            Update statistics
        """
        # Delete existing symbols from this file
        deleted = self.vector_store.delete_by_file(file_path)
        logger.info(f"Deleted {deleted} existing symbols from {file_path}")
        
        # Extract new symbols
        path = Path(file_path)
        if not path.exists():
            return {
                "status": "file_not_found",
                "deleted": deleted,
                "added": 0
            }
        
        symbols = await self.extract_symbols_from_file(path)
        
        if not symbols:
            return {
                "status": "no_symbols",
                "deleted": deleted,
                "added": 0
            }
        
        # Create embeddings
        embeddings = self.embedder.embed_code_symbols(symbols, show_progress=False)
        
        # Store in database
        result = self.vector_store.add_symbols(symbols, embeddings)
        
        return {
            "status": "updated",
            "deleted": deleted,
            "added": len(symbols),
            "total_in_store": result['total']
        }