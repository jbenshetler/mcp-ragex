# Project Name Display Fix Plan

## Problem Analysis

### Current Issue
`ragex ls` displays project IDs instead of human-readable project names:
```
PROJECT NAME                 PROJECT ID                      PATH
-----------------------------------------------------------------
ragex_1000_f8902326ad894225  ragex_1000_f8902326ad894225     /home/jeff/clients/mcp-ragex
```

**Expected behavior:**
```
PROJECT NAME                 PROJECT ID                      PATH
-----------------------------------------------------------------
mcp-ragex                    ragex_1000_f8902326ad894225     /home/jeff/clients/mcp-ragex
```

### Root Cause Analysis

**Two different project name sources:**

1. **CLI Logic** (`ragex` Python script):
   - `project_name = workspace_path.name` (e.g., "mcp-ragex")
   - Used by `ragex info` command ✅ **Works correctly**

2. **Container Metadata** (`project_info.json`):
   - `project_name = PROJECT_NAME` environment variable
   - Created by `docker/entrypoint.sh` setup_project_data()
   - Currently shows project ID instead of proper name ❌ **Broken**

### Specific Issues

1. **Metadata Creation Mismatch:**
   - `smart_index.py` creates metadata with proper project name
   - `entrypoint.sh` overwrites it with project ID as name
   - `ragex ls` reads from metadata, gets wrong name

2. **Environment Variable Confusion:**
   - `entrypoint.sh` sets `PROJECT_NAME=${PROJECT_ID}` 
   - Should be `PROJECT_NAME=${workspace_basename}`

3. **Name Uniqueness Not Enforced:**
   - Multiple projects with same basename (e.g., "api") should get unique names
   - Current system doesn't handle this properly

## Fix Plan

### Phase 1: Fix Entrypoint Project Name Logic

**File:** `docker/entrypoint.sh`

**Current problematic code:**
```bash
PROJECT_HASH=$(echo "$WORKSPACE_PATH" | sha256sum | cut -d' ' -f1 | head -c 16)
PROJECT_NAME="${PROJECT_NAME:-project_${PROJECT_HASH}}"
```

**Fix:**
```bash
# Extract basename for human-readable name
WORKSPACE_BASENAME=$(basename "$WORKSPACE_PATH")

# Check if custom name provided via environment
if [ -n "$RAGEX_PROJECT_NAME" ]; then
    PROJECT_NAME="$RAGEX_PROJECT_NAME"
else
    # Use workspace basename as default
    PROJECT_NAME="$WORKSPACE_BASENAME"
fi

# Generate project ID separately (unchanged)
PROJECT_ID="ragex_${USER_ID}_$(echo "$WORKSPACE_PATH" | sha256sum | cut -d' ' -f1 | head -c 16)"
```

### Phase 2: Fix Metadata Structure

**File:** `docker/entrypoint.sh`

**Current metadata:**
```json
{
    "project_name": "${PROJECT_NAME}",  # Currently project ID
    "workspace_path": "${WORKSPACE_PATH}",
    "workspace_basename": "$(basename "${WORKSPACE_PATH}")"
}
```

**Fixed metadata:**
```json
{
    "project_name": "${PROJECT_NAME}",           # Human-readable name
    "project_id": "${PROJECT_ID}",               # Unique identifier  
    "workspace_path": "${WORKSPACE_PATH}",
    "workspace_basename": "${WORKSPACE_BASENAME}",
    "user_id": "${USER_ID}"
}
```

### Phase 3: Handle Name Uniqueness

**Approach:** Add uniqueness suffix when needed

**Implementation:**
1. Before creating metadata, check if project name already exists
2. If exists, append suffix: `api_001`, `api_002`, etc.
3. Store both original basename and unique name

**New function in entrypoint.sh:**
```bash
ensure_unique_project_name() {
    local base_name="$1"
    local user_id="$2"
    local candidate="$base_name"
    local counter=1
    
    # Check existing projects for this user
    while project_name_exists "$candidate" "$user_id"; do
        candidate="${base_name}_$(printf "%03d" $counter)"
        counter=$((counter + 1))
    done
    
    echo "$candidate"
}
```

### Phase 4: Fix CLI Integration

**File:** `ragex` (Python CLI)

