# MCP Code Search Integration Plan - POC First Approach

## Overview
Build an MCP server ecosystem for intelligent code search, starting with a simple POC using `ripgrep` to validate the integration approach before implementing advanced RAG features.

## Phase 1: POC - Simple MCP Code Search Server (Week 1)

### **Objective**
Prove that MCP integration works and coding agents will use the search functionality by building a minimal server using `ripgrep`.

### **POC Architecture**
```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Coding Agent  │───▶│  MCP Client      │───▶│ MCP Search      │
│   (Claude Code, │    │  (Built into     │    │ Server (POC)    │
│    Cursor, etc) │    │   Agent)         │    │                 │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                                                         │
                                                         ▼
                                               ┌─────────────────┐
                                               │   ripgrep (rg)  │
                                               │   Command Line  │
                                               └─────────────────┘
```

### **POC Features**
1. **Basic Text Search**: Execute `rg` commands with regex patterns
2. **File Type Filtering**: Support `--type py`, `--type js`, etc.
3. **Directory Scoping**: Search specific directories or entire codebase
4. **Result Formatting**: Structure results for easy agent consumption
5. **Error Handling**: Graceful handling of invalid regex or missing files

### **MCP Tools for POC**
```json
{
  "search_code": {
    "description": "Search for code patterns using regex",
    "parameters": {
      "pattern": "string (required) - Regex pattern to search for",
      "file_type": "string (optional) - File type (py, js, ts, java, cpp, etc.)",
      "directory": "string (optional) - Directory to search (default: current)",
      "max_results": "number (optional) - Maximum results to return (default: 50)"
    }
  },
  "search_function": {
    "description": "Search for function definitions",
    "parameters": {
      "function_name": "string (required) - Function name to find",
      "file_type": "string (optional) - File type to search in"
    }
  },
  "search_class": {
    "description": "Search for class definitions", 
    "parameters": {
      "class_name": "string (required) - Class name to find",
      "file_type": "string (optional) - File type to search in"
    }
  }
}
```

### **POC Implementation**

#### **1. Basic MCP Server (Python)**
```python
# poc_search_server.py
import asyncio
import subprocess
import json
import re
from mcp.server.fastmcp import FastMCP
from typing import Optional, List, Dict

# Initialize MCP server
mcp = FastMCP("code-search-poc")

# File type mappings for ripgrep
FILE_TYPES = {
    "py": "python", "js": "javascript", "ts": "typescript",
    "java": "java", "cpp": "cpp", "c": "c", "go": "go",
    "rs": "rust", "rb": "ruby", "php": "php"
}

@mcp.tool()
async def search_code(
    pattern: str,
    file_type: Optional[str] = None,
    directory: Optional[str] = ".",
    max_results: Optional[int] = 50
) -> Dict:
    """Search for code patterns using ripgrep"""
    
    cmd = ["rg", "--json", "--max-count", str(max_results)]
    
    # Add file type filter if specified
    if file_type and file_type in FILE_TYPES:
        cmd.extend(["--type", FILE_TYPES[file_type]])
    
    # Add pattern and directory
    cmd.extend([pattern, directory])
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        
        # Parse ripgrep JSON output
        matches = []
        for line in result.stdout.strip().split('\n'):
            if line:
                match_data = json.loads(line)
                if match_data.get('type') == 'match':
                    data = match_data['data']
                    matches.append({
                        'file': data['path']['text'],
                        'line_number': data['line_number'],
                        'line_text': data['lines']['text'].strip(),
                        'submatches': data.get('submatches', [])
                    })
        
        return {
            "pattern": pattern,
            "file_type": file_type,
            "total_matches": len(matches),
            "matches": matches
        }
        
    except subprocess.CalledProcessError as e:
        return {
            "error": f"Search failed: {e.stderr}",
            "pattern": pattern,
            "matches": []
        }

@mcp.tool()
async def search_function(
    function_name: str,
    file_type: Optional[str] = None
) -> Dict:
    """Search for function definitions"""
    
    # Language-specific function patterns
    patterns = {
        "py": rf"def\s+{function_name}\s*\(",
        "js": rf"(function\s+{function_name}|{function_name}\s*[:=]\s*(async\s+)?function|\s*{function_name}\s*\()",
        "ts": rf"(function\s+{function_name}|{function_name}\s*[:=]\s*(async\s+)?function|\s*{function_name}\s*\()",
        "java": rf"(public|private|protected)?\s*(static\s+)?\w+\s+{function_name}\s*\(",
        "cpp": rf"\w+\s+{function_name}\s*\("
    }
    
    pattern = patterns.get(file_type, rf"{function_name}\s*\(")
    return await search_code(pattern, file_type, max_results=25)

@mcp.tool() 
async def search_class(
    class_name: str,
    file_type: Optional[str] = None
) -> Dict:
    """Search for class definitions"""
    
    patterns = {
        "py": rf"class\s+{class_name}(\s*\(|\s*:)",
        "js": rf"class\s+{class_name}(\s+extends|\s*\{{)",
        "ts": rf"class\s+{class_name}(\s+extends|\s+implements|\s*\{{)",
        "java": rf"(public\s+|private\s+|protected\s+)?class\s+{class_name}(\s+extends|\s+implements|\s*\{{)",
        "cpp": rf"class\s+{class_name}(\s*:\s*(public|private|protected)|\s*\{{)"
    }
    
    pattern = patterns.get(file_type, rf"class\s+{class_name}")
    return await search_code(pattern, file_type, max_results=25)

# Run the server
if __name__ == "__main__":
    mcp.run()
```

