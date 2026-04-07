#!/bin/bash
set -e

cd /home/zai/ruobr-bot

echo "=== Deploy ruobr-bot ==="
echo "Pulling latest code..."
git pull

echo "Stopping old container..."
docker stop ruobr-bot 2>/dev/null || true
docker rm ruobr-bot 2>/dev/null || true

echo "Building..."
docker-compose build --no-cache

echo "Starting..."
docker-compose up -d

echo "Waiting for startup..."
sleep 3

echo "=== Status ==="
docker ps --filter name=ruobr-bot --format "table {{.Names}}\t{{.Status}}"
echo "=== Logs (last 5 lines) ==="
docker logs ruobr-bot --tail 5 2>&1
echo "=== Done ==="

