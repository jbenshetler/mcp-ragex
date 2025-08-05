#!/usr/bin/env python3
"""Test Tree-sitter query to find correct field names"""

import tree_sitter
import tree_sitter_python as tspython

# Create parser
parser = tree_sitter.Parser()
lang = tree_sitter.Language(tspython.language())
parser.language = lang

# Test code with module-level constant
code = b'''
API_KEY = os.environ.get("API_KEY", "default_key")
BASE_URL = "https://api.example.com"
'''
tree = parser.parse(code)

# Print the tree structure
def print_tree(node, indent=0, source=None):
    text = ""
    if source and node.start_byte < len(source):
        text = source[node.start_byte:node.end_byte].decode('utf-8', errors='ignore')
        if len(text) > 40:
            text = text[:40] + "..."
        text = f" -> '{text}'"
    
    print(" " * indent + f"{node.type}{text}")
    
    for i, child in enumerate(node.children):
        print_tree(child, indent + 2, source)

print("Tree structure for module-level constants:")
print("-" * 60)
print_tree(tree.root_node, source=code)