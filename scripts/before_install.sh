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

echo "BeforeInstall hook completed."
