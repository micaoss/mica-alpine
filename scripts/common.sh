#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
project_dir=$PWD
source ./images.env

case "${PLATFORM:-}" in
    linux/amd64|linux/386|linux/arm64|linux/arm64/v8|linux/arm/v6|linux/arm/v7|linux/ppc64le|linux/riscv64|linux/s390x) ;;
    *) echo 'error: set PLATFORM to a Linux platform in the pinned Alpine image, e.g. linux/amd64, linux/arm64, or linux/arm/v7' >&2; exit 2 ;;
esac
platform_dir=${PLATFORM//\//-}
builder_args=()
if [[ -n ${BUILDER:-} ]]; then
    builder_args=(--builder "$BUILDER")
fi
command -v docker >/dev/null
command -v timeout >/dev/null
