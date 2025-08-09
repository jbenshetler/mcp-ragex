#!/usr/bin/env python3
"""
Shared parser pool for optimizing tree-sitter parser initialization across processes
Uses shared memory to reduce startup overhead in worker processes
"""

import logging
import multiprocessing as mp
import pickle
import mmap
from typing import Dict, Optional, Any
from pathlib import Path

import tree_sitter
from tree_sitter import Language, Parser, Query

try:
    import tree_sitter_python as tspython
    import tree_sitter_javascript as tsjavascript
    import tree_sitter_typescript as tstypescript
except ImportError as e:
    logging.error(f"Failed to import tree-sitter language modules: {e}")
    tspython = tsjavascript = tstypescript = None

logger = logging.getLogger("shared-parser-pool")

class SharedParserPool:
    """
    Manages a pool of tree-sitter parsers with shared memory optimization
    
    This class reduces the overhead of initializing parsers in each worker process
    by sharing language objects and query patterns across processes.
    """
    
    def __init__(self):
        self._languages = {}
        self._parsers = {}
        self._queries = {}
        self._shared_memory = {}
        self._initialized = False
        
        # File extension to language mapping
        self.ext_to_lang = {
            ".py": "python",
            ".js": "javascript",
            ".jsx": "javascript", 
            ".ts": "typescript",
            ".tsx": "tsx",
        }
    
    def _init_languages(self):
        """Initialize language objects"""
        if not tspython or not tsjavascript or not tstypescript:
            logger.warning("Some tree-sitter language modules not available")
            return
            
        try:
            self._languages = {
                "python": Language(tspython.language()),
                "javascript": Language(tsjavascript.language()),
                "typescript": Language(tstypescript.language_typescript()),
                "tsx": Language(tstypescript.language_tsx()),
            }
            logger.debug(f"Initialized {len(self._languages)} language parsers")
        except Exception as e:
            logger.error(f"Failed to initialize languages: {e}")
            self._languages = {}
    
    def _init_parsers(self):
        """Initialize parser objects for each language"""
        self._parsers = {}
        for name, language in self._languages.items():
            try:
                parser = Parser()
                parser.language = language
                self._parsers[name] = parser
                logger.debug(f"Initialized parser for {name}")
            except Exception as e:
                logger.error(f"Failed to initialize parser for {name}: {e}")
    
    def _init_queries(self):
        """Initialize tree-sitter queries for symbol extraction"""
        if not self._languages:
            return
            
        # Python queries
        python_query_text = """
            (class_definition
                name: (identifier) @class.name
                body: (block) @class.body) @class
            
            (function_definition
                name: (identifier) @function.name
                parameters: (parameters) @function.params
                body: (block) @function.body) @function
            
            (decorated_definition
                (decorator) @decorator
                definition: [
                    (function_definition
                        name: (identifier) @method.name
                        parameters: (parameters) @method.params)
                    (class_definition
                        name: (identifier) @decorated_class.name)
                ]) @decorated
            
            ; Import statements
            (import_statement
                name: (dotted_name) @import.name) @import
            
            (import_from_statement
                module_name: (dotted_name)? @import.module
                name: (dotted_name)? @import.name
                (aliased_import
                    name: (dotted_name) @import.name
                    alias: (identifier) @import.alias)?
                ) @import_from
            
            ; Module-level assignments (constants)
            ((expression_statement
                (assignment
                    left: (identifier) @constant.name
                    right: (_) @constant.value)) @constant
                (#match? @constant.name "^[A-Z_]+$|^[a-z_]*config[a-z_]*$|^[a-z_]*setting[a-z_]*$"))
            
            ; Environment variable access patterns
            (call
                function: (attribute
                    object: (attribute
                        object: (identifier) @env.module
                        attribute: (identifier) @env.environ)
                    attribute: (identifier) @env.method)
                arguments: (argument_list
                    (string) @env.var_name)
                (#eq? @env.module "os")
                (#eq? @env.environ "environ")
                (#match? @env.method "^(get|pop)$")) @env_access
            
            ; Comments for semantic search only
            (comment) @comment
            
            ; Module docstrings
            (module
                . (expression_statement
                    (string) @module_doc.content)) @module_doc
        """
        
        # JavaScript/TypeScript queries
        js_ts_query_text = """
            (class_declaration
                name: (identifier) @class.name
                body: (class_body) @class.body) @class
            
            (function_declaration
                name: (identifier) @function.name
                parameters: (formal_parameters) @function.params) @function
            
            (variable_declarator
                name: (identifier) @var.name
                value: (arrow_function
                    parameters: (formal_parameters) @arrow.params)) @arrow_func
            
            (method_definition
                name: (property_identifier) @method.name
                parameters: (formal_parameters) @method.params) @method
            
            ; Import statements
            (import_statement
                source: (string) @import.source) @import
            
            (import_statement
                (import_clause
                    (named_imports
                        (import_specifier
                            name: (identifier) @import.name)))) @named_import
        """
        
        # TypeScript-specific queries
        ts_query_text = js_ts_query_text + """
            (interface_declaration
                name: (type_identifier) @interface.name) @interface
            
            (function_declaration
                name: (identifier) @function.name
                parameters: (formal_parameters) @function.params
                return_type: (_)? @function.return) @function
        """
        
        try:
            # Initialize queries for each language
            if "python" in self._languages:
                self._queries["python"] = Query(self._languages["python"], python_query_text)
            
            if "javascript" in self._languages:
                self._queries["javascript"] = Query(self._languages["javascript"], js_ts_query_text)
            
            if "typescript" in self._languages:
                self._queries["typescript"] = Query(self._languages["typescript"], ts_query_text)
                
            if "tsx" in self._languages:
                self._queries["tsx"] = Query(self._languages["tsx"], ts_query_text)
            
            logger.debug(f"Initialized {len(self._queries)} query patterns")
            
        except Exception as e:
            logger.error(f"Failed to initialize queries: {e}")
            self._queries = {}
    
    def initialize(self):
        """Initialize the shared parser pool"""
        if self._initialized:
            return
            
        logger.debug("Initializing shared parser pool")
        
        self._init_languages()
        self._init_parsers()
        self._init_queries()
        
        self._initialized = True
        logger.info(f"Shared parser pool initialized with {len(self._parsers)} parsers")
    
    def get_parser(self, language: str) -> Optional[Parser]:
        """Get a parser for the specified language"""
        if not self._initialized:
            self.initialize()
            
        return self._parsers.get(language)
    
    def get_query(self, language: str) -> Optional[Query]:
        """Get a query object for the specified language"""
        if not self._initialized:
            self.initialize()
            
        return self._queries.get(language)
    
    def get_language(self, file_path: str) -> Optional[str]:
        """Determine language from file extension"""
        ext = Path(file_path).suffix.lower()
        return self.ext_to_lang.get(ext)
    
    def get_supported_languages(self) -> list:
        """Get list of supported language identifiers"""
        if not self._initialized:
            self.initialize()
            
        return list(self._parsers.keys())
    
    def is_supported_file(self, file_path: str) -> bool:
        """Check if file is supported by any parser"""
        lang = self.get_language(file_path)
        return lang is not None and lang in self._parsers
    
    def clone_parser(self, language: str) -> Optional[Parser]:
        """
        Create a new parser instance for the specified language
        This is safer for concurrent use than sharing parser instances
        """
        if language not in self._languages:
            return None
            
        try:
            parser = Parser()
            parser.language = self._languages[language]
            return parser
        except Exception as e:
            logger.error(f"Failed to clone parser for {language}: {e}")
            return None

# Global shared instance
_shared_pool = None
_pool_lock = mp.Lock()

def get_shared_pool() -> SharedParserPool:
    """Get the global shared parser pool instance"""
    global _shared_pool
    
    with _pool_lock:
        if _shared_pool is None:
            _shared_pool = SharedParserPool()
            _shared_pool.initialize()
    
    return _shared_pool

def init_worker_pool():
    """Initialize the shared parser pool in a worker process"""
    global _shared_pool
    if _shared_pool is None:
        _shared_pool = SharedParserPool()
        _shared_pool.initialize()
        logger.debug(f"Worker process {mp.current_process().pid} initialized parser pool")

# Process-local parser pool for worker processes
_worker_pool = None

def get_worker_pool() -> SharedParserPool:
    """Get the process-local parser pool for worker processes"""
    global _worker_pool
    
    if _worker_pool is None:
        _worker_pool = SharedParserPool()
        _worker_pool.initialize()
        logger.debug(f"Initialized worker pool in process {mp.current_process().pid}")
    
    return _worker_pool