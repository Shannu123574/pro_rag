#!/bin/bash
set -e

echo "Starting CI pipeline..."

# 1. Start containers in the background
echo "Starting services..."
docker compose up -d

# 2. Wait for services to be healthy
echo "Waiting for API to become ready..."
for i in {1..30}; do
    if curl -s http://localhost:8000/ready > /dev/null; then
        echo "API is ready!"
        break
    fi
    echo "Waiting for API..."
    sleep 2
done

# 3. Run all tests
echo "Running full test suite..."
docker compose exec -T api pytest tests/ -v

echo "CI Pipeline completed successfully!"
