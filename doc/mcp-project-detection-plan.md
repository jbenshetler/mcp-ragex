# Plan: MCP Server Project Auto-Detection and Custom Names

## Overview

Enable the MCP server to automatically detect which project it's running in based on the current working directory, and add support for custom project names with strict name management. This allows both project-scoped and global MCP registration to work seamlessly.

## Critical Requirements

1. **MCP server must NEVER write to stdout/stderr** - only JSON protocol
2. **ALL commands should auto-detect project from CWD** (not just MCP)
3. **Register command needs NO changes** - auto-detection makes it work automatically

## Current State

- MCP server uses environment variables (`PROJECT_NAME`, `RAGEX_PROJECT_DATA_DIR`) set at daemon startup
- This breaks when multiple projects exist - always uses the daemon's initial project
- No support for custom project names
- Projects use `workspace_basename` field which is redundant with custom names
- Continuous scanning already removes deleted files from the database

## Goals

1. **ALL commands** auto-detect project from CWD
2. Support custom project names with `--name` flag (strict mode - no renaming)
3. Ensure duplicate project names are handled gracefully
4. Simplify to single `project_name` field (remove `workspace_basename`)
5. Handle moved directories by detecting path mismatch and clearing index
6. **MCP server outputs ONLY JSON** - absolutely no other stdout/stderr

## Implementation Plan

### Phase 1: Simplify Project Name Handling

1. **Update project metadata structure**
   - Remove `workspace_basename` field
   - Use single `project_name` field for all purposes
   - Update `get_project_info()` to return `project_name` instead of `workspace_basename`

2. **Update all references**
   - `src/ragex_core/project_utils.py`: Remove workspace_basename
   - `docker/entrypoint.sh`: Use project_name
   - `src/daemon/handlers/ls.py`: Already uses first element of tuple
   
3. **Add name uniqueness check**
   ```python
   def is_project_name_unique(name: str, user_id: str, exclude_project_id: str = None) -> bool:
       """Check if a project name is unique for this user"""
       projects_dir = Path("/data/projects")
       user_prefix = f"ragex_{user_id}_"
       
       for project_dir in projects_dir.iterdir():
           if not project_dir.name.startswith(user_prefix):
               continue
           if exclude_project_id and project_dir.name == exclude_project_id:
               continue
               
           metadata = load_project_metadata(project_dir.name)
           if metadata and metadata.get('project_name') == name:
               return False
       
       return True
   ```

### Phase 2: Add Custom Name Support (Strict Mode)

1. **Add `--name` flag to commands**
   ```python
   # In ragex parse_args()
   index_parser.add_argument('--name', 
       help='Custom name for the project (must be unique, cannot be changed later)')
   start_parser.add_argument('--name',
       help='Custom name for the project (must be unique, cannot be changed later)')
   ```

2. **Implement strict name policy in smart_index.py**
   ```python
   # After loading existing metadata
   existing_metadata = load_project_metadata(project_id)
   if existing_metadata:
       existing_name = existing_metadata.get('project_name')
       existing_path = existing_metadata.get('workspace_path')
       
       # STRICT: No name changes allowed
       if args.name and existing_name != args.name:
           print(f"❌ Project already indexed as '{existing_name}'")
           print(f"   Use 'ragex rm {existing_name}' first to re-index with a different name")
           sys.exit(1)
       
       # Detect moved directory
       if existing_path != str(host_workspace_path):
           print(f"🔄 Detected project moved from:")
           print(f"   {existing_path}")
           print(f"   → {host_workspace_path}")
           print(f"📦 Clearing old index and re-scanning...")
           
           # Clear the entire ChromaDB for this project
           vector_store = CodeVectorStore(persist_directory=str(get_chroma_db_path(project_data_dir)))
           vector_store.clear_all()
           
           # Update metadata with new path
           metadata['workspace_path'] = str(host_workspace_path)
           update_project_metadata(project_id, metadata)
           
           # Force full reindex
           args.force = True
   ```

### Phase 3: Universal Project Auto-Detection

1. **Create project detection utility**
   
   Create `src/ragex_core/project_detection.py`:
   ```python
   def detect_project_from_cwd() -> Optional[Dict[str, str]]:
       """Detect project from current working directory
       
       Returns:
           Dict with project_id, project_name, project_data_dir
           None if no project found
       """
       # Get current working directory (in container)
       cwd = Path.cwd()
       
       # Get user ID
       user_id = os.environ.get('DOCKER_USER_ID', str(os.getuid()))
       
       # Get host workspace path (required for project ID generation)
       host_workspace_path = os.environ.get('WORKSPACE_PATH')
       if not host_workspace_path:
           logger.error("WORKSPACE_PATH not set - cannot detect project")
           return None
       
       # Find project using host path
       project_root = find_existing_project_root(Path(host_workspace_path), user_id)
       if not project_root:
           return None
       
       # Generate project ID from host path
       project_id = generate_project_id(str(project_root), user_id)
       project_data_dir = f'/data/projects/{project_id}'
       
       # Load project metadata
       metadata = load_project_metadata(project_id)
       project_name = metadata.get('project_name', 'unknown') if metadata else 'unknown'
       
       return {
           'project_id': project_id,
           'project_name': project_name,
           'project_data_dir': project_data_dir,
           'project_root': str(project_root)
       }
   ```

2. **Update search command to auto-detect**
   
   In `src/cli/search.py`:
   ```python
   def __init__(self, index_dir: Optional[str] = None, json_output: bool = False):
       self.json_output = json_output
       self.initialization_messages = []
       
       # Auto-detect project if no index_dir provided
       if not index_dir:
           from src.ragex_core.project_detection import detect_project_from_cwd
           project_info = detect_project_from_cwd()
           
           if project_info:
               index_dir = project_info['project_data_dir']
               msg = f"Detected project: {project_info['project_name']}"
               logger.info(msg)
               if not json_output:
                   print(f"# {msg}", file=sys.stderr)
           else:
               msg = "No indexed project found. Run 'ragex index' first."
               logger.error(msg)
               if not json_output:
                   print(f"# {msg}", file=sys.stderr)
               return
       
       # ... rest of initialization
   ```

