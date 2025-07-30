#!/bin/bash
# Debug script to test index command

echo "=== Testing ragex index command ==="
echo "Date: $(date)"
echo "Working directory: $(pwd)"
echo

# Enable debug mode
export RAGEX_DEBUG=true

# Run in foreground to see what happens
echo "Running: ragex index ."
ragex index .

echo
echo "Exit code: $?"