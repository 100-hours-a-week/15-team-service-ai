#!/bin/bash
set -e

CONTAINER_NAME="ai-server"

echo "Stopping container $CONTAINER_NAME if running..."

if docker ps -a --format '{{.Names}}' | grep -Eq "^${CONTAINER_NAME}\$"; then
    echo "Container $CONTAINER_NAME found."
    docker stop $CONTAINER_NAME || true
    docker rm $CONTAINER_NAME || true
    echo "Container $CONTAINER_NAME stopped and removed."
else
    echo "Container $CONTAINER_NAME does not exist. Skipping stop."
fi

# Prune unused images to save space
docker image prune -af --filter "until=24h" || true
