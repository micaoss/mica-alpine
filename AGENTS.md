## Project Development

This project follows `/pma` for workflow and `/pma-cr` for review.
The implementation is Dockerfiles, Bash, and an Alpine/OpenRC filesystem
overlay. Python standard-library scripts verify archives and QEMU boots.

- Target platform is explicit: `make build PLATFORM=linux/arm64`.
- Outputs: `dist/<platform-with-hyphens>/rootfs.tar.gz` and its SHA-256 file.
- Validation: `make check`, `make verify PLATFORM=...`, and
  `make smoke PLATFORM=...` for amd64 and arm64.
- Do not assume a board, console device, partition layout, or kernel modules.
- Backward compatibility is not required unless explicitly requested.
- Do not create commits, push, or use subagents unless the user requests it.
- Communicate in Chinese; write repository files in English.

Tracking: `docs/task/index.md` and `docs/changelog.md`.
Release: `.github/workflows/release.yml` (manual, tag `YYYYMMDD-HHMM`).