**Add name parameter support:**
```python
# In cmd_index and cmd_start methods
if args.name:
    docker_cmd.extend(['-e', f'RAGEX_PROJECT_NAME={args.name}'])
```

**Validate name uniqueness:**
```python
def validate_project_name(self, name: str) -> bool:
    """Check if project name is unique for current user"""
    # Query existing projects via docker volume ls or API
    pass
```

### Phase 5: Update Project Detection Logic

**File:** `src/ragex_core/project_utils.py`

**Current:** `get_project_info()` returns `(project_name, workspace_path)`
**Fix:** Ensure it reads from metadata correctly

**Priority order for project name:**
1. `project_name` field in metadata
2. Fallback to `workspace_basename` 
3. Fallback to project ID (current behavior)

### Phase 6: Migration Strategy

**For existing projects with wrong names:**

1. **Detect corrupted metadata:**
   ```python
   def needs_name_migration(metadata):
       return metadata.get('project_name', '').startswith('ragex_')
   ```

2. **Auto-migrate on first access:**
   ```python
   if needs_name_migration(metadata):
       metadata['project_name'] = metadata['workspace_basename']
       save_metadata(metadata)
   ```

3. **Preserve user-provided names:**
   - Check if name was explicitly provided
   - Don't overwrite custom names with basename

## Implementation Order

### Phase 1: Quick Fix (Immediate)
1. Fix `entrypoint.sh` project name calculation
2. Test with new project creation

### Phase 2: Robust Solution (Follow-up)
1. Add name uniqueness checking
2. Add CLI `--name` parameter support
3. Implement migration for existing projects

### Phase 3: Polish (Future)
1. Add `ragex rename` command
2. Better error messages for name conflicts
3. Comprehensive testing suite

## Expected Results

### Before Fix:
```bash
$ ragex ls
PROJECT NAME                 PROJECT ID                      PATH
-----------------------------------------------------------------
ragex_1000_f8902326ad894225  ragex_1000_f8902326ad894225     /home/jeff/clients/mcp-ragex
```

### After Fix:
```bash
$ ragex ls
PROJECT NAME    PROJECT ID                      PATH
----------------------------------------------------------------
mcp-ragex       ragex_1000_f8902326ad894225     /home/jeff/clients/mcp-ragex
api-server      ragex_1000_a1b2c3d4e5f6g7h8     /home/jeff/projects/api-server
api-client      ragex_1000_h8g7f6e5d4c3b2a1     /home/jeff/other/api-server
```

### With Custom Names:
```bash
$ ragex index . --name "my-awesome-project"
$ ragex ls
PROJECT NAME        PROJECT ID                      PATH
--------------------------------------------------------------------
my-awesome-project  ragex_1000_f8902326ad894225     /home/jeff/clients/mcp-ragex
```

## Risk Assessment

### Low Risk Changes:
- Fix entrypoint.sh project name calculation
- Update metadata structure (backward compatible)

### Medium Risk Changes:
- Add name uniqueness checking (could affect existing workflows)
- CLI parameter changes (need to maintain backward compatibility)

### High Risk Changes:
- Automatic migration of existing projects (could break user expectations)

## Testing Strategy

### Test Cases:
1. **New project with basename:** `ragex index /path/to/myproject` → name should be "myproject"
2. **New project with custom name:** `ragex index /path/to/myproject --name "custom"` → name should be "custom"
3. **Name conflict handling:** Two projects with same basename should get unique names
4. **Existing project migration:** Projects with ID-as-name should migrate to basename
5. **Special characters in paths:** Handle spaces, unicode, etc. in project names

### Validation:
1. `ragex ls` shows correct names
2. `ragex info` consistency with `ragex ls`
3. `ragex rm` works with both name and ID
4. MCP integration unaffected
5. Project isolation maintained

## Success Criteria

✅ **Primary Goal:** `ragex ls` shows human-readable project names instead of IDs

✅ **Secondary Goals:**
- Project names are unique per user
- Custom names supported via `--name` parameter  
- Existing projects work without manual intervention
- All commands remain backward compatible

✅ **Quality Goals:**
- Clear error messages for name conflicts
- Consistent naming across all commands
- Proper handling of edge cases (special chars, long names, etc.)