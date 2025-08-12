# CPU ML Image for MCP-Ragex
# This provides ML dependencies on top of CPU base image

ARG BASE_IMAGE=scratch
FROM ${BASE_IMAGE}

# Copy requirements files
COPY --chown=ragex:ragex requirements/ ./requirements/

# Install PyTorch and ML dependencies based on architecture
ARG TARGETARCH
RUN set -e; \
    echo "Building ML layer for architecture: ${TARGETARCH:-unknown}"; \
    if [ "$TARGETARCH" = "amd64" ] || [ -z "$TARGETARCH" ]; then \
      echo "Installing AMD64 CPU-only PyTorch and ML deps..."; \
      pip install --no-cache-dir --no-warn-script-location -r requirements/cpu-amd64.txt; \
    elif [ "$TARGETARCH" = "arm64" ]; then \
      echo "Installing ARM64 PyTorch and ML deps..."; \
      pip install --no-cache-dir --no-warn-script-location -r requirements/cpu-arm64.txt; \
    else \
      echo "Unsupported architecture: $TARGETARCH"; \
      exit 1; \
    fi

# Install core ML dependencies
RUN pip install --no-cache-dir --no-warn-script-location -r requirements/base-ml.txt

# Pre-download tree-sitter language parsers
RUN python -c "import tree_sitter; import tree_sitter_python as tspython; import tree_sitter_javascript as tsjavascript; import tree_sitter_typescript as tstypescript"

# Pre-download fast embedding model for offline operation
# Switch to root to create directory, then back to ragex
USER root
RUN mkdir -p /opt/models && chown ragex:ragex /opt/models
USER ragex
# Set cache directories to use build-time location
ENV HF_HOME=/opt/models
ENV SENTENCE_TRANSFORMERS_HOME=/opt/models
RUN python -c "from sentence_transformers import SentenceTransformer; print('Downloading fast embedding model for offline operation...'); SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2'); print('Fast model cached successfully!')"