### Phase 4: Ensure MCP Complete Silence

1. **Update MCP server initialization**
   
   In `src/mcp_server.py`:
   ```python
   import sys
   import logging
   import json
   
   # CRITICAL: Configure logging to ONLY go to file, NEVER to stdout/stderr
   logging.basicConfig(
       level=logging.INFO,
       format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
       handlers=[
           logging.FileHandler('/tmp/ragex-mcp.log', mode='a'),
           # NO StreamHandler - this would print to stderr
       ],
       force=True  # Override any existing configuration
   )
   
   # Suppress ALL other loggers that might print
   for logger_name in ['chromadb', 'sentence_transformers', 'transformers', 'torch']:
       logging.getLogger(logger_name).setLevel(logging.ERROR)
       logging.getLogger(logger_name).handlers = []
   
   # Create a custom print function that logs instead
   _original_print = print
   def silent_print(*args, **kwargs):
       # Convert print to logger
       message = ' '.join(str(arg) for arg in args)
       logger.debug(f"Suppressed print: {message}")
   
   # Override print globally for MCP
   __builtins__['print'] = silent_print
   
   # Capture any writes to stdout/stderr
   class SilentIO:
       def write(self, text):
           if text and text != '\n':
               logger.debug(f"Suppressed output: {text}")
       def flush(self):
           pass
   
   # Redirect stdout/stderr to prevent ANY output except our JSON
   _original_stdout = sys.stdout
   _original_stderr = sys.stderr
   sys.stderr = SilentIO()
   # Keep stdout for JSON output only
   ```

2. **Update MCP error handling**
   ```python
   async def _initialize_search_client(self) -> bool:
       """Initialize the search client with auto-detected project"""
       if self.search_client is not None:
           return True
       
       try:
           from src.ragex_core.project_detection import detect_project_from_cwd
           project_info = detect_project_from_cwd()
           
           if not project_info:
               # ONLY log, never print
               logger.error("No indexed project found in current directory")
               return False
           
           logger.info(f"Auto-detected project '{project_info['project_name']}'")
           
           # Create search client with detected project
           # CRITICAL: Force json_output=True to prevent any prints
           self.search_client = SearchClient(project_info['project_data_dir'], json_output=True)
           
           # Ensure search client also doesn't print
           if hasattr(self.search_client, 'pattern_matcher'):
               # Disable any warnings from pattern matcher
               self.search_client.pattern_matcher.check_ignore_file = lambda x: True
           
           return True
           
       except Exception as e:
           logger.error(f"Failed to initialize search client: {e}", exc_info=True)
           return False
   ```

3. **Update entrypoint.sh for MCP mode**
   ```bash
   # In entrypoint.sh
   "mcp")
       # MCP mode - absolute silence required
       # DO NOT setup project data - that would print
       # DO NOT check workspace - that would print
       
       # Just run the MCP server
       exec python -m src.mcp_server "$@" 2>/tmp/ragex-mcp-startup.log
       ;;
   ```

4. **Test MCP complete silence**
   ```bash
   # Test 1: Empty input
   echo '{}' | ragex --mcp 2>stderr.txt | jq .
   [ ! -s stderr.txt ] || (echo "FAIL: stderr not empty" && cat stderr.txt)
   
   # Test 2: With project
   cd /path/to/indexed/project
   echo '{}' | ragex --mcp 2>stderr.txt | jq .
   [ ! -s stderr.txt ] || (echo "FAIL: stderr not empty" && cat stderr.txt)
   
   # Test 3: Without project
   cd /tmp
   echo '{}' | ragex --mcp 2>stderr.txt | jq .
   [ ! -s stderr.txt ] || (echo "FAIL: stderr not empty" && cat stderr.txt)
   ```

### Phase 5: Register Command Works As-Is

With auto-detection, the register command needs NO changes:

1. User runs `ragex register claude` in project directory
2. Register command detects current project automatically
3. Creates `.mcp.json` with simple args: `["--mcp"]`
4. When Claude runs MCP server, it auto-detects project from CWD

No code changes needed for register command!

## Testing Plan

1. **MCP Absolute Silence**
   ```bash
   # Must produce ONLY valid JSON, no other output
   cd /home/user/project
   echo '{"jsonrpc":"2.0","method":"initialize","id":1,"params":{}}' | \
     ragex --mcp 2>err.log >out.json
   
   # Verify
   [ ! -s err.log ] && echo "✓ stderr empty" || echo "✗ stderr has content"
   jq . out.json && echo "✓ valid JSON" || echo "✗ invalid JSON"
   ```

2. **Auto-detection for All Commands**
   ```bash
   # From project subdirectory
   cd /home/user/project/src/lib
   ragex search "test"  # Should work
   ragex info          # Should show project info
   ragex --mcp         # Should work silently
   ```

3. **Register Command**
   ```bash
   cd /home/user/project
   ragex register claude
   # Should create .mcp.json with just ["--mcp"]
   # Claude can then use it from any project subdirectory
   ```

## Success Criteria

1. ✅ MCP outputs ONLY JSON - zero other stdout/stderr
2. ✅ All commands auto-detect project from CWD
3. ✅ Register command works without modification
4. ✅ Single project_name field used everywhere
5. ✅ Custom names enforced as unique
6. ✅ No name changes allowed (strict mode)
7. ✅ Moved directories detected and handled
8. ✅ No regression in existing functionality