#!/bin/bash
set -e

cd /home/zai/ruobr-bot

ENV_FILE="${1:-.env}"
CONTAINER_NAME="${2:-ruobr-bot}"
DATA_DIR="${3:-data-prod}"

echo "=== Deploy ruobr-bot ($CONTAINER_NAME) ==="
echo "Env: $ENV_FILE | Data: $DATA_DIR"

echo "Pulling latest code..."
git pull

echo "Stopping old container..."
docker stop $CONTAINER_NAME 2>/dev/null || true
docker rm $CONTAINER_NAME 2>/dev/null || true

echo "Building..."
docker build -t ruobr-bot_bot .

echo "Starting $CONTAINER_NAME..."
docker run -d \
  --name $CONTAINER_NAME \
  --restart unless-stopped \
  --network host \
  --env-file $ENV_FILE \
  -v $(pwd)/$DATA_DIR:/app/data \
  ruobr-bot_bot

echo "Waiting for startup..."
sleep 3

echo "=== Status ==="
docker ps --filter name=$CONTAINER_NAME --format "table {{.Names}}\t{{.Status}}"
echo "=== Logs (last 5 lines) ==="
docker logs $CONTAINER_NAME --tail 5 2>&1
echo "=== Done ==="

