#!/bin/bash
set -e

echo "Validating service..."

# Wait for a few seconds to let the application start
sleep 10

# Retry loop
for i in {1..10}; do
    if curl -sf --max-time 5 http://localhost:8000/health; then
        echo ""
        echo "Service is healthy!"
        exit 0
    fi
    echo "Waiting for service to be healthy... ($i/10)"
    sleep 5
done

echo "Service failed to become healthy."
exit 1
