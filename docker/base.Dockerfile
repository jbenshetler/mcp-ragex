# Base image with all dependencies for MCP-RageX
# This image is built weekly or when dependencies change
# It contains all the slow-to-install components

FROM python:3.10-slim AS base

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    git \
    ripgrep \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create directories that will be needed
RUN mkdir -p /data/models /data/chroma_db /app

# Set working directory
WORKDIR /app

# Copy only requirements file
COPY requirements.txt ./

# Install Python dependencies - this is the slow part
RUN pip install --no-cache-dir -r requirements.txt

# Pre-download sentence transformer model
RUN python -c "from sentence_transformers import SentenceTransformer; \
    model = SentenceTransformer('all-MiniLM-L6-v2'); \
    model.save('/data/models/all-MiniLM-L6-v2'); \
    print('Model downloaded successfully')"

# Pre-compile tree-sitter languages to speed up first run
RUN python -c "import tree_sitter_python as tspython; \
    import tree_sitter_javascript as tsjavascript; \
    import tree_sitter_typescript as tstypescript; \
    print('Tree-sitter languages compiled')"

# Create non-root user
RUN useradd -m -u 1000 ragex && \
    chown -R ragex:ragex /data

# Clean up any temporary files
RUN rm -rf /tmp/* /var/tmp/* ~/.cache/pip

# Label the image
LABEL org.opencontainers.image.title="MCP-RageX Base"
LABEL org.opencontainers.image.description="Base image with dependencies for MCP-RageX"
LABEL org.opencontainers.image.authors="jbenshetler"
LABEL org.opencontainers.image.source="https://github.com/jbenshetler/mcp-ragex"
LABEL org.opencontainers.image.licenses="MIT"

# Health check to verify base dependencies
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD python -c "import sentence_transformers; import tree_sitter_python; print('OK')" || exit 1

# This is a base image, so no CMD or ENTRYPOINT