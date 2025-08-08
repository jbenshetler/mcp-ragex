# ARM64 ML Image for MCP-Ragex
# This provides ML dependencies on top of ARM64 base image

ARG BASE_IMAGE=scratch
FROM ${BASE_IMAGE}

# Copy requirements files
COPY --chown=ragex:ragex requirements/ ./requirements/

# Install ARM64 PyTorch and dependencies
RUN pip install --no-cache-dir --no-warn-script-location -r requirements/cpu-arm64.txt

# Install core ML dependencies
RUN pip install --no-cache-dir --no-warn-script-location -r requirements/base-ml.txt

# Pre-download tree-sitter language parsers
RUN python -c "import tree_sitter; import tree_sitter_python as tspython; import tree_sitter_javascript as tsjavascript; import tree_sitter_typescript as tstypescript"