#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/common.sh"
mode=${1:-verify}
case "$mode" in
    verify) ;;
    smoke)
        case "$PLATFORM" in
            linux/amd64|linux/arm64|linux/arm64/v8) ;;
            *) echo 'error: QEMU smoke supports amd64 and arm64; archive verification supports all build targets' >&2; exit 2 ;;
        esac ;;
    *) echo 'error: expected verify or smoke' >&2; exit 2 ;;
esac
test -f "dist/$platform_dir/rootfs.tar.gz"
if [[ $mode == smoke ]]; then
    bash scripts/build.sh fixture
fi
# Sibling containers resolve bind paths on the Docker daemon's host.
case "$project_dir" in
    /work/*) host_project="/srv/station/work/${project_dir#/work/}" ;;
    /root/*) host_project="/srv/station/root/${project_dir#/root/}" ;;
    *) host_project=$project_dir ;;
esac
timeout 900 docker buildx build "${builder_args[@]}" \
    --build-arg "ALPINE_IMAGE=$ALPINE_IMAGE" --target test-tools \
    --label ai-agent=true --tag ai-agent/mica-alpine-test-tools:local --load --progress plain .
container_name="ai-agent-mica-alpine-test-$$"
cleanup() { docker rm -f "$container_name" >/dev/null 2>&1 || true; }
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
run_args=(--rm --name "$container_name" --label ai-agent=true --network traefik
    --mount "type=bind,src=$host_project/dist/$platform_dir,dst=/artifact,readonly")
if [[ $mode == verify ]]; then
    timeout 120 docker run "${run_args[@]}" ai-agent/mica-alpine-test-tools:local \
        python3 /usr/local/bin/verify-archive.py /artifact/rootfs.tar.gz "$PLATFORM"
else
    mkdir -p .tmp
    run_dir=$(mktemp -d "$project_dir/.tmp/smoke-$platform_dir.XXXXXX")
    host_run="$host_project/${run_dir#"$project_dir"/}"
    printf 'Boot evidence: %s\n' "$run_dir"
    timeout 900 docker run "${run_args[@]}" \
        --mount "type=bind,src=$host_project/.tmp/fixtures/$platform_dir,dst=/fixture,readonly" \
        --mount "type=bind,src=$host_run,dst=/work" \
        ai-agent/mica-alpine-test-tools:local \
        python3 /usr/local/bin/boot.py "$PLATFORM"
fi
