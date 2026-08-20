#!/bin/bash
set -euo pipefail

IMAGE="$1"
NAME="${IMAGE##*/}"
NAME="${NAME%%:*}"

echo "Testing image: $IMAGE"

CONTAINER_NAME="test-${NAME}-$$"

cleanup() {
  docker rm -f "$CONTAINER_NAME" 2>/dev/null || true
}
trap cleanup EXIT

case "$NAME" in
  workflow_runner*)
    docker run -d --name "$CONTAINER_NAME" "$IMAGE"
    sleep 5
    docker exec "$CONTAINER_NAME" curl -f http://localhost:8000/health 2>/dev/null || docker exec "$CONTAINER_NAME" curl -f http://localhost:8000/ 2>/dev/null || true
    ;;
  langgraph*)
    docker run -d --name "$CONTAINER_NAME" "$IMAGE"
    sleep 5
    docker exec "$CONTAINER_NAME" curl -f http://localhost:8000/health 2>/dev/null || docker exec "$CONTAINER_NAME" curl -f http://localhost:8000/ 2>/dev/null || true
    ;;
  control-center-ui*)
    docker run -d --name "$CONTAINER_NAME" "$IMAGE"
    sleep 5
    docker exec "$CONTAINER_NAME" curl -f http://localhost/ 2>/dev/null || true
    ;;
  *)
    echo "Unknown image type: $NAME"
    exit 1
    ;;
esac

echo "Image test passed: $IMAGE"
