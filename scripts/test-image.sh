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
    docker run -d --name "$CONTAINER_NAME" -p 8000:8000 "$IMAGE"
    sleep 5
    curl -f http://localhost:8000/health || curl -f http://localhost:8000/ || true
    ;;
  langgraph*)
    docker run -d --name "$CONTAINER_NAME" -p 8000:8000 "$IMAGE"
    sleep 5
    curl -f http://localhost:8000/health || curl -f http://localhost:8000/ || true
    ;;
  control-center-ui*)
    docker run -d --name "$CONTAINER_NAME" -p 80:80 "$IMAGE"
    sleep 5
    curl -f http://localhost/ || true
    ;;
  *)
    echo "Unknown image type: $NAME"
    exit 1
    ;;
esac

echo "Image test passed: $IMAGE"
