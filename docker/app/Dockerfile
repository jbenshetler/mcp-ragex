ARG BASE_IMAGE=mcp-ragex:cpu-amd64-ml
FROM ${BASE_IMAGE}

# Switch to root to install app dependencies and set permissions
USER root

# Copy application code
COPY --chown=ragex:ragex src/ ./src/

# Copy requirements and install app-specific dependencies
COPY --chown=ragex:ragex requirements/app.txt /tmp/
RUN pip install --no-cache-dir --no-warn-script-location -r /tmp/app.txt

# Copy entrypoint and set permissions
COPY --chown=ragex:ragex docker/common/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Switch back to non-root user
USER ragex

ENTRYPOINT ["/entrypoint.sh"]