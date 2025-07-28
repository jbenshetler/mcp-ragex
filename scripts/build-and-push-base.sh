#!/bin/bash
# Build and push the base image to GHCR
# This is needed for the initial setup before the workflow is on main branch

set -e

REGISTRY="ghcr.io"
REPO="jbenshetler/mcp-ragex-base"
TAG="latest"

echo "Building base image locally..."
docker build -f docker/base.Dockerfile -t $REGISTRY/$REPO:$TAG .

echo "Logging in to GitHub Container Registry..."

# Check for environment variables first
if [ -n "$GITHUB_USER" ] && [ -n "$GITHUB_TOKEN" ]; then
    echo "Using credentials from environment variables"
elif [ -n "$GITHUB_REGEX_DOCKER_PAT" ]; then
    # Support the specific env var mentioned
    echo "Using GITHUB_REGEX_DOCKER_PAT for authentication"
    GITHUB_TOKEN="$GITHUB_REGEX_DOCKER_PAT"
    # Try to get username from git config or environment
    if [ -n "$GITHUB_USER" ]; then
        echo "Using GITHUB_USER from environment"
    else
        GITHUB_USER=$(git config user.name 2>/dev/null || echo "")
        if [ -z "$GITHUB_USER" ]; then
            echo "Error: GITHUB_USER not set and could not determine from git config"
            echo "Please set GITHUB_USER environment variable"
            exit 1
        fi
        echo "Using GitHub username from git config: $GITHUB_USER"
    fi
else
    # Interactive mode
    echo "You'll need a GitHub Personal Access Token with 'packages:write' permission"
    echo "Create one at: https://github.com/settings/tokens"
    read -p "Enter your GitHub username: " GITHUB_USER
    read -s -p "Enter your GitHub PAT: " GITHUB_TOKEN
    echo
fi

echo "$GITHUB_TOKEN" | docker login $REGISTRY -u "$GITHUB_USER" --password-stdin

echo "Pushing base image..."
docker push $REGISTRY/$REPO:$TAG

# Also tag with date
DATE_TAG=$(date +'%Y.%m.%d')
docker tag $REGISTRY/$REPO:$TAG $REGISTRY/$REPO:$DATE_TAG
docker push $REGISTRY/$REPO:$DATE_TAG

echo "Base image pushed successfully!"
echo "Images available at:"
echo "  - $REGISTRY/$REPO:latest"
echo "  - $REGISTRY/$REPO:$DATE_TAG"
