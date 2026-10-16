#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/common.sh"
target=${1:-artifact}
case "$target" in
    artifact) output="dist/$platform_dir" ;;
    fixture) output=".tmp/fixtures/$platform_dir" ;;
    *) echo 'error: expected artifact or fixture' >&2; exit 2 ;;
esac
timeout 1800 docker buildx build "${builder_args[@]}" \
    --platform "$PLATFORM" --build-arg "ALPINE_IMAGE=$ALPINE_IMAGE" \
    --label ai-agent=true --tag "ai-agent/mica-alpine-$target:$platform_dir" \
    --target "$target" --output "type=local,dest=$output" --progress plain .
