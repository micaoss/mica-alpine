SHELL := /bin/bash
.DEFAULT_GOAL := help
export PLATFORM BUILDER

.PHONY: help build verify fixtures smoke check
help:
	@echo 'make build PLATFORM=linux/amd64   Build a debug rootfs archive'
	@echo 'make verify PLATFORM=linux/amd64  Verify the delivered archive'
	@echo 'make smoke PLATFORM=linux/amd64   Boot in QEMU (amd64 or arm64)'
	@echo 'make check                       Check source syntax'
	@echo 'Optional: BUILDER=<existing-buildx-builder>'

build:
	bash scripts/build.sh artifact

fixtures:
	bash scripts/build.sh fixture

verify:
	bash scripts/test.sh verify

smoke:
	bash scripts/test.sh smoke

check:
	bash scripts/check.sh