#### **2. Configuration File**
```yaml
# config/poc_search.yaml
server:
  name: "code-search-poc"
  version: "0.1.0"
  description: "POC MCP server for code search using ripgrep"

tools:
  search_code:
    description: "Search code using regex patterns"
    max_results_default: 50
    max_results_limit: 200
  
  search_function:
    description: "Find function definitions"
    enabled_languages: ["py", "js", "ts", "java", "cpp"]
  
  search_class:
    description: "Find class definitions" 
    enabled_languages: ["py", "js", "ts", "java", "cpp"]

ripgrep:
  default_args: ["--smart-case", "--follow", "--hidden"]
  exclude_patterns: [".git", "node_modules", "__pycache__", ".venv"]
```

### **POC Testing & Validation**

#### **1. Basic Functionality Test**
```bash
# Test the MCP server directly
python poc_search_server.py &
MCP_SERVER_PID=$!

# Test with MCP client
echo '{"jsonrpc": "2.0", "method": "tools/call", "params": {"name": "search_code", "arguments": {"pattern": "async def", "file_type": "py"}}, "id": 1}' | nc localhost 3000

kill $MCP_SERVER_PID
```

#### **2. Integration Test Script**
```python
# test_poc_integration.py
import asyncio
from mcp.client import StdioMCPClient

async def test_search_integration():
    """Test MCP search integration"""
    
    # Connect to MCP server
    async with StdioMCPClient("python", ["poc_search_server.py"]) as client:
        
        # Test basic search
        result = await client.call_tool("search_code", {
            "pattern": "def.*test",
            "file_type": "py",
            "max_results": 10
        })
        print(f"Search Results: {result}")
        
        # Test function search
        result = await client.call_tool("search_function", {
            "function_name": "main",
            "file_type": "py"
        })
        print(f"Function Search: {result}")

if __name__ == "__main__":
    asyncio.run(test_search_integration())
```

## Client Integration Strategies

### **1. Memory/Context Prompts for Coding Agents**

#### **System Prompt Addition**
```
You have access to a powerful code search MCP server with the following capabilities:

SEARCH TOOLS AVAILABLE:
- search_code(pattern, file_type?, directory?, max_results?) - Search using regex patterns
- search_function(function_name, file_type?) - Find function definitions
- search_class(class_name, file_type?) - Find class definitions

WHEN TO USE CODE SEARCH:
- User asks about existing code: "Where is the login function?"
- Looking for patterns: "Show me all async functions"  
- Understanding codebase: "How is error handling implemented?"
- Finding examples: "Find usage of the UserService class"
- Debugging: "Where is this variable defined?"
- Refactoring: "Find all places this function is called"

SEARCH BEST PRACTICES:
- Always specify file_type when known (py, js, ts, java, cpp)
- Use specific patterns for better results
- Start with broader searches, then narrow down
- Check multiple file types if unsure

EXAMPLE USAGE:
User: "Find all authentication functions"
You: Let me search for authentication-related functions.
[Call search_code with pattern="auth.*function|function.*auth" and file_type="py"]
```

#### **Conversation Memory**
```
CODEBASE CONTEXT:
- Last searched patterns: [store recent successful searches]
- File types in project: [detected from searches: py, js, ts, etc.]
- Common patterns found: [function naming patterns, class structures]
- Project structure: [directories that yielded results]

USE THIS CONTEXT TO:
- Suggest better search patterns
- Remember what file types are relevant
- Build on previous search results
```

### **2. Trigger Hooks & Prompts**

