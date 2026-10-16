# Changelog

## 2026-10-16 05:30 [progress]

Completed `20261016-0508-dhcp-all-ethernet`. The dhcpcd service (boot runlevel)
now obtains DHCP leases on every `eth*`, `en*`, and `wlan*` interface, including
hotplugged ones. ifupdown-ng brings up `lo` and only authenticates Wi-Fi
(`wlan0` is `inet manual` with the Wi-Fi executor). Static addresses and
exclusions are configured in `/etc/dhcpcd.conf`. amd64 archive verification and
QEMU smoke pass: both NICs lease without configuration, static and
`denyinterfaces` overrides apply, and offline boot starts dropbear cleanly.

## 2026-10-16 05:30 [progress]

Added the manual `release` workflow: a published `YYYYMMDD-HHMM` release or a
workflow_dispatch run builds amd64/arm64 natively and ARMv7 with QEMU, then
attaches `mica-alpine-<platform>.tar.gz` and `SHA256SUMS`. Removed `docs/plan/`.

## 2026-10-16 05:10 [progress]

Initial project state: a minimal Alpine/OpenRC debug rootfs built per platform
with Docker. 18 packages; Dropbear SSH, doas, BusyBox ntpd/ip/wget,
ifupdown-ng with dhcpcd, Wi-Fi, and CAN/I2C/PCI/USB/DRM diagnostics. The amd64
archive is about 9 MiB and passes archive verification and QEMU smoke. arm64
and ARMv7 have not been built: no available builder executes arm binaries.
