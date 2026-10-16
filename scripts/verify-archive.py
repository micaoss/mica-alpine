#!/usr/bin/env python3
"""Check a delivered archive without extracting or executing target binaries."""
import hashlib
from pathlib import Path, PurePosixPath
import struct
import sys
import tarfile


def verify(path, platform):
    machines = {
        "linux/amd64": (62, "x86_64"),
        "linux/386": (3, "x86"),
        "linux/arm64": (183, "aarch64"),
        "linux/arm64/v8": (183, "aarch64"),
        "linux/arm/v6": (40, "armhf"),
        "linux/arm/v7": (40, "armv7"),
        "linux/ppc64le": (21, "ppc64le"),
        "linux/riscv64": (243, "riscv64"),
        "linux/s390x": (22, "s390x"),
    }
    expected_machine, expected_apk = machines[platform]
    checksum = Path(str(path) + ".sha256").read_text().split()
    assert len(checksum) == 2 and checksum[1] == path.name, "invalid checksum manifest"
    with path.open("rb") as stream:
        digest = hashlib.sha256()
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
        assert digest.hexdigest() == checksum[0], "SHA-256 mismatch"
    with tarfile.open(path, "r:gz") as archive:
        members = {entry.name.removeprefix("./"): entry for entry in archive.getmembers()}
        for name in members:
            assert not name.startswith("/") and ".." not in PurePosixPath(name).parts, f"unsafe archive path: {name}"

        def read(name):
            with archive.extractfile(members[name]) as stream:
                return stream.read()

        for name in ("etc", "usr", "var", "dev", "proc", "sys", "run", "tmp"):
            assert members[name].isdir(), f"missing root directory: {name}"
        for name in ("sbin/init", "sbin/openrc", "bin/busybox", "usr/sbin/dropbear", "usr/bin/doas", "usr/local/sbin/console-getty"):
            entry = members[name]
            assert entry.uid == 0 and entry.gid == 0, f"incorrect ownership: {name}"
            assert entry.mode & 0o111, f"not executable: {name}"
        header = read("bin/busybox")[:20]
        assert header[:4] == b"\x7fELF", "BusyBox is not ELF"
        byte_order = "<" if header[5] == 1 else ">"
        assert struct.unpack(byte_order + "H", header[18:20])[0] == expected_machine, "wrong ELF architecture"
        assert read("usr/share/mica-alpine/apk-arch").decode().strip() == expected_apk, "wrong APK architecture"
        actual_platform = read("usr/share/mica-alpine/platform").decode().strip()
        assert actual_platform.removesuffix("/v8") == platform.removesuffix("/v8"), "wrong platform metadata"
        assert read("etc/hostname") == b"mica-alpine\n", "wrong hostname"
        assert read("etc/doas.d/wheel.conf") == b"permit :wheel\n", "missing doas wheel policy"
        assert members["tmp"].mode == 0o1777, "incorrect /tmp permissions"
        assert read("etc/shadow").splitlines()[0].split(b":")[1] not in (b"", b"!", b"*"), "root account must require a password"
        assert b"alpine:" in read("etc/passwd"), "missing debug user"
        assert b"klogd:" in read("etc/passwd"), "missing klogd service account"
        installed = {line.rsplit("-", 2)[0] for line in read("usr/share/mica-alpine/packages.txt").decode().split()}
        for package in ("docker", "docker-cli-compose", "openssh", "sudo", "chrony", "iproute2", "curl", "bluez",
                        "dbus", "bash", "nftables", "iptables", "tzdata", "parted", "sgdisk", "cloud-utils-growpart",
                        "e2fsprogs", "file", "htop", "strace", "tcpdump"):
            assert package not in installed, f"excluded package installed: {package}"
        assert not read("etc/resolv.conf").startswith(b"nameserver"), "build host DNS leaked"
        interfaces = read("etc/network/interfaces").decode().splitlines()
        assert [line for line in interfaces if line.startswith("auto ")] == ["auto lo"], "only lo is managed by ifupdown at boot"
        assert not any(line.startswith("iface eth") for line in interfaces), "Ethernet must be managed by dhcpcd"
        assert "iface wlan0 inet manual" in interfaces, "Wi-Fi stanza must only authenticate"
        assert b"wifi-config-path /etc/wpa_supplicant/wpa_supplicant.conf" in read("etc/network/interfaces"), "missing interfaces-managed Wi-Fi authentication"
        assert members["etc/wpa_supplicant/wpa_supplicant.conf"].mode == 0o600, "Wi-Fi credentials must be root-only"
        dhcpcd = read("etc/dhcpcd.conf").decode().splitlines()
        assert "allowinterfaces eth* en* wlan*" in dhcpcd, "dhcpcd must manage every Ethernet and Wi-Fi interface"
        assert "background" not in dhcpcd, "the dhcpcd service must not fork early"
        for level, services in {
            "sysinit": ("devfs", "mdev", "hwdrivers"),
            "boot": ("hostname", "networking", "dhcpcd", "machine-id", "seedrng"),
            "default": ("dropbear", "ntpd", "crond"),
            "shutdown": ("killprocs", "mount-ro"),
        }.items():
            for service in services:
                entry = members[f"etc/runlevels/{level}/{service}"]
                assert entry.issym(), f"service not linked: {service}"
                assert f"etc/init.d/{service}" in members, f"service implementation missing: {service}"
        for name in members:
            assert not name.startswith(("etc/dropbear/dropbear_", "lib/modules/", "lib/firmware/")), f"non-generic payload: {name}"
            assert not name.startswith(("proc/", "sys/", "dev/")), f"build device state leaked: {name}"
            assert name not in ("etc/machine-id", "var/lib/dbus/machine-id", "var/lib/misc/random-seed", "var/lib/seedrng/seed"), f"shared machine identity: {name}"
        for service in ("wpa_supplicant",):
            assert not any(f"etc/runlevels/{level}/{service}" in members for level in ("sysinit", "boot", "default")), f"unexpected automatic service: {service}"
    print(f"PASS: {platform} archive, SHA-256, ELF, permissions, startup, and clean identity", flush=True)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("usage: verify-archive.py <rootfs.tar.gz> <platform>")
    verify(Path(sys.argv[1]), sys.argv[2])