#### **Automatic Search Triggers**
```python
# Suggested hooks for MCP client integration
SEARCH_TRIGGERS = {
    # Question patterns that should trigger search
    "code_location": [
        r"where is (\w+)",
        r"find (the|a) (\w+)",
        r"locate (\w+)",
        r"show me (\w+)"
    ],
    
    "pattern_search": [
        r"find all (\w+)",
        r"show me all (\w+)",
        r"list all (\w+)",
        r"how many (\w+)"
    ],
    
    "implementation_search": [
        r"how is (\w+) implemented",
        r"show me the implementation of (\w+)",
        r"what does (\w+) do"
    ]
}
```

#### **Proactive Search Suggestions**
```
WHEN USER SAYS: "I need to add authentication"
AGENT RESPONSE: "Let me first search for existing authentication code to understand the current patterns."
[Automatically call search_code with pattern="auth|login|signin"]

WHEN USER SAYS: "There's a bug in the user service"  
AGENT RESPONSE: "Let me find the UserService implementation."
[Automatically call search_class with class_name="UserService"]

WHEN USER SAYS: "How do I use this API?"
AGENT RESPONSE: "Let me search for usage examples."
[Call search_code with pattern="api.*call|\.api\.|fetch.*api"]
```

### **3. Example Client Configurations**

#### **Claude Code Integration**
```json
{
  "mcpServers": {
    "code-search": {
      "command": "python",
      "args": ["poc_search_server.py"],
      "description": "Code search using ripgrep",
      "auto_discover": true
    }
  },
  "searchBehaviors": {
    "auto_search_on_code_questions": true,
    "suggest_searches": true,
    "remember_search_context": true
  }
}
```

#### **Cursor Integration**
```typescript
// cursor-mcp-integration.ts
export const codeSearchHooks = {
  onCodeQuestion: async (question: string) => {
    const searchTriggers = detectSearchTriggers(question);
    if (searchTriggers.length > 0) {
      const searches = await Promise.all(
        searchTriggers.map(trigger => 
          mcpClient.callTool('search_code', trigger.params)
        )
      );
      return { context: searches, shouldSearch: true };
    }
    return { shouldSearch: false };
  },
  
  onFileOpen: async (filePath: string) => {
    const fileType = getFileExtension(filePath);
    // Proactively search for related code
    const relatedCode = await mcpClient.callTool('search_code', {
      pattern: getFileBaseName(filePath),
      file_type: fileType
    });
    return { relatedContext: relatedCode };
  }
};
```

## Phase 2: Enhanced Search (Week 2-3)

### **Add Tree-sitter Symbol Extraction**
- Upgrade from regex to precise symbol detection
- Add symbol metadata (parameters, return types, scope)
- Implement symbol relationship mapping

### **Advanced Search Features**
- Semantic search within regex results
- Cross-reference detection (find all calls to a function)
- Dependency analysis (what imports this module)

## Phase 3: Full RAG Implementation (Week 4-6)

### **Vector Database Integration**
- Add Qdrant for semantic search
- Implement CodeBERT embeddings
- Hybrid search (structural + semantic)

### **Real-time Indexing**
- File system watching with `watchdog`
- Incremental index updates
- Background processing pipeline

## Success Metrics for POC

### **Functional Validation**
- [ ] MCP server responds to search requests
- [ ] Coding agents successfully call search tools
- [ ] Results are properly formatted and useful
- [ ] File type filtering works correctly
- [ ] Error handling gracefully manages bad input

### **Usage Validation**
- [ ] Agents use search automatically for code questions
- [ ] Search results improve agent responses
- [ ] Users find search suggestions helpful
- [ ] Search context improves follow-up conversations

### **Performance Validation**
- [ ] Search responses under 2 seconds
- [ ] Handles repositories with 10K+ files
- [ ] Memory usage remains reasonable
- [ ] Concurrent searches work properly

## Next Steps After POC

1. **Validate Integration**: Confirm agents use the search functionality
2. **Gather Feedback**: Document what works and what doesn't
3. **Identify Gaps**: Where regex search falls short
4. **Plan Enhancement**: Roadmap for Tree-sitter and RAG features
5. **Scale Testing**: Test with larger, real-world codebases

## Dependencies for POC

```bash
# Install ripgrep
# macOS: brew install ripgrep
# Ubuntu: apt install ripgrep  
# Windows: choco install ripgrep

# Python dependencies
pip install mcp fastmcp pydantic asyncio
```

This POC approach validates the core MCP integration concept quickly while providing immediate value to coding agents. Once proven, we can confidently invest in the more sophisticated Tree-sitter + RAG features knowing the integration patterns work.