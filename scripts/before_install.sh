#!/bin/bash
set -e

# Validate deployment directory exists
mkdir -p /home/ubuntu/deploy
DEPLOY_DIR="/home/ubuntu/deploy"
COMPOSE_FILE="$DEPLOY_DIR/docker-compose.yml"

# Ensure jq is installed (SSM parameter parsing에 필요)
if ! command -v jq &> /dev/null; then
    echo "jq not found. Installing..."
    sudo apt-get update && sudo apt-get install -y jq
    echo "jq installed successfully."
else
    echo "jq is already installed."
fi

# Ensure docker compose is available on instance
if ! docker compose version > /dev/null 2>&1; then
    echo "Error: docker compose is not available on this instance."
    exit 1
fi

# Ensure compose file exists in deployment bundle
if [ ! -f "$COMPOSE_FILE" ]; then
    echo "Error: $COMPOSE_FILE not found in deployment package."
    exit 1
fi

echo "BeforeInstall hook completed."
