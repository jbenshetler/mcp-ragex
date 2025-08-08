# CUDA ML Image for MCP-Ragex
# This provides CUDA ML dependencies on top of CUDA base image

ARG BASE_IMAGE=mcp-ragex:cuda-base
FROM ${BASE_IMAGE}

# Switch to root to install ML dependencies
USER root

# Copy requirements files
COPY --chown=ragex:ragex requirements/ /tmp/requirements/

# Install CUDA PyTorch and ML dependencies
RUN pip install --no-cache-dir --no-warn-script-location -r /tmp/requirements/cuda.txt
RUN pip install --no-cache-dir --no-warn-script-location -r /tmp/requirements/base-ml.txt

# Pre-download tree-sitter language parsers
RUN python -c "import tree_sitter; import tree_sitter_python as tspython; import tree_sitter_javascript as tsjavascript; import tree_sitter_typescript as tstypescript"

# Switch back to non-root user
USER ragex