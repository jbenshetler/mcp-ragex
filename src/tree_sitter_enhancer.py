#!/usr/bin/env python3
"""
Tree-sitter based code parsing for enhanced symbol extraction
"""

import asyncio
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from functools import lru_cache

import tree_sitter
from tree_sitter import Language, Parser
import tree_sitter_python as tspython
import tree_sitter_javascript as tsjavascript
import tree_sitter_typescript as tstypescript

logger = logging.getLogger("tree-sitter-enhancer")

@dataclass
class Symbol:
    """Represents a code symbol (function, class, method, etc.)"""
    name: str
    type: str  # function, class, method, variable, etc.
    file: str
    line: int
    end_line: int
    column: int
    parent: Optional[str] = None  # Parent class/module
    signature: Optional[str] = None  # Function signature
    docstring: Optional[str] = None
    code: Optional[str] = None  # The actual code content
    start_byte: Optional[int] = None  # Start position in file
    end_byte: Optional[int] = None  # End position in file
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "type": self.type,
            "file": self.file,
            "line": self.line,
            "end_line": self.end_line,
            "column": self.column,
            "parent": self.parent,
            "signature": self.signature,
            "docstring": self.docstring,
        }


class TreeSitterEnhancer:
    """Enhances search results with Tree-sitter parsed symbol information"""
    
    def __init__(self, pattern_matcher=None):
        # Import here to avoid circular import
        from pattern_matcher import PatternMatcher
        
        # Pattern matcher for exclusions
        self.pattern_matcher = pattern_matcher or PatternMatcher()
        
        # Initialize language parsers
        self.languages = {
            "python": Language(tspython.language()),
            "javascript": Language(tsjavascript.language()),
            "typescript": Language(tstypescript.language_typescript()),
            "tsx": Language(tstypescript.language_tsx()),
        }
        
        self.parsers = {}
        for name, language in self.languages.items():
            parser = Parser()
            parser.language = language
            self.parsers[name] = parser
        
        # File extension to language mapping
        self.ext_to_lang = {
            ".py": "python",
            ".js": "javascript",
            ".jsx": "javascript",
            ".ts": "typescript",
            ".tsx": "tsx",
        }
        
        # Query patterns for different languages
        self._init_queries()
        
        # Cache for parsed files (limited size for memory)
        self._symbol_cache = {}
        self._cache_size = 100  # Cache last 100 files
    
    def _init_queries(self):
        """Initialize Tree-sitter queries for symbol extraction"""
        
        # Python queries
        self.queries = {
            "python": self.languages["python"].query("""
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
            """),
            
            "javascript": self.languages["javascript"].query("""
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
            """),
            
            "typescript": self.languages["typescript"].query("""
                (class_declaration
                    name: (type_identifier) @class.name
                    body: (class_body) @class.body) @class
                
                (interface_declaration
                    name: (type_identifier) @interface.name) @interface
                
                (function_declaration
                    name: (identifier) @function.name
                    parameters: (formal_parameters) @function.params
                    return_type: (_)? @function.return) @function
                
                (variable_declarator
                    name: (identifier) @var.name
                    value: (arrow_function
                        parameters: (formal_parameters) @arrow.params
                        return_type: (_)? @arrow.return)) @arrow_func
                
                (method_signature
                    name: (property_identifier) @method.name
                    parameters: (formal_parameters) @method.params
                    return_type: (_)? @method.return) @method_sig
            """),
        }
        
        # TSX uses the same queries as TypeScript
        self.queries["tsx"] = self.queries["typescript"]
    
    def _get_language(self, file_path: str) -> Optional[str]:
        """Determine language from file extension"""
        ext = Path(file_path).suffix.lower()
        return self.ext_to_lang.get(ext)
    
    @lru_cache(maxsize=1000)
    def _read_file_cached(self, file_path: str) -> Optional[bytes]:
        """Read file with caching"""
        try:
            return Path(file_path).read_bytes()
        except Exception as e:
            logger.warning(f"Failed to read {file_path}: {e}")
            return None
    
    def _extract_text(self, node, source: bytes) -> str:
        """Extract text from a tree-sitter node"""
        return source[node.start_byte:node.end_byte].decode('utf-8', errors='ignore')
    
    def _extract_docstring(self, node, source: bytes, lang: str) -> Optional[str]:
        """Extract docstring from function/class node"""
        if lang == "python":
            # Look for string as first statement in body
            body = node.child_by_field_name("body")
            if body and body.child_count > 0:
                first_stmt = body.child(0)
                if first_stmt.type == "expression_statement":
                    expr = first_stmt.child(0)
                    if expr and expr.type == "string":
                        return self._extract_text(expr, source).strip('"""\'')
        return None
    
    async def extract_symbols(self, file_path: str) -> List[Symbol]:
        """Extract symbols from a single file"""
        # Check if file should be excluded
        if self.pattern_matcher.should_exclude(file_path):
            return []
        
        lang = self._get_language(file_path)
        if not lang:
            return []
        
        # Check cache first
        if file_path in self._symbol_cache:
            return self._symbol_cache[file_path]
        
        content = self._read_file_cached(file_path)
        if not content:
            return []
        
        parser = self.parsers[lang]
        tree = parser.parse(content)
        
        symbols = []
        query = self.queries[lang]
        captures = query.captures(tree.root_node)
        
        # Debug: Check what captures returns
        logger.debug(f"Captures type: {type(captures)}, length: {len(captures) if hasattr(captures, '__len__') else 'N/A'}")
        if captures:
            logger.debug(f"Captures keys: {list(captures.keys()) if isinstance(captures, dict) else 'Not a dict'}")
        
        # Convert captures dict to list of tuples for processing
        if isinstance(captures, dict):
            # Tree-sitter returns a dict mapping capture names to lists of nodes
            capture_list = []
            for capture_name, nodes in captures.items():
                for node in nodes:
                    capture_list.append((node, capture_name))
            captures = capture_list
        
        # Process captures based on language
        if lang == "python":
            symbols.extend(self._extract_python_symbols(captures, content, file_path))
        elif lang in ["javascript", "typescript", "tsx"]:
            symbols.extend(self._extract_js_ts_symbols(captures, content, file_path, lang))
        
        # Update cache (with size limit)
        if len(self._symbol_cache) >= self._cache_size:
            # Remove oldest entry
            oldest = next(iter(self._symbol_cache))
            del self._symbol_cache[oldest]
        self._symbol_cache[file_path] = symbols
        
        return symbols
    
    def _extract_python_symbols(self, captures, source: bytes, file_path: str) -> List[Symbol]:
        """Extract symbols from Python code"""
        symbols = []
        current_class = None
        
        # Helper function to find nodes by capture name
        def find_capture_node(capture_name_to_find: str, parent_node=None):
            """Find a node with specific capture name, optionally with specific parent"""
            for cap in captures:
                if isinstance(cap, tuple) and len(cap) == 2:
                    n, name = cap
                    if name == capture_name_to_find:
                        if parent_node is None or n.parent == parent_node:
                            return n
            return None
        
        # Debug: log capture structure
        logger.debug(f"Python captures: {len(captures)} items")
        
        for capture in captures:
            # Handle different capture formats
            if isinstance(capture, tuple) and len(capture) == 2:
                node, capture_name = capture
            else:
                logger.error(f"Unexpected capture format: {type(capture)}, value: {capture}")
                continue
            if capture_name == "class":
                class_name_node = None
                for cap in captures:
                    if isinstance(cap, tuple) and len(cap) == 2:
                        n, name = cap
                        if name == "class.name" and n.parent == node:
                            class_name_node = n
                            break
                if class_name_node:
                    class_name = self._extract_text(class_name_node, source)
                    current_class = class_name
                    docstring = self._extract_docstring(node, source, "python")
                    
                    symbols.append(Symbol(
                        name=class_name,
                        type="class",
                        file=file_path,
                        line=class_name_node.start_point[0] + 1,
                        end_line=node.end_point[0] + 1,
                        column=class_name_node.start_point[1],
                        docstring=docstring,
                        code=self._extract_text(node, source),
                        start_byte=node.start_byte,
                        end_byte=node.end_byte,
                    ))
            
            elif capture_name == "function" or capture_name == "method.name":
                is_method = capture_name == "method.name"
                func_node = node.parent if is_method else node
                func_name_node = None
                for cap in captures:
                    if isinstance(cap, tuple) and len(cap) == 2:
                        n, name = cap
                        if name in ["function.name", "method.name"] and (n == node or n.parent == func_node):
                            func_name_node = n
                            break
                
                if func_name_node:
                    func_name = self._extract_text(func_name_node, source)
                    params_node = func_node.child_by_field_name("parameters")
                    signature = self._extract_text(params_node, source) if params_node else "()"
                    docstring = self._extract_docstring(func_node, source, "python")
                    
                    # Check if it's inside a class
                    parent_class = None
                    if current_class and func_node.start_byte > node.start_byte:
                        parent_class = current_class
                    
                    symbols.append(Symbol(
                        name=func_name,
                        type="method" if parent_class else "function",
                        file=file_path,
                        line=func_name_node.start_point[0] + 1,
                        end_line=func_node.end_point[0] + 1,
                        column=func_name_node.start_point[1],
                        parent=parent_class,
                        signature=f"{func_name}{signature}",
                        docstring=docstring,
                        code=self._extract_text(func_node, source),
                        start_byte=func_node.start_byte,
                        end_byte=func_node.end_byte,
                    ))
        
        return symbols
    
    def _extract_js_ts_symbols(self, captures, source: bytes, file_path: str, lang: str) -> List[Symbol]:
        """Extract symbols from JavaScript/TypeScript code"""
        symbols = []
        
        for capture in captures:
            # Handle different capture formats
            if isinstance(capture, tuple) and len(capture) == 2:
                node, capture_name = capture
            else:
                logger.error(f"Unexpected capture format in JS/TS: {type(capture)}, value: {capture}")
                continue
            if capture_name == "class":
                class_name_node = None
                for cap in captures:
                    if isinstance(cap, tuple) and len(cap) == 2:
                        n, name = cap
                        if name == "class.name" and n.parent == node:
                            class_name_node = n
                            break
                if class_name_node:
                    class_name = self._extract_text(class_name_node, source)
                    symbols.append(Symbol(
                        name=class_name,
                        type="class",
                        file=file_path,
                        line=class_name_node.start_point[0] + 1,
                        end_line=node.end_point[0] + 1,
                        column=class_name_node.start_point[1],
                        code=self._extract_text(node, source),
                        start_byte=node.start_byte,
                        end_byte=node.end_byte,
                    ))
            
            elif capture_name == "interface" and lang in ["typescript", "tsx"]:
                interface_name_node = None
                for cap in captures:
                    if isinstance(cap, tuple) and len(cap) == 2:
                        n, name = cap
                        if name == "interface.name" and n.parent == node:
                            interface_name_node = n
                            break
                if interface_name_node:
                    interface_name = self._extract_text(interface_name_node, source)
                    symbols.append(Symbol(
                        name=interface_name,
                        type="interface",
                        file=file_path,
                        line=interface_name_node.start_point[0] + 1,
                        end_line=node.end_point[0] + 1,
                        column=interface_name_node.start_point[1],
                        code=self._extract_text(node, source),
                        start_byte=node.start_byte,
                        end_byte=node.end_byte,
                    ))
            
            elif capture_name in ["function", "arrow_func"]:
                if capture_name == "function":
                    func_name_node = next((n for n, name in captures if name == "function.name" and n.parent == node), None)
                else:  # arrow function
                    func_name_node = next((n for n, name in captures if name == "var.name" and n.parent == node.parent), None)
                
                if func_name_node:
                    func_name = self._extract_text(func_name_node, source)
                    params_node = node.child_by_field_name("parameters")
                    signature = self._extract_text(params_node, source) if params_node else "()"
                    
                    # Get return type for TypeScript
                    return_type = ""
                    if lang in ["typescript", "tsx"]:
                        return_node = node.child_by_field_name("return_type")
                        if return_node:
                            return_type = ": " + self._extract_text(return_node, source)
                    
                    symbols.append(Symbol(
                        name=func_name,
                        type="function",
                        file=file_path,
                        line=func_name_node.start_point[0] + 1,
                        end_line=node.end_point[0] + 1,
                        column=func_name_node.start_point[1],
                        signature=f"{func_name}{signature}{return_type}",
                        code=self._extract_text(node, source),
                        start_byte=node.start_byte,
                        end_byte=node.end_byte,
                    ))
        
        return symbols
    
    async def enhance_search_results(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """Enhance ripgrep search results with symbol context"""
        if not results.get("success") or not results.get("matches"):
            return results
        
        enhanced_matches = []
        
        # Group matches by file for efficiency
        matches_by_file = {}
        for match in results["matches"]:
            file_path = match["file"]
            if file_path not in matches_by_file:
                matches_by_file[file_path] = []
            matches_by_file[file_path].append(match)
        
        # Process each file
        for file_path, file_matches in matches_by_file.items():
            # Extract symbols for this file
            symbols = await self.extract_symbols(file_path)
            
            # Create a lookup structure for efficient symbol finding
            symbol_lookup = []
            for symbol in symbols:
                symbol_lookup.append((symbol.line, symbol.end_line, symbol))
            symbol_lookup.sort(key=lambda x: x[0])
            
            # Enhance each match
            for match in file_matches:
                line_num = match["line_number"]
                
                # Find containing symbol
                containing_symbol = None
                for start_line, end_line, symbol in symbol_lookup:
                    if start_line <= line_num <= end_line:
                        containing_symbol = symbol
                        break
                
                # Add symbol context to match
                enhanced_match = match.copy()
                if containing_symbol:
                    enhanced_match["symbol_context"] = {
                        "name": containing_symbol.name,
                        "type": containing_symbol.type,
                        "parent": containing_symbol.parent,
                        "signature": containing_symbol.signature,
                    }
                
                enhanced_matches.append(enhanced_match)
        
        # Return enhanced results
        enhanced_results = results.copy()
        enhanced_results["matches"] = enhanced_matches
        enhanced_results["enhanced"] = True
        
        return enhanced_results
    
    async def get_file_symbols(self, file_path: str) -> List[Dict[str, Any]]:
        """Get all symbols from a file"""
        symbols = await self.extract_symbols(file_path)
        return [s.to_dict() for s in symbols]