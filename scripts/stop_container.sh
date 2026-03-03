#!/bin/bash
set -e

CONTAINER_NAME="ai-server"

DEPLOY_DIR="/home/ubuntu/deploy"

echo "Stopping containers using docker compose if they exist..."

if [ -f "$DEPLOY_DIR/docker-compose.yml" ]; then
    cd "$DEPLOY_DIR"
    docker compose down || true
    echo "Containers stopped and removed via docker compose."
else
    # Fallback to older mechanism if no docker-compose.yml
    if docker ps -a --format '{{.Names}}' | grep -Eq "^${CONTAINER_NAME}\$"; then
        echo "Container $CONTAINER_NAME found. Using docker stop..."
        docker stop $CONTAINER_NAME || true
        docker rm $CONTAINER_NAME || true
    fi
fi

# Prune unused images to save space
docker image prune -af --filter "until=24h" || true
