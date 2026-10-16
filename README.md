# Mica Alpine

A minimal Alpine/OpenRC debug userspace for Linux kernel and board projects.
Builds do not require a board BSP, kernel modules, firmware, or a bootloader.

## Build

Requirements: a Linux build host with Docker Engine, Buildx, Bash, Make, and
GNU coreutils (`timeout`). Select the target explicitly:

```sh
make build PLATFORM=linux/amd64
make build PLATFORM=linux/arm64
make build PLATFORM=linux/arm/v7
```

Each invocation produces two files, for example:

```text
dist/linux-arm64/rootfs.tar.gz
dist/linux-arm64/rootfs.tar.gz.sha256
```

Other platform selectors in the pinned Alpine image are `linux/386`,
`linux/arm/v6`, `linux/arm64/v8`, `linux/ppc64le`, `linux/riscv64`, and
`linux/s390x`. A platform must also have every package in `packages.txt` and
work on the selected builder. A build fails if a required package is absent;
it never substitutes another architecture or silently reduces the tool set.

Cross-platform builds require native target execution or a BuildKit builder
with the corresponding QEMU user emulator. To select an existing builder:

```sh
make build PLATFORM=linux/arm64 BUILDER=my-builder
```

The workflow uses the current Buildx builder unless `BUILDER` is specified.
It does not register host emulators or change the selected builder. See
[Docker's multi-platform build documentation](https://docs.docker.com/build/building/multi-platform/)
for builder setup. Compression runs on the builder's native architecture.

`images.env` pins the Alpine image by digest. Packages come from that release's
live repositories; future builds can receive package updates and are not
promised to be byte-identical. Installed package versions, the Docker platform,
and the APK architecture are recorded in `/usr/share/mica-alpine/`.

## Use with a kernel

Verify the checksum, then extract onto the consumer project's mounted root
filesystem, preserving ownership and permissions:

```sh
(cd dist/linux-arm64 && sha256sum -c rootfs.tar.gz.sha256)
sudo tar --numeric-owner --xattrs --acls -xzf dist/linux-arm64/rootfs.tar.gz -C /mnt/rootfs
```

The archive's top-level entries are `etc/`, `usr/`, `var/`, and the other root
directories. It contains no wrapping project directory. A writable ext4 root
partition is a straightforward integration option. The consuming project owns
partitioning, filesystem creation, flashing, and bootloader configuration.

Supply the correct CPU-architecture kernel and board DTB/bootloader. A typical
kernel command line is:

```text
console=ttyS0,115200 root=/dev/mmcblk0p2 rootwait rw init=/sbin/init
```

Replace the console and root device for the actual board. The rootfs follows
the kernel's active console and preserves its baud rate; a virtual terminal
console uses `tty1`. Required kernel capabilities include ELF execution,
Unix98 PTYs, procfs, sysfs, tmpfs, devtmpfs, and the chosen root filesystem.
For booting without an initramfs, enable automatic devtmpfs mounting and build
the root storage controller and filesystem drivers into the kernel.

Install any matching consumer-built modules into
`/lib/modules/<kernel-release>/` and run `depmod` for that release. Put required
firmware under `/lib/firmware/`. Drivers needed to mount root must be built in
or included in the consumer's initramfs. A tar.gz root filesystem is not a cpio
initramfs and cannot be passed directly to the kernel as an initrd.

## Runtime defaults

- Hostname: `mica-alpine`.
- Lab accounts: `root` / `root` and `alpine` / `alpine`; `alpine` can use doas
  with its password. These are public debug credentials; change them when
  adapting the image for a non-lab environment.
- OpenRC starts device management, logs, networking, Dropbear SSH, cron, and
  BusyBox `ntpd`.
- The `dhcpcd` service obtains addresses by DHCP on every Ethernet (`eth*`,
  `en*`) and Wi-Fi (`wlan*`) interface, including interfaces and links that
  appear after boot. A missing cable or lease does not block login or SSH.
- `/etc/network/interfaces` (ifupdown-ng) brings up `lo` and authenticates
  Wi-Fi; it does not assign Ethernet addresses.
- Dropbear host keys and machine ID are created on first boot and persist on the
  writable root. Dropbear has no SFTP server; OpenSSH clients use `scp -O`. No private host keys or machine ID are shared in the archive.
- Wi-Fi (`wpa_supplicant`, `iw`), `ethtool`, CAN, I2C, PCI, USB, and DRM
  (`modetest`) diagnostics are installed; BusyBox provides the shell, `ip`,
  `wget`, `fdisk`, and other core utilities. Hardware services are started
  explicitly after supplying suitable drivers. Bluetooth, firewall, ext4
  mkfs/fsck, time zone data, `strace`, `tcpdump`, and Docker are not included;
  install them with `apk add` on a networked board.
- No service rewrites partition tables, resizes storage, assigns board-specific
  MAC addresses, configures CAN bitrates, or changes USB gadget/LED state.

To give one interface a static address instead of DHCP, add to
`/etc/dhcpcd.conf`:

```text
interface eth1
static ip_address=192.168.1.100/24
static routers=192.168.1.1
static domain_name_servers=192.168.1.1
```

To take an interface away from dhcpcd entirely, add `denyinterfaces eth1`
(it overrides `allowinterfaces`) and configure it in `/etc/network/interfaces`
or by hand. Apply `dhcpcd.conf` edits with `rc-service dhcpcd restart` from the
console; this also restarts dropbear. For a one-off change until reboot, run
`dhcpcd -k eth1` and configure the interface with `ip`.

For Wi-Fi, add a `network={...}` block containing the SSID and credentials to
`/etc/wpa_supplicant/wpa_supplicant.conf`, then run `ifup wlan0`. The existing
`wlan0` stanza uses ifupdown's Wi-Fi executor and points to that config file:

```text
# Uncomment to start this interface at boot:
# auto wlan0
iface wlan0 inet manual
    use wifi
    wifi-config-path /etc/wpa_supplicant/wpa_supplicant.conf
```

dhcpcd obtains the address once the link is associated; `ifdown wlan0` stops
the supplicant. Do not start a second global wpa_supplicant service. Wireless
drivers and firmware must come from the consuming kernel project.

## Verify

```sh
make check
make verify PLATFORM=linux/amd64
make smoke PLATFORM=linux/amd64
make smoke PLATFORM=linux/arm64
```

Current delivery verification:

| Platform | Archive | QEMU boot |
| --- | --- | --- |
| `linux/amd64` | Passed (8.8 MiB) | Passed |
| `linux/arm64` | Not built | Not tested |
| `linux/arm/v7` | Not built | Not tested |

`make check` uses the host's Python 3 for syntax checks. Build and archive
verification run inside Docker. The build itself verifies archive layout,
checksum, ELF/APK architecture, permissions, startup services, and clean
machine identity. The build also checks the installed ifupdown parser, the dhcpcd
service and interface policy, and Wi-Fi executor wiring. `make verify` repeats the
archive checks on an existing artifact. Wi-Fi association has not been tested
on physical wireless hardware.

`make smoke` supports amd64 and arm64 and requires a previously built archive.
It builds test-only Alpine `linux-virt` kernels and matching modules, extracts
the delivered archive into a temporary ext4 disk, and boots it with QEMU TCG.
The supplied modules model a consuming kernel project's driver payload; the
delivered archive is not changed. Checks cover OpenRC startup, authenticated
console login and job control, DHCP/DNS, SSH for both accounts, persistent
identity across reboot, offline boot, and orderly shutdown.
Both Ethernet interfaces must obtain DHCP leases without configuration; tests
also apply a dhcpcd static address and `denyinterfaces` exclusion to the second.
The offline case boots a separate, unchanged extraction without any modules
added to the rootfs; the test initramfs supplies the root storage drivers.

Test kernels and logs stay under ignored `.tmp/`. Test containers carry the
`ai-agent=true` label and are removed on exit. The smoke runner uses the existing
`traefik` Docker network; it requires no KVM, device access, host port publishing,
or privileged containers. Bind mounts are limited to this project's artifacts,
fixtures, and scratch directory. For a remote Docker daemon, run the smoke
runner where these project paths are visible to that daemon.

## Release

Releases are manual and tagged with the UTC time `YYYYMMDD-HHMM`. Either
publish a release, which builds that tag:

```sh
gh release create 20261016-1200 --target main --title 20261016-1200 --notes ""
```

or run the `release` workflow from the Actions tab (or
`gh workflow run release -f tag=20261016-1200`), which builds the selected
branch and creates the release if it does not exist. The workflow builds
`linux/amd64` and `linux/arm64` on native runners and `linux/arm/v7` with QEMU,
then attaches `mica-alpine-<platform>.tar.gz` for each platform and
`SHA256SUMS`. Rerunning it replaces the assets of that release.

## Maintain

`rootfs/` mirrors the installed `/`; keep static configuration there. Put the
required package list in `packages.txt`, build logic in `Dockerfile`, and host
entry points in `scripts/`. Keep device-specific setup in consuming projects.
Use `make check`, rebuild each affected target, and rerun its verification.

The project source is licensed under Apache-2.0. Installed Alpine packages
retain their respective licenses.
