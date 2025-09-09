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

import sys
import tree_sitter
from tree_sitter import Language, Parser, Query, QueryCursor
import tree_sitter_python as tspython
import tree_sitter_javascript as tsjavascript
import tree_sitter_typescript as tstypescript

try:
    from .ragex_core.path_mapping import container_to_host_path, is_container_path
except ImportError:
    from src.ragex_core.path_mapping import container_to_host_path, is_container_path

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
        try:
            # Try relative import first (when running as module)
            from .ragex_core.pattern_matcher import PatternMatcher
        except ImportError:
            # Fall back to absolute import
            from src.ragex_core.pattern_matcher import PatternMatcher
        
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
            "python": Query(self.languages["python"], """
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
                
                ; All module-level assignments for now (fallback)
                ((expression_statement
                    (assignment
                        left: (identifier) @assignment.name
                        right: (_) @assignment.value)) @assignment)
                
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
                
                (call
                    function: (attribute
                        object: (identifier) @getenv.module
                        attribute: (identifier) @getenv.method)
                    arguments: (argument_list
                        (string) @getenv.var_name)
                    (#eq? @getenv.module "os")
                    (#eq? @getenv.method "getenv")) @getenv_access
                
                ; Subscript access to os.environ
                (subscript
                    (attribute
                        object: (identifier) @env_sub.module
                        attribute: (identifier) @env_sub.attr)
                    (string) @env_sub.var_name
                    (#eq? @env_sub.module "os")
                    (#eq? @env_sub.attr "environ")) @env_subscript
                
                ; Comments for semantic search only
                (comment) @comment
                
                ; Module docstrings (first expression in module if it's a string)
                (module
                    . (expression_statement
                        (string) @module_doc.content)) @module_doc
            """),
            
            "javascript": Query(self.languages["javascript"], """
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
                
                (variable_declarator
                    name: (identifier) @var.name
                    value: (function_expression
                        name: (identifier)? @func_expr.name
                        parameters: (formal_parameters) @func_expr.params)) @func_expr
                
                (method_definition
                    name: (property_identifier) @method.name
                    parameters: (formal_parameters) @method.params) @method
                
                ; Modern JS patterns
                (lexical_declaration
                    (variable_declarator
                        name: (identifier) @const.name
                        value: (arrow_function
                            parameters: (formal_parameters) @const.params))) @const_arrow
                
                (lexical_declaration
                    (variable_declarator
                        name: (identifier) @const.name
                        value: (function_expression
                            parameters: (formal_parameters) @const.params))) @const_func
                
                ; Export patterns
                (export_statement
                    declaration: (lexical_declaration
                        (variable_declarator
                            name: (identifier) @export.name
                            value: (arrow_function
                                parameters: (formal_parameters) @export.params)))) @export_arrow
                
                (export_statement
                    declaration: (function_declaration
                        name: (identifier) @export_func.name
                        parameters: (formal_parameters) @export_func.params)) @export_func
                
                ; Import statements
                (import_statement
                    source: (string) @import.source) @import
                
                (import_statement
                    (import_clause
                        (named_imports
                            (import_specifier
                                name: (identifier) @import.name)))) @named_import
            """),
            
            "typescript": Query(self.languages["typescript"], """
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
    
    async def extract_symbols(self, file_path: str, include_docs_and_comments: bool = False) -> List[Symbol]:
        """Extract symbols from a single file
        
        Args:
            file_path: Path to the file to analyze
            include_docs_and_comments: If True, includes comments and standalone docstrings
                                     (for semantic search). If False, only code symbols
                                     (for symbol search).
        """
        # Convert container path to host path for consistent storage
        host_path = file_path
        if is_container_path(file_path):
            host_path = container_to_host_path(file_path)
        
        # Check if file should be excluded
        if self.pattern_matcher.should_exclude(file_path):
            return []
        
        lang = self._get_language(file_path)
        if not lang:
            return []
        
        # Check cache first (separate caches for with/without docs)
        cache_key = f"{file_path}:{include_docs_and_comments}"
        if cache_key in self._symbol_cache:
            return self._symbol_cache[cache_key]
        
        content = self._read_file_cached(file_path)
        if not content:
            return []
        
        parser = self.parsers[lang]
        tree = parser.parse(content)
        
        symbols = []
        query = self.queries[lang]
        
        # Use modern tree-sitter API with QueryCursor
        # Create a cursor for the query
        cursor = QueryCursor(query)
        # Get captures using the cursor
        captures_dict = cursor.captures(tree.root_node)
        
        # Convert to list format for compatibility with existing code
        captures = []
        for capture_name, nodes in captures_dict.items():
            for node in nodes:
                captures.append((node, capture_name))
                
        logger.debug(f"Using tree-sitter with QueryCursor API, found {len(captures)} captures")
        
        # Debug: Check what captures returns
        logger.debug(f"Captures type: {type(captures)}, length: {len(captures) if hasattr(captures, '__len__') else 'N/A'}")
        
        # Process captures based on language
        if lang == "python":
            symbols.extend(self._extract_python_symbols(captures, content, host_path, include_docs_and_comments))
        elif lang in ["javascript", "typescript", "tsx"]:
            symbols.extend(self._extract_js_ts_symbols(captures, content, host_path, lang))
        
        # Update cache (with size limit)
        if len(self._symbol_cache) >= self._cache_size:
            # Remove oldest entry
            oldest = next(iter(self._symbol_cache))
            del self._symbol_cache[oldest]
        self._symbol_cache[cache_key] = symbols
        
        return symbols
    
    def _extract_python_symbols(self, captures, source: bytes, host_path: str, include_docs_and_comments: bool = False) -> List[Symbol]:
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
            # TODO: Temporarily skip class indexing to prevent massive code blocks
            # This avoids indexing entire class definitions (can be 1000+ lines)
            # Individual methods within classes are still indexed separately
            # TODO: Future - implement class header-only indexing
            if capture_name == "class":
                logger.debug(f"Skipping class symbol indexing for token optimization")
                continue
            
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
                        file=host_path,
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
            
            # Handle import statements
            elif capture_name == "import":
                import_name_node = find_capture_node("import.name", node)
                if import_name_node:
                    import_name = self._extract_text(import_name_node, source)
                    symbols.append(Symbol(
                        name=import_name,
                        type="import",
                        file=host_path,
                        line=node.start_point[0] + 1,
                        end_line=node.end_point[0] + 1,
                        column=node.start_point[1],
                        code=self._extract_text(node, source),
                        start_byte=node.start_byte,
                        end_byte=node.end_byte,
                    ))
            
            elif capture_name == "import_from":
                module_node = find_capture_node("import.module", node)
                name_nodes = [n for n, name in captures if name == "import.name" and n.parent == node]
                alias_nodes = [n for n, name in captures if name == "import.alias" and n.parent == node]
                
                module_name = self._extract_text(module_node, source) if module_node else ""
                
                # Handle "from X import Y, Z" or "from X import Y as A"
                for i, name_node in enumerate(name_nodes):
                    imported_name = self._extract_text(name_node, source)
                    alias = None
                    if i < len(alias_nodes):
                        alias = self._extract_text(alias_nodes[i], source)
                    
                    full_name = f"{module_name}.{imported_name}" if module_name else imported_name
                    display_name = alias if alias else imported_name
                    
                    symbols.append(Symbol(
                        name=display_name,
                        type="import_from",
                        file=host_path,
                        line=node.start_point[0] + 1,
                        end_line=node.end_point[0] + 1,
                        column=node.start_point[1],
                        signature=f"from {module_name} import {imported_name}" + (f" as {alias}" if alias else ""),
                        code=self._extract_text(node, source),
                        start_byte=node.start_byte,
                        end_byte=node.end_byte,
                    ))
            
            # Handle module-level constants and assignments
            elif capture_name in ["constant", "assignment"]:
                name_key = f"{capture_name}.name"
                value_key = f"{capture_name}.value"
                
                const_name_node = find_capture_node(name_key, node)
                const_value_node = find_capture_node(value_key, node)
                
                if const_name_node and const_value_node:
                    const_name = self._extract_text(const_name_node, source)
                    const_value = self._extract_text(const_value_node, source)
                    
                    # Determine if this is inside a function/class (not module-level)
                    is_module_level = True
                    parent = node.parent
                    while parent:
                        if parent.type in ["function_definition", "class_definition"]:
                            is_module_level = False
                            break
                        parent = parent.parent
                    
                    # Only capture module-level assignments
                    if is_module_level:
                        # Determine type based on name pattern
                        if const_name.isupper() or "config" in const_name.lower() or "setting" in const_name.lower():
                            symbol_type = "constant"
                        else:
                            # Skip regular variable assignments for now
                            continue
                        
                        symbols.append(Symbol(
                            name=const_name,
                            type=symbol_type,
                            file=host_path,
                            line=const_name_node.start_point[0] + 1,
                            end_line=node.end_point[0] + 1,
                            column=const_name_node.start_point[1],
                            signature=f"{const_name} = {const_value[:50]}..." if len(const_value) > 50 else f"{const_name} = {const_value}",
                            code=self._extract_text(node, source),
                            start_byte=node.start_byte,
                            end_byte=node.end_byte,
                        ))
            
            # Handle environment variable access
            elif capture_name in ["env_access", "getenv_access", "env_subscript"]:
                # Find the specific var_name node for this capture
                var_name_node = None
                for n, name in captures:
                    if name.endswith(".var_name") and node.start_byte <= n.start_byte <= node.end_byte:
                        # Get the first string argument (the env var name)
                        if n.parent.type == "argument_list":
                            # For os.environ.get() or os.getenv(), get first argument only
                            var_name_node = n
                            break
                        elif n.parent.type == "subscript":
                            # For os.environ[], get the subscript string
                            var_name_node = n
                            break
                
                if var_name_node:
                    env_var_name = self._extract_text(var_name_node, source).strip('"\'')
                    
                    # Determine the access pattern
                    if capture_name == "env_access":
                        access_pattern = "os.environ.get()"
                    elif capture_name == "getenv_access":
                        access_pattern = "os.getenv()"
                    else:
                        access_pattern = "os.environ[]"
                    
                    symbols.append(Symbol(
                        name=env_var_name,
                        type="env_var",
                        file=host_path,
                        line=node.start_point[0] + 1,
                        end_line=node.end_point[0] + 1,
                        column=node.start_point[1],
                        signature=f"{access_pattern} -> {env_var_name}",
                        code=self._extract_text(node, source),
                        start_byte=node.start_byte,
                        end_byte=node.end_byte,
                    ))
            
            # Handle comments and module docstrings (only for semantic search)
            elif include_docs_and_comments and capture_name == "comment":
                comment_text = self._extract_text(node, source).strip()
                # Extract TODO/FIXME/NOTE patterns
                special_comment = None
                for pattern in ['TODO', 'FIXME', 'NOTE', 'HACK', 'XXX']:
                    if pattern in comment_text.upper():
                        special_comment = pattern
                        break
                
                symbols.append(Symbol(
                    name=f"Comment: {comment_text[:50]}..." if len(comment_text) > 50 else f"Comment: {comment_text}",
                    type="comment",
                    file=host_path,
                    line=node.start_point[0] + 1,
                    end_line=node.end_point[0] + 1,
                    column=node.start_point[1],
                    code=comment_text,
                    signature=special_comment if special_comment else "comment",
                    start_byte=node.start_byte,
                    end_byte=node.end_byte,
                ))
            
            elif include_docs_and_comments and capture_name == "module_doc":
                doc_node = find_capture_node("module_doc.content", node)
                if doc_node:
                    module_doc = self._extract_text(doc_node, source).strip('"""\'')
                    symbols.append(Symbol(
                        name="Module Documentation",
                        type="module_doc",
                        file=host_path,
                        line=doc_node.start_point[0] + 1,
                        end_line=doc_node.end_point[0] + 1,
                        column=doc_node.start_point[1],
                        docstring=module_doc,
                        code=module_doc[:200] + "..." if len(module_doc) > 200 else module_doc,
                        start_byte=doc_node.start_byte,
                        end_byte=doc_node.end_byte,
                    ))
        
        return symbols
    
    def _extract_js_ts_symbols(self, captures, source: bytes, host_path: str, lang: str) -> List[Symbol]:
        """Extract symbols from JavaScript/TypeScript code"""
        symbols = []
        
        for capture in captures:
            # Handle different capture formats
            if isinstance(capture, tuple) and len(capture) == 2:
                node, capture_name = capture
            else:
                logger.error(f"Unexpected capture format in JS/TS: {type(capture)}, value: {capture}")
                continue
            # TODO: Temporarily skip class indexing to prevent massive code blocks
            # This avoids indexing entire class definitions (can be 1000+ lines)
            # Individual methods within classes are still indexed separately
            # TODO: Future - implement class header-only indexing
            if capture_name == "class":
                logger.debug(f"Skipping class symbol indexing for token optimization")
                continue
                
                # TODO: Future class header indexing implementation reference:
                # class_name_node = None
                # for cap in captures:
                #     if isinstance(cap, tuple) and len(cap) == 2:
                #         n, name = cap
                #         if name == "class.name" and n.parent == node:
                #             class_name_node = n
                #             break
                # if class_name_node:
                #     class_name = self._extract_text(class_name_node, source)
                #     symbols.append(Symbol(
                #         name=class_name,
                #         type="class",
                #         file=host_path,
                #         line=class_name_node.start_point[0] + 1,
                #         end_line=node.end_point[0] + 1,  # TODO: Should be header end, not full class end
                #         column=class_name_node.start_point[1],
                #         code=self._extract_text(node, source),  # TODO: Should be header only, not full class
                #         start_byte=node.start_byte,
                #         end_byte=node.end_byte,  # TODO: Should be header end, not full class end
                #     ))
            
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
                        file=host_path,
                        line=interface_name_node.start_point[0] + 1,
                        end_line=node.end_point[0] + 1,
                        column=interface_name_node.start_point[1],
                        code=self._extract_text(node, source),
                        start_byte=node.start_byte,
                        end_byte=node.end_byte,
                    ))
            
            elif capture_name in ["function", "arrow_func", "func_expr", "const_arrow", "const_func", "export_arrow", "export_func"]:
                # Determine the function name node based on capture type
                func_name_node = None
                func_node = node
                
                if capture_name == "function":
                    func_name_node = next((n for n, name in captures if name == "function.name" and n.parent == node), None)
                elif capture_name == "arrow_func":
                    func_name_node = next((n for n, name in captures if name == "var.name" and n.parent == node.parent), None)
                elif capture_name == "func_expr":
                    func_name_node = next((n for n, name in captures if name == "var.name" and n.parent == node.parent), None)
                    # The actual function node is the value
                    func_node = next((n for n, name in captures if name == "func_expr" and n.parent == node.parent), node)
                elif capture_name in ["const_arrow", "const_func"]:
                    func_name_node = next((n for n, name in captures if name == "const.name" and n.parent.parent == node), None)
                    # Find the actual function node
                    for n, name in captures:
                        if name == "const.params" and n.parent.parent.parent == node:
                            func_node = n.parent
                            break
                elif capture_name in ["export_arrow", "export_func"]:
                    if capture_name == "export_arrow":
                        func_name_node = next((n for n, name in captures if name == "export.name"), None)
                    else:
                        func_name_node = next((n for n, name in captures if name == "export_func.name"), None)
                
                if func_name_node:
                    func_name = self._extract_text(func_name_node, source)
                    
                    # Find parameters node
                    params_node = None
                    if capture_name in ["const_arrow", "const_func", "export_arrow"]:
                        # Look for the associated params capture
                        param_capture_name = {
                            "const_arrow": "const.params",
                            "const_func": "const.params",
                            "export_arrow": "export.params"
                        }.get(capture_name)
                        if param_capture_name:
                            params_node = next((n for n, name in captures if name == param_capture_name), None)
                    else:
                        params_node = func_node.child_by_field_name("parameters")
                    
                    signature = self._extract_text(params_node, source) if params_node else "()"
                    
                    # Get return type for TypeScript
                    return_type = ""
                    if lang in ["typescript", "tsx"]:
                        return_node = func_node.child_by_field_name("return_type")
                        if return_node:
                            return_type = ": " + self._extract_text(return_node, source)
                    
                    symbols.append(Symbol(
                        name=func_name,
                        type="function",
                        file=host_path,
                        line=func_name_node.start_point[0] + 1,
                        end_line=node.end_point[0] + 1,
                        column=func_name_node.start_point[1],
                        signature=f"{func_name}{signature}{return_type}",
                        code=self._extract_text(node, source),
                        start_byte=node.start_byte,
                        end_byte=node.end_byte,
                    ))
            
            elif capture_name in ["import", "named_import"]:
                if capture_name == "import":
                    # Import the whole module/file
                    source_node = next((n for n, name in captures if name == "import.source" and n.parent == node), None)
                    if source_node:
                        import_source = self._extract_text(source_node, source).strip('"\'')
                        symbols.append(Symbol(
                            name=f"import {import_source}",
                            type="import",
                            file=host_path,
                            line=node.start_point[0] + 1,
                            end_line=node.end_point[0] + 1,
                            column=node.start_point[1],
                            code=self._extract_text(node, source),
                            start_byte=node.start_byte,
                            end_byte=node.end_byte,
                        ))
                else:
                    # Named imports
                    import_names = [self._extract_text(n, source) for n, name in captures if name == "import.name"]
                    for import_name in import_names:
                        symbols.append(Symbol(
                            name=import_name,
                            type="import",
                            file=host_path,
                            line=node.start_point[0] + 1,
                            end_line=node.end_point[0] + 1,
                            column=node.start_point[1],
                            signature=f"imported from module",
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