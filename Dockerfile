# Stage 1: Builder
FROM python:3.10-slim AS builder

# Install build dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build

# Copy dependency files
COPY requirements.txt pyproject.toml ./

# Install Python dependencies
RUN pip install --user --no-cache-dir -r requirements.txt

# Stage 2: Test (optional stage for CI/CD)
FROM python:3.10-slim AS test

# Install test dependencies
RUN apt-get update && apt-get install -y \
    git \
    ripgrep \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy dependencies from builder
COPY --from=builder /root/.local /root/.local
ENV PATH=/root/.local/bin:$PATH

# Copy all code including tests
COPY . .

# Install test dependencies
RUN pip install --no-cache-dir pytest pytest-cov

# Run tests
CMD ["python", "-m", "pytest", "tests/", "-v"]

# Stage 3: Runtime
FROM python:3.10-slim

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    git \
    ripgrep \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN useradd -m -u 1000 ragex

WORKDIR /app

# Copy dependencies from builder
COPY --from=builder /root/.local /home/ragex/.local
ENV PATH=/home/ragex/.local/bin:$PATH

# Copy application code
COPY --chown=ragex:ragex src/ ./src/
COPY --chown=ragex:ragex scripts/ ./scripts/
COPY --chown=ragex:ragex pyproject.toml ./
COPY --chown=ragex:ragex ragex_search.py ./

# Create data directories
RUN mkdir -p /data/chroma_db /data/models && \
    chown -R ragex:ragex /data

# Switch to non-root user
USER ragex

# Pre-download tree-sitter language parsers (after switching to user with Python packages)
RUN python -c "import tree_sitter; import tree_sitter_python as tspython; import tree_sitter_javascript as tsjavascript; import tree_sitter_typescript as tstypescript"

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV RAGEX_DATA_DIR=/data
ENV TRANSFORMERS_CACHE=/data/models
ENV SENTENCE_TRANSFORMERS_HOME=/data/models
ENV DOCKER_CONTAINER=true
ENV LOG_LEVEL=INFO

# Copy and set entrypoint
COPY --chown=ragex:ragex docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh
ENTRYPOINT ["/entrypoint.sh"]