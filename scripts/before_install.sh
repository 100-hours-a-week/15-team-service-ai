#!/bin/bash
set -e

# Validate deployment directory exists
mkdir -p /home/ubuntu/deploy

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

# In CodeDeploy, files are copied to destination during Install (after BeforeInstall).
# Validate bundle content from deployment archive path when env vars are available.
if [ -n "$DEPLOYMENT_GROUP_ID" ] && [ -n "$DEPLOYMENT_ID" ]; then
    ARCHIVE_DIR="/opt/codedeploy-agent/deployment-root/$DEPLOYMENT_GROUP_ID/$DEPLOYMENT_ID/deployment-archive"
    if [ ! -f "$ARCHIVE_DIR/docker-compose.yml" ]; then
        echo "Error: docker-compose.yml not found in deployment archive ($ARCHIVE_DIR)."
        exit 1
    fi
    echo "docker-compose.yml found in deployment archive."
else
    echo "Warning: DEPLOYMENT_GROUP_ID/DEPLOYMENT_ID not set. Skipping archive compose check."
fi

echo "BeforeInstall hook completed."
