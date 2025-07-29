# Improve Project Listing Plan

## Current Problem

The `ragex list-projects` command shows unhelpful output:
```
📋 Available projects:
  • ragex_1000_8375a7fda539e891 (unknown) [unknown]
```

Issues:
1. Project names are cryptic hashes (e.g., `ragex_1000_8375a7fda539e891`)
2. Workspace paths show as "unknown" even though they're stored
3. No way to identify which project corresponds to which directory
4. No additional useful information (last used, size, etc.)

## Root Cause Analysis

1. **WORKSPACE_PATH not set**: The environment variable `WORKSPACE_PATH` is not available inside the container when running `list-projects`
2. **Project ID is a hash**: The project name is generated from a hash of the workspace path, making it unreadable
3. **Container context**: When listing projects, we're not in the original workspace context

## Proposed Solution

### 1. Enhanced Project Metadata Storage

Update `project_info.json` to store more useful information:
```json
{
    "project_id": "ragex_1000_8375a7fda539e891",
    "project_name": "mcp-ragex",  // Human-readable name from directory
    "workspace_path": "/home/jeff/clients/mcp-ragex",  // Full host path
    "workspace_basename": "mcp-ragex",  // Directory name only
    "created_at": "2024-01-15T10:30:00Z",
    "last_accessed": "2024-01-15T14:22:00Z",
    "last_indexed": "2024-01-15T10:35:00Z",
    "embedding_model": "fast",
    "collection_name": "code_embeddings",
    "index_stats": {
        "total_symbols": 2332,
        "unique_files": 125,
        "languages": ["python", "javascript", "bash"]
    }
}
```

### 2. Update Project Creation Logic

In `docker/entrypoint.sh`, enhance the `setup_project_data` function:
- Store the full host workspace path (passed from ragex wrapper)
- Extract and store the workspace basename for display
- Track creation and last access times
- Update last_accessed on each use

### 3. Improve Project Listing Display

Enhanced output format:
```
📋 Available projects:

  mcp-ragex [ragex_1000_8375a7fda539e891]
  📁 /home/jeff/clients/mcp-ragex
  📊 2,332 symbols | 125 files | Python, JavaScript, Bash
  🕐 Last used: 2 hours ago | Created: 3 days ago
  ⚙️  Model: fast

  nancyknows-main [ragex_1000_266b9bcd293ce8af]
  📁 /home/jeff/clients/nancyknows/nancyknows-main
  📊 5,120 symbols | 312 files | Python, TypeScript
  🕐 Last used: 1 day ago | Created: 1 week ago
  ⚙️  Model: balanced

  [3 more projects...]
```

### 4. Add Project Management Commands

New commands to improve usability:
- `ragex list-projects --verbose` - Show full details
- `ragex list-projects --json` - Machine-readable output
- `ragex clean-old-projects --days 30` - Clean projects not used in 30 days
- `ragex rename-project <old_id> <new_name>` - Give projects friendly names

### 5. Implementation Steps

#### Phase 1: Fix Immediate Issues (Quick Fix)
1. Pass `WORKSPACE_PATH` environment variable to the container in list-projects
2. Update entrypoint.sh to properly read and display workspace paths
3. Show both project ID and workspace basename

#### Phase 2: Enhanced Metadata (Medium Term)
1. Update project_info.json structure
2. Add last_accessed tracking
3. Store index statistics when indexing completes
4. Implement human-readable project names

#### Phase 3: Advanced Features (Long Term)
1. Add project management commands
2. Implement project cleanup based on age
3. Add ability to rename/alias projects
4. Show disk usage per project

## Technical Changes Required

### 1. ragex wrapper script
```bash
# Pass workspace info even for list-projects
case "$COMMAND" in
    "list-projects"|"clean-project")
        DOCKER_ARGS=(
            "run"
            "--rm"
            "-u" "${DOCKER_USER_ID}:${DOCKER_GROUP_ID}"
            "-v" "${USER_VOLUME}:/data"
            "-e" "PROJECT_NAME=admin"
            "-e" "HOST_HOME=${HOME}"  # Add this
            "-e" "HOST_USER=${USER}"   # Add this
        )
        ;;
esac
```

### 2. docker/entrypoint.sh
- Update `setup_project_data` to store enhanced metadata
- Update `list-projects` to read and display the enhanced data
- Add function to update last_accessed timestamp

### 3. scripts/build_semantic_index.py
- After indexing, update project_info.json with index stats
- Store last_indexed timestamp

## Success Metrics

1. Users can immediately identify which project is which from the listing
2. No more "unknown" values in the output
3. Useful information about each project (size, last used, etc.)
4. Ability to clean up old projects easily

## Migration Strategy

For existing projects without the new metadata:
1. Check if project_info.json exists
2. If old format, try to reconstruct data from available info
3. Mark reconstructed data with a flag
4. Update metadata on next access

## Alternative Approaches Considered

1. **Store projects by path hash + name**: Rejected because it would break existing projects
2. **Use symbolic links**: Rejected due to Docker volume complexity
3. **Single shared index**: Rejected because it would mix different projects' data

## Conclusion

The improved project listing will make ragex much more user-friendly by:
- Showing human-readable project information
- Displaying the full host paths
- Providing useful statistics about each project
- Making it easy to manage multiple projects

The phased approach allows us to fix the immediate "unknown" issue quickly while planning for more comprehensive improvements.