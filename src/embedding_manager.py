#!/usr/bin/env python3
"""
Embedding manager for semantic code search using sentence-transformers
"""

import re
from typing import List, Dict, Optional
import numpy as np
from sentence_transformers import SentenceTransformer
import logging

logger = logging.getLogger("embedding-manager")


class EmbeddingManager:
    """Manages code embeddings using sentence-transformers"""
    
    def __init__(self, model_name: str = "sentence-transformers/all-mpnet-base-v2"):
        """Initialize with specified model
        
        Args:
            model_name: HuggingFace model name for sentence-transformers
        """
        logger.info(f"Loading embedding model: {model_name}")
        self.model = SentenceTransformer(model_name)
        self.embedding_dim = self.model.get_sentence_embedding_dimension()
        logger.info(f"Model loaded. Embedding dimension: {self.embedding_dim}")
    
    def create_code_context(self, symbol: Dict) -> str:
        """Create enriched text representation of code symbol
        
        Args:
            symbol: Dictionary containing symbol information with keys:
                - type: function, class, method, etc.
                - name: symbol name
                - file: file path
                - signature: function/method signature
                - docstring: documentation string
                - code: actual code content
                - parent: parent class/module
                - language: programming language
        
        Returns:
            Enriched text representation for embedding
        """
        # Extract keywords from code
        keywords = self._extract_keywords(symbol.get("code", ""))
        
        # Extract function calls
        calls = self._extract_function_calls(symbol.get("code", ""))
        
        # Build context string with multiple signals
        parts = []
        
        # Basic metadata
        parts.append(f"Type: {symbol.get('type', 'unknown')}")
        parts.append(f"Name: {symbol.get('name', 'unknown')}")
        parts.append(f"Language: {symbol.get('language', 'unknown')}")
        
        # File context
        if symbol.get("file"):
            parts.append(f"File: {symbol['file']}")
        
        # Signature is very important for understanding
        if symbol.get("signature"):
            parts.append(f"Signature: {symbol['signature']}")
        
        # Documentation provides intent
        if symbol.get("docstring"):
            parts.append(f"Documentation: {symbol['docstring']}")
        
        # Parent context
        if symbol.get("parent"):
            parts.append(f"Parent: {symbol['parent']}")
        
        # Keywords help with matching
        if keywords:
            parts.append(f"Keywords: {', '.join(keywords[:10])}")
        
        # Function calls show dependencies
        if calls:
            parts.append(f"Calls: {', '.join(calls[:10])}")
        
        # Add a snippet of the actual code
        code = symbol.get("code", "")
        if code:
            # Take first few lines for context
            lines = code.split('\n')[:5]
            code_snippet = '\n'.join(lines)
            parts.append(f"Code snippet:\n{code_snippet}")
        
        return '\n'.join(parts)
    
    def _extract_keywords(self, code: str) -> List[str]:
        """Extract meaningful keywords from code"""
        # Remove comments and strings
        code_clean = re.sub(r'#.*$', '', code, flags=re.MULTILINE)  # Python comments
        code_clean = re.sub(r'//.*$', '', code_clean, flags=re.MULTILINE)  # JS comments
        code_clean = re.sub(r'/\*.*?\*/', '', code_clean, flags=re.DOTALL)  # Block comments
        code_clean = re.sub(r'".*?"|\'.*?\'', '', code_clean)  # Strings
        
        # Extract identifiers
        words = re.findall(r'\b[a-zA-Z_][a-zA-Z0-9_]*\b', code_clean)
        
        # Filter common keywords
        common_keywords = {
            'def', 'class', 'function', 'const', 'let', 'var', 'return',
            'if', 'else', 'for', 'while', 'import', 'from', 'self', 'this',
            'true', 'false', 'null', 'none', 'undefined', 'async', 'await'
        }
        
        keywords = [w for w in words if w.lower() not in common_keywords and len(w) > 2]
        
        # Deduplicate while preserving order
        seen = set()
        unique_keywords = []
        for kw in keywords:
            if kw not in seen:
                seen.add(kw)
                unique_keywords.append(kw)
        
        return unique_keywords
    
    def _extract_function_calls(self, code: str) -> List[str]:
        """Extract function calls from code"""
        # Simple regex-based extraction
        # Matches: function_name( or object.method( or object->method(
        calls = re.findall(r'([a-zA-Z_][a-zA-Z0-9_]*(?:\.[a-zA-Z_][a-zA-Z0-9_]*)*)\s*\(', code)
        
        # Deduplicate
        return list(dict.fromkeys(calls))
    
    def embed_text(self, text: str) -> np.ndarray:
        """Embed a single text string
        
        Args:
            text: Text to embed
            
        Returns:
            Embedding vector
        """
        return self.model.encode(text, convert_to_numpy=True)
    
    def embed_batch(self, texts: List[str], batch_size: int = 32, show_progress: bool = True) -> np.ndarray:
        """Embed multiple texts in batches
        
        Args:
            texts: List of texts to embed
            batch_size: Batch size for processing
            show_progress: Whether to show progress bar
            
        Returns:
            Array of embeddings
        """
        return self.model.encode(
            texts,
            batch_size=batch_size,
            show_progress_bar=show_progress,
            convert_to_numpy=True
        )
    
    def embed_code_symbols(self, symbols: List[Dict], batch_size: int = 32, show_progress: bool = True) -> np.ndarray:
        """Embed code symbols with enriched context
        
        Args:
            symbols: List of symbol dictionaries
            batch_size: Batch size for processing
            show_progress: Whether to show progress bar
            
        Returns:
            Array of embeddings
        """
        # Create enriched contexts
        contexts = [self.create_code_context(symbol) for symbol in symbols]
        
        # Embed in batches
        return self.embed_batch(contexts, batch_size, show_progress)