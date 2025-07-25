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
echo "You'll need a GitHub Personal Access Token with 'packages:write' permission"
echo "Create one at: https://github.com/settings/tokens"
read -p "Enter your GitHub username: " GITHUB_USER
read -s -p "Enter your GitHub PAT: " GITHUB_TOKEN
echo

echo $GITHUB_TOKEN | docker login $REGISTRY -u $GITHUB_USER --password-stdin

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