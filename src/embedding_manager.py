#!/usr/bin/env python3
"""
Embedding manager for semantic code search using sentence-transformers
"""

import re
from typing import List, Dict, Optional, Union
import numpy as np
from sentence_transformers import SentenceTransformer
import logging
import warnings

# Suppress the specific FutureWarning about encoder_attention_mask
warnings.filterwarnings("ignore", message=".*encoder_attention_mask.*is deprecated.*", category=FutureWarning)

try:
    from src.embedding_config import EmbeddingConfig, ModelConfig
except ImportError:
    from .embedding_config import EmbeddingConfig, ModelConfig

logger = logging.getLogger("embedding-manager")


class EmbeddingManager:
    """Manages code embeddings using sentence-transformers"""
    
    def __init__(self, 
                 model_name: Optional[str] = None,
                 config: Optional[Union[EmbeddingConfig, str]] = None):
        """Initialize with specified model or configuration
        
        Args:
            model_name: HuggingFace model name for sentence-transformers (deprecated, use config)
            config: EmbeddingConfig instance or preset name ("fast", "balanced", "accurate")
        """
        # Handle configuration
        if config is not None:
            if isinstance(config, str):
                # Preset name provided
                self.config = EmbeddingConfig(preset=config)
            elif isinstance(config, EmbeddingConfig):
                self.config = config
            else:
                raise ValueError(f"config must be EmbeddingConfig or preset name, got {type(config)}")
        elif model_name is not None:
            # Legacy support - create config from model name
            logger.warning("Using model_name parameter is deprecated, use config instead")
            self.config = EmbeddingConfig(custom_model=ModelConfig(
                model_name=model_name,
                dimensions=384,  # Assume default
                max_seq_length=256,
                batch_size=32
            ))
        else:
            # Use default configuration
            self.config = EmbeddingConfig()
        
        logger.info(f"Loading embedding model: {self.config.model_name}")
        logger.info(f"Model config: dims={self.config.dimensions}, max_seq={self.config.max_seq_length}")
        
        self.model = SentenceTransformer(self.config.model_name)
        self.embedding_dim = self.model.get_sentence_embedding_dimension()
        
        # Verify dimensions match
        if self.embedding_dim != self.config.dimensions:
            logger.warning(f"Model dimension mismatch: expected {self.config.dimensions}, got {self.embedding_dim}")
            logger.warning("Using actual model dimensions")
        
        logger.info(f"Model loaded. Embedding dimension: {self.embedding_dim}")
    
    def create_code_context(self, symbol: Dict) -> str:
        """Create enriched text representation of code symbol
        
        Args:
            symbol: Dictionary containing symbol information with keys:
                - type: function, class, method, import, env_var, constant, etc.
                - name: symbol name
                - file: file path
                - signature: function/method signature or import statement
                - docstring: documentation string
                - code: actual code content
                - parent: parent class/module
                - language: programming language
        
        Returns:
            Enriched text representation for embedding
        """
        symbol_type = symbol.get('type', 'unknown')
        
        # Handle different symbol types with specialized context
        if symbol_type in ['import', 'import_from']:
            return self._create_import_context(symbol)
        elif symbol_type == 'env_var':
            return self._create_env_var_context(symbol)
        elif symbol_type == 'constant':
            return self._create_constant_context(symbol)
        elif symbol_type == 'comment':
            return self._create_comment_context(symbol)
        elif symbol_type == 'module_doc':
            return self._create_module_doc_context(symbol)
        else:
            # Default handling for functions, classes, methods
            return self._create_default_context(symbol)
    
    def _create_import_context(self, symbol: Dict) -> str:
        """Create context for import statements"""
        parts = []
        parts.append(f"Type: import statement")
        parts.append(f"Module: {symbol.get('name', 'unknown')}")
        
        if symbol.get('signature'):
            parts.append(f"Import: {symbol['signature']}")
        
        # Add file context for understanding where it's used
        if symbol.get('file'):
            parts.append(f"Used in: {symbol['file']}")
        
        # For imports, the module name itself is the key signal
        module_name = symbol.get('name', '')
        if '.' in module_name:
            # For dotted imports, include parent package
            parent_package = module_name.split('.')[0]
            parts.append(f"Package: {parent_package}")
        
        # Common import patterns for searchability
        if any(pkg in module_name.lower() for pkg in ['os', 'sys', 'path']):
            parts.append("Category: system/filesystem")
        elif any(pkg in module_name.lower() for pkg in ['numpy', 'pandas', 'scipy']):
            parts.append("Category: data science")
        elif any(pkg in module_name.lower() for pkg in ['requests', 'urllib', 'http']):
            parts.append("Category: networking/http")
        
        return '\n'.join(parts)
    
    def _create_env_var_context(self, symbol: Dict) -> str:
        """Create context for environment variable access"""
        parts = []
        parts.append(f"Type: environment variable")
        parts.append(f"Variable: {symbol.get('name', 'unknown')}")
        
        if symbol.get('signature'):
            # Signature contains access pattern
            parts.append(f"Access: {symbol['signature']}")
        
        # Add semantic hints based on common env var patterns
        var_name = symbol.get('name', '').upper()
        if any(key in var_name for key in ['KEY', 'TOKEN', 'SECRET', 'PASSWORD']):
            parts.append("Category: credentials/secrets")
        elif any(key in var_name for key in ['URL', 'HOST', 'PORT', 'ENDPOINT']):
            parts.append("Category: configuration/connection")
        elif any(key in var_name for key in ['PATH', 'DIR', 'FOLDER']):
            parts.append("Category: filesystem/paths")
        elif any(key in var_name for key in ['DEBUG', 'LOG', 'VERBOSE']):
            parts.append("Category: debugging/logging")
        
        if symbol.get('file'):
            parts.append(f"File: {symbol['file']}")
        
        # Include the code context for better matching
        if symbol.get('code'):
            parts.append(f"Context: {symbol['code'][:100]}")
        
        return '\n'.join(parts)
    
    def _create_constant_context(self, symbol: Dict) -> str:
        """Create context for module-level constants"""
        parts = []
        parts.append(f"Type: constant/configuration")
        parts.append(f"Name: {symbol.get('name', 'unknown')}")
        
        if symbol.get('signature'):
            parts.append(f"Definition: {symbol['signature']}")
        
        # Categorize based on naming patterns
        const_name = symbol.get('name', '')
        if const_name.isupper():
            parts.append("Style: UPPER_CASE constant")
        elif 'config' in const_name.lower():
            parts.append("Category: configuration")
        elif 'setting' in const_name.lower():
            parts.append("Category: settings")
        
        if symbol.get('file'):
            parts.append(f"File: {symbol['file']}")
        
        return '\n'.join(parts)
    
    def _create_comment_context(self, symbol: Dict) -> str:
        """Create context for comments"""
        parts = []
        parts.append(f"Type: code comment")
        
        # Check if it's a special comment (TODO, FIXME, etc.)
        signature = symbol.get('signature', '')
        if signature and signature != 'comment':
            parts.append(f"Category: {signature} comment")
        
        # The comment text itself
        comment_text = symbol.get('code', '')
        parts.append(f"Comment: {comment_text}")
        
        # File location
        if symbol.get('file'):
            parts.append(f"File: {symbol['file']}")
            parts.append(f"Line: {symbol.get('line', 'unknown')}")
        
        # Try to infer what the comment is about
        if any(word in comment_text.lower() for word in ['param', 'arg', 'return', 'raise']):
            parts.append("Context: function documentation")
        elif any(word in comment_text.lower() for word in ['class', 'inherit', 'attribute']):
            parts.append("Context: class documentation")
        elif any(word in comment_text.lower() for word in ['todo', 'fixme', 'hack', 'bug']):
            parts.append("Context: development note")
        elif any(word in comment_text.lower() for word in ['example', 'usage', 'note']):
            parts.append("Context: usage guidance")
        
        return '\n'.join(parts)
    
    def _create_module_doc_context(self, symbol: Dict) -> str:
        """Create context for module-level documentation"""
        parts = []
        parts.append(f"Type: module documentation")
        parts.append(f"Module: {symbol.get('file', 'unknown')}")
        
        # The docstring content
        docstring = symbol.get('docstring', symbol.get('code', ''))
        
        # Extract key sections if present
        if 'Overview' in docstring or 'Description' in docstring:
            parts.append("Contains: module overview")
        if 'Usage' in docstring or 'Example' in docstring:
            parts.append("Contains: usage examples")
        if 'API' in docstring or 'Interface' in docstring:
            parts.append("Contains: API documentation")
        if 'Copyright' in docstring or 'License' in docstring:
            parts.append("Contains: licensing information")
        
        # Include a portion of the docstring
        doc_preview = docstring[:300] + "..." if len(docstring) > 300 else docstring
        parts.append(f"Documentation:\n{doc_preview}")
        
        return '\n'.join(parts)
    
    def _create_default_context(self, symbol: Dict) -> str:
        """Default context creation for functions, classes, methods"""
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
    
    def embed_batch(self, texts: List[str], batch_size: Optional[int] = None, show_progress: bool = True) -> np.ndarray:
        """Embed multiple texts in batches
        
        Args:
            texts: List of texts to embed
            batch_size: Batch size for processing (uses config default if not specified)
            show_progress: Whether to show progress bar
            
        Returns:
            Array of embeddings
        """
        # Use config batch size if not specified
        if batch_size is None:
            batch_size = self.config.batch_size
            
        return self.model.encode(
            texts,
            batch_size=batch_size,
            show_progress_bar=show_progress,
            convert_to_numpy=True,
            normalize_embeddings=self.config.normalize_embeddings
        )
    
    def embed_code_symbols(self, symbols: List[Dict], batch_size: Optional[int] = None, show_progress: bool = True) -> np.ndarray:
        """Embed code symbols with enriched context
        
        Args:
            symbols: List of symbol dictionaries
            batch_size: Batch size for processing (uses config default if not specified)
            show_progress: Whether to show progress bar
            
        Returns:
            Array of embeddings
        """
        # Create enriched contexts
        contexts = [self.create_code_context(symbol) for symbol in symbols]
        
        # Embed in batches
        return self.embed_batch(contexts, batch_size, show_progress)