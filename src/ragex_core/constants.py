"""
Core constants for the ragex system
"""

# Admin/system project constants
ADMIN_PROJECT_NAME = ".ragex_admin"
ADMIN_WORKSPACE_PATH = f"/{ADMIN_PROJECT_NAME}"

# This is used for projects that don't have a real workspace
# (e.g., when running admin commands without a mounted workspace)
# The dot prefix and "_admin" suffix make it unlikely to conflict with user projects