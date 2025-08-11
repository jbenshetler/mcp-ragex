#!/usr/bin/env python3
"""
Vector store for semantic code search using ChromaDB
"""

import os
from typing import List, Dict, Optional, Any, Union
import numpy as np
import chromadb
from chromadb.config import Settings
import logging
from pathlib import Path

try:
    from src.ragex_core.embedding_config import EmbeddingConfig
except ImportError:
    from .embedding_config import EmbeddingConfig

logger = logging.getLogger("vector-store")


class CodeVectorStore:
    """Manages code embeddings in ChromaDB"""
    
    def __init__(self, 
                 persist_directory: Optional[str] = None,
                 collection_name: Optional[str] = None,
                 config: Optional[Union[EmbeddingConfig, str]] = None):
        """Initialize ChromaDB with persistent storage
        
        Args:
            persist_directory: Directory to store the database (uses config default if not specified)
            collection_name: Name of the collection (uses config default if not specified)
            config: EmbeddingConfig instance or preset name
        """
        # Handle configuration
        if config is not None:
            if isinstance(config, str):
                self.config = EmbeddingConfig(preset=config)
            elif isinstance(config, EmbeddingConfig):
                self.config = config
            else:
                raise ValueError(f"config must be EmbeddingConfig or preset name, got {type(config)}")
        else:
            self.config = EmbeddingConfig()
        
        # Use provided values or fall back to config
        self.persist_directory = Path(persist_directory or self.config.persist_directory).absolute()
        self.collection_name = collection_name or self.config.collection_name
        
        self.persist_directory.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"Initializing ChromaDB at {self.persist_directory}")
        logger.info(f"Collection name: {self.collection_name}")
        
        # Initialize ChromaDB client with persistence
        self.client = chromadb.PersistentClient(
            path=str(self.persist_directory),
            settings=Settings(
                allow_reset=True,
                anonymized_telemetry=False
            )
        )
        
        # Get or create collection with configurable HNSW parameters
        self.collection = self.client.get_or_create_collection(
            name=self.collection_name,
            metadata={
                "hnsw:space": "cosine",
                "hnsw:construction_ef": self.config.hnsw_construction_ef,
                "hnsw:search_ef": self.config.hnsw_search_ef,
                "hnsw:M": self.config.hnsw_M
            }
        )
        
        logger.info(f"Collection '{self.collection_name}' ready. Current count: {self.collection.count()}")
        
        # Validate embedding dimensions if collection has data
        self._validate_embedding_dimensions()
    
    def _validate_embedding_dimensions(self):
        """Validate that existing embeddings match current model dimensions"""
        try:
            count = self.collection.count()
            if count == 0:
                # No existing data, validation not needed
                return
                
            # Get a sample embedding to check dimensions
            results = self.collection.get(limit=1, include=['embeddings'])
            if results['embeddings']:
                existing_dim = len(results['embeddings'][0])
                expected_dim = self.config.dimensions
                
                if existing_dim != expected_dim:
                    error_msg = (f"❌ CRITICAL: Embedding dimension mismatch detected in ChromaDB!\n"
                               f"   Collection has embeddings with {existing_dim} dimensions\n"
                               f"   Current model expects {expected_dim} dimensions\n"
                               f"   \n"
                               f"   This indicates a model change without proper reindexing.\n"
                               f"   The search results will be meaningless and corrupted.\n"
                               f"   \n"
                               f"   🔧 Solution: Delete project and reindex:\n"
                               f"     ragex rm <project-name>\n"
                               f"     ragex index . --model <desired-model>")
                    
                    logger.error(error_msg)
                    raise ValueError(f"Embedding dimension mismatch: collection={existing_dim}d, model={expected_dim}d")
                else:
                    logger.debug(f"✅ Embedding dimensions validated: {existing_dim}d")
        except Exception as e:
            if "dimension mismatch" in str(e).lower():
                # Re-raise dimension errors
                raise
            else:
                # Log other validation errors but don't fail
                logger.warning(f"Could not validate embedding dimensions: {e}")
    
    def _prepare_batch_data(self, symbols: List[Dict], start_idx: int = 0) -> tuple:
        """Prepare a batch of symbols for ChromaDB storage
        
        Args:
            symbols: List of symbol dictionaries to process
            start_idx: Starting index for unique ID generation
            
        Returns:
            Tuple of (ids, documents, metadatas) ready for ChromaDB
        """
        ids = []
        documents = []
        metadatas = []
        
        for i, symbol in enumerate(symbols):
            # Create unique ID - include type and global index to avoid duplicates
            global_idx = start_idx + i
            symbol_id = f"{symbol['file']}:{symbol.get('line', 0)}:{symbol['type']}:{symbol['name']}:{global_idx}"
            ids.append(symbol_id)
            
            # Store code as document
            documents.append(symbol.get('code', ''))
            
            # Store metadata for filtering and display (only meaningful values)
            metadata = {
                "type": symbol.get('type', 'unknown'),
                "name": symbol.get('name', 'unknown'),
                "file": symbol.get('file', ''),
                "line": symbol.get('line', 0),
                "language": symbol.get('language', ''),
                "file_checksum": symbol.get('file_checksum', ''),  # NEW: Store file checksum
            }
            
            # Only add optional fields if they have values
            if symbol.get('parent'):
                metadata["parent"] = symbol['parent']
            if symbol.get('signature'):
                metadata["signature"] = symbol['signature']
            
            # Add docstring if available (ChromaDB has metadata size limits)
            docstring = symbol.get('docstring')
            if docstring and len(docstring) < 1000:
                metadata['docstring'] = docstring
            
            metadatas.append(metadata)
        
        return ids, documents, metadatas
    
    def add_symbols(self, symbols: List[Dict], embeddings: np.ndarray) -> Dict[str, Any]:
        """Add code symbols with their embeddings to the store
        
        Args:
            symbols: List of symbol dictionaries
            embeddings: Numpy array of embeddings
            
        Returns:
            Dictionary with indexing statistics
        """
        if len(symbols) != len(embeddings):
            raise ValueError(f"Number of symbols ({len(symbols)}) must match number of embeddings ({len(embeddings)})")
        
        if len(symbols) == 0:
            return {"added": 0, "total": self.collection.count()}
        
        # ChromaDB has a maximum batch size limit
        MAX_BATCH_SIZE = 5000  # Set slightly below 5461 limit for safety
        
        logger.info(f"Adding {len(symbols)} symbols to vector store")
        
        # Process in batches if necessary
        total_added = 0
        num_batches = (len(symbols) + MAX_BATCH_SIZE - 1) // MAX_BATCH_SIZE
        
        for batch_num in range(num_batches):
            batch_start = batch_num * MAX_BATCH_SIZE
            batch_end = min(batch_start + MAX_BATCH_SIZE, len(symbols))
            
            # Extract batch data
            batch_symbols = symbols[batch_start:batch_end]
            batch_embeddings = embeddings[batch_start:batch_end]
            
            # Prepare batch for ChromaDB
            ids, documents, metadatas = self._prepare_batch_data(batch_symbols, batch_start)
            
            # Add batch to collection
            batch_size = len(batch_symbols)
            logger.info(f"Adding batch {batch_num + 1}/{num_batches} ({batch_size} symbols)")
            
            self.collection.add(
                embeddings=batch_embeddings.tolist(),  # ChromaDB expects list, not numpy array
                documents=documents,
                metadatas=metadatas,
                ids=ids
            )
            
            total_added += batch_size
        
        new_count = self.collection.count()
        logger.info(f"Added {total_added} symbols. Total in store: {new_count}")
        
        return {
            "added": total_added,
            "total": new_count
        }
    
    def search(self, 
              query_embedding: np.ndarray, 
              limit: int = 20,
              where: Optional[Dict] = None,
              include: Optional[List[str]] = None) -> Dict[str, Any]:
        """Search for similar code using vector similarity
        
        Args:
            query_embedding: Query embedding vector
            limit: Maximum number of results
            where: Optional metadata filter (e.g., {"language": "python"})
            include: What to include in results (default: all)
            
        Returns:
            Search results with metadata and distances
        """
        if include is None:
            include = ["metadatas", "documents", "distances"]
        
        # Ensure query_embedding is 2D array for ChromaDB
        if query_embedding.ndim == 1:
            query_embedding = query_embedding.reshape(1, -1)
        
        logger.debug(f"Searching with limit={limit}, where={where}")
        
        results = self.collection.query(
            query_embeddings=query_embedding.tolist(),
            n_results=limit,
            where=where,
            include=include
        )
        
        # Format results
        formatted_results = []
        
        if results['ids'] and len(results['ids'][0]) > 0:
            for i in range(len(results['ids'][0])):
                result = {
                    "id": results['ids'][0][i],
                    "distance": results['distances'][0][i],
                    "metadata": results['metadatas'][0][i] if 'metadatas' in results else {},
                    "code": results['documents'][0][i] if 'documents' in results else ""
                }
                formatted_results.append(result)
        
        return {
            "results": formatted_results,
            "total": len(formatted_results)
        }
    
    def delete_by_file(self, file_path: str) -> int:
        """Delete all symbols from a specific file
        
        Args:
            file_path: Path to the file
            
        Returns:
            Number of symbols deleted
        """
        # Get IDs of symbols from this file
        results = self.collection.get(
            where={"file": file_path},
            include=["metadatas"]
        )
        
        if results['ids']:
            logger.info(f"Deleting {len(results['ids'])} symbols from {file_path}")
            self.collection.delete(ids=results['ids'])
            return len(results['ids'])
        
        return 0
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get statistics about the vector store
        
        Returns:
            Dictionary with store statistics
        """
        # Get total count
        total_count = self.collection.count()
        
        # Sample to get metadata statistics
        sample_size = min(1000, total_count)
        if sample_size > 0:
            sample = self.collection.get(limit=sample_size, include=["metadatas"])
            
            # Count by type
            type_counts = {}
            language_counts = {}
            file_counts = {}
            
            for metadata in sample['metadatas']:
                # Count types
                symbol_type = metadata.get('type', 'unknown')
                type_counts[symbol_type] = type_counts.get(symbol_type, 0) + 1
                
                # Count languages
                language = metadata.get('language', 'unknown')
                language_counts[language] = language_counts.get(language, 0) + 1
                
                # Count files
                file_path = metadata.get('file', 'unknown')
                file_counts[file_path] = file_counts.get(file_path, 0) + 1
            
            # Extrapolate if we only sampled
            if sample_size < total_count:
                scale_factor = total_count / sample_size
                type_counts = {k: int(v * scale_factor) for k, v in type_counts.items()}
                language_counts = {k: int(v * scale_factor) for k, v in language_counts.items()}
        else:
            type_counts = {}
            language_counts = {}
            file_counts = {}
        
        return {
            "total_symbols": total_count,
            "types": type_counts,
            "languages": language_counts,
            "unique_files": len(file_counts),
            "persist_directory": str(self.persist_directory),
            "collection_name": self.collection_name
        }
    
    def clear(self) -> Dict[str, str]:
        """Clear all data from the vector store
        
        Returns:
            Status message
        """
        logger.warning("Clearing all data from vector store")
        # ChromaDB requires getting all IDs first, then deleting
        # Get all document IDs
        all_data = self.collection.get()
        if all_data['ids']:
            self.collection.delete(ids=all_data['ids'])
        
        return {
            "status": "cleared",
            "message": f"All symbols removed from store"
        }
    
    def reset(self) -> Dict[str, str]:
        """Completely reset the vector store
        
        Returns:
            Status message
        """
        logger.warning("Resetting vector store")
        
        # Delete the collection
        self.client.delete_collection(self.collection_name)
        
        # Recreate it with configurable HNSW parameters
        self.collection = self.client.get_or_create_collection(
            name=self.collection_name,
            metadata={
                "hnsw:space": "cosine",
                "hnsw:construction_ef": self.config.hnsw_construction_ef,
                "hnsw:search_ef": self.config.hnsw_search_ef,
                "hnsw:M": self.config.hnsw_M
            }
        )
        
        return {
            "status": "reset",
            "message": "Vector store reset to empty state"
        }
    
    def get_file_checksums(self) -> Dict[str, str]:
        """
        Retrieve all stored file checksums.
        
        Returns:
            Dictionary mapping file paths to their checksums
            {file_path: checksum}
        """
        logger.info("Retrieving file checksums from vector store")
        
        # Get all metadata containing file checksums
        all_data = self.collection.get(include=["metadatas"])
        
        file_checksums = {}
        for metadata in all_data.get('metadatas', []):
            file_path = metadata.get('file', '')
            file_checksum = metadata.get('file_checksum', '')
            
            if file_path and file_checksum:
                # Use the most recent checksum for each file
                # (in case of multiple symbols per file)
                file_checksums[file_path] = file_checksum
        
        logger.info(f"Retrieved checksums for {len(file_checksums)} files")
        return file_checksums
    
    def get_files_by_checksum(self, checksum: str) -> List[str]:
        """
        Get all files with a specific checksum.
        
        This is useful for detecting moved/renamed files with the same content.
        
        Args:
            checksum: The checksum to search for
            
        Returns:
            List of file paths with the given checksum
        """
        results = self.collection.get(
            where={"file_checksum": checksum},
            include=["metadatas"]
        )
        
        files = []
        for metadata in results.get('metadatas', []):
            file_path = metadata.get('file', '')
            if file_path and file_path not in files:
                files.append(file_path)
        
        return files
    
    def get_file_info(self, file_path: str) -> Optional[Dict[str, Any]]:
        """
        Get information about a specific file in the index.
        
        Args:
            file_path: Path to the file
            
        Returns:
            Dictionary with file info or None if not found
        """
        results = self.collection.get(
            where={"file": file_path},
            include=["metadatas"]
        )
        
        if not results.get('metadatas'):
            return None
        
        # Get info from first symbol in the file
        metadata = results['metadatas'][0]
        symbol_count = len(results['metadatas'])
        
        return {
            "file_path": file_path,
            "checksum": metadata.get('file_checksum', ''),
            "language": metadata.get('language', ''),
            "symbol_count": symbol_count
        }