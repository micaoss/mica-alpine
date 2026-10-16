#!/usr/bin/env python3
"""Boot a delivered rootfs with a separately supplied kernel and driver modules."""
import importlib.util
import os
from pathlib import Path
import pty
import re
import select
import subprocess
import sys
import time
import tty


def run(*args):
    return subprocess.run(args, check=True, text=True, capture_output=True, timeout=120).stdout


class Guest:
    def __init__(self, platform, online, log):
        arch = "arm64" if platform.startswith("linux/arm64") else "amd64"
        binary, machine, console = {
            "amd64": ("qemu-system-x86_64", "q35", "ttyS0"),
            "arm64": ("qemu-system-aarch64", "virt", "ttyAMA0"),
        }[arch]
        self.console = console
        disk = "/work/root.img" if online else "/work/offline.img"
        self.buffer = b""
        self.log = log.open("wb")
        self.master, slave = pty.openpty()
        tty.setraw(slave)
        command = [binary, "-machine", machine, "-accel", "tcg", "-cpu", "max",
                   "-m", "2048", "-smp", "2", "-display", "none", "-serial", "stdio",
                   "-monitor", "none", "-kernel", "/fixture/kernel", "-initrd", "/fixture/initramfs",
                   "-append", f"console={console},115200 root=/dev/vda rootfstype=ext4 rw init=/sbin/init",
                   "-drive", f"file={disk},format=raw,if=none,id=root",
                   "-device", "virtio-blk-pci,drive=root"]
        if online:
            command += ["-netdev", "user,id=net0,hostfwd=tcp:127.0.0.1:2222-:22",
                        "-device", "virtio-net-pci,netdev=net0,mac=52:54:00:12:34:01",
                        "-netdev", "user,id=net1,net=10.0.3.0/24",
                        "-device", "virtio-net-pci,netdev=net1,mac=52:54:00:12:34:02"]
        else:
            command += ["-nic", "none"]
        self.process = subprocess.Popen(command, stdin=slave, stdout=slave, stderr=slave)
        os.close(slave)

    def wait(self, pattern, seconds=180):
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            match = re.search(pattern, self.buffer)
            if match:
                result, self.buffer = self.buffer[:match.end()], self.buffer[match.end():]
                return result
            if select.select([self.master], [], [], 0.2)[0]:
                try:
                    data = os.read(self.master, 65536)
                except OSError:
                    data = b""
                if not data:
                    break
                self.log.write(data)
                self.log.flush()
                self.buffer += data.replace(b"\r", b"")
            if self.process.poll() is not None:
                break
        raise AssertionError(f"guest did not reach {pattern!r}: {self.buffer[-4000:]!r}")

    def send(self, command):
        os.write(self.master, command.encode() + b"\n")

    def login(self):
        self.wait(rb"login: ")
        self.send("root")
        self.wait(rb"Password: ")
        self.send("root")
        self.wait(rb"~# ")
        self.send("stty -echo")
        self.wait(rb"~# ")

    def command(self, command):
        self.send(command + "; printf '\\nCHECK_STATUS=%s\\n' \"$?\"")
        output = self.wait(rb"CHECK_STATUS=\d+\r?\n", 60)
        assert b"CHECK_STATUS=0" in output, output.decode(errors="replace")
        return output.decode(errors="replace")

    def close(self):
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=10)
        os.close(self.master)
        self.log.close()


def ssh(command, user="root"):
    password = "root" if user == "root" else "alpine"
    return run("sshpass", "-p", password, "ssh", "-o", "StrictHostKeyChecking=no",
               "-o", "UserKnownHostsFile=/dev/null", "-o", "ConnectTimeout=5",
               "-p", "2222", f"{user}@127.0.0.1", command)


def wait_ssh():
    deadline = time.monotonic() + 60
    while True:
        try:
            ssh("true")
            return
        except (subprocess.SubprocessError, OSError):
            if time.monotonic() >= deadline:
                raise
            time.sleep(1)


def main(platform):
    spec = importlib.util.spec_from_file_location("verify", "/usr/local/bin/verify-archive.py")
    verifier = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(verifier)
    verifier.verify(Path("/artifact/rootfs.tar.gz"), platform)
    root = Path("/work/root")
    root.mkdir()
    run("tar", "--numeric-owner", "--xattrs", "--acls", "-xzf", "/artifact/rootfs.tar.gz", "-C", str(root))
    # A separate, unchanged archive must also boot without a modules payload.
    run("truncate", "-s", "2G", "/work/offline.img")
    run("mke2fs", "-q", "-F", "-t", "ext4", "-d", str(root), "/work/offline.img")
    # The consuming kernel supplies its own modules, as on a physical board.
    run("tar", "-xzf", "/fixture/modules.tar.gz", "-C", str(root))
    run("truncate", "-s", "2G", "/work/root.img")
    run("mke2fs", "-q", "-F", "-t", "ext4", "-d", str(root), "/work/root.img")
    guest = Guest(platform, True, Path("/work/online.log"))
    try:
        guest.login()
        guest.command("test \"$(cat /proc/1/comm)\" = init && test -d /run/openrc && "
                      "mountpoint -q /proc && mountpoint -q /sys && mountpoint -q /dev")
        guest.command(f"test \"$(tty)\" = /dev/{guest.console} && test -r /dev/tty && "
                      "set -o | grep -E '^monitor[[:space:]]+on$'")
        guest.command("sleep 30 & job=$!; jobs; kill \"$job\"; wait \"$job\"; test $? -gt 128")
        guest.command("rc-service dropbear status && rc-service networking status && rc-service dhcpcd status && "
                      "rc-service syslog status && rc-service klogd status")
        wait_ssh()
        lease = ("for attempt in $(seq 1 30); do ip -4 addr show dev {0} | grep -q 'inet {1}' && break; "
                 "sleep 1; done; ip -4 addr show dev {0} | grep -q 'inet {1}'")
        guest.command(lease.format("eth0", "10.0.2.") + " && " + lease.format("eth1", "10.0.3."))
        guest.command("cp /etc/dhcpcd.conf /tmp/dhcpcd.conf && "
                      "printf 'interface eth1\\nstatic ip_address=192.0.2.10/24\\n' >> /etc/dhcpcd.conf && "
                      "rc-service dhcpcd restart && " + lease.format("eth1", "192.0.2.10/24") + " && "
                      "! ip -4 addr show dev eth1 | grep -q 'inet 10.0.3.'")
        guest.command("cp /tmp/dhcpcd.conf /etc/dhcpcd.conf && echo 'denyinterfaces eth1' >> /etc/dhcpcd.conf && "
                      "rc-service dhcpcd restart && " + lease.format("eth0", "10.0.2.") + " && sleep 5 && "
                      "! ip -4 addr show dev eth1 | grep -q 'inet '")
        guest.command("cp /tmp/dhcpcd.conf /etc/dhcpcd.conf && rc-service dhcpcd restart && "
                      + lease.format("eth0", "10.0.2.") + " && " + lease.format("eth1", "10.0.3."))
        wait_ssh()
        print(f"PASS: {platform} automatic DHCP on every Ethernet port, static address, and exclusion", flush=True)
        print(ssh("set -e; test \"$(hostname)\" = mica-alpine; "
                  "ip -4 route show default | grep default; grep '^nameserver ' /etc/resolv.conf; "
                  "nslookup alpinelinux.org; rc-status default; "
                  "test -s /etc/machine-id; test -s /etc/dropbear/dropbear_ed25519_host_key; "
                  "echo ONLINE_OK"), flush=True)
        assert ssh("id -un", "alpine").strip() == "alpine"
        identity = ssh("cat /etc/machine-id; dropbearkey -y -f /etc/dropbear/dropbear_ed25519_host_key")
        boot_id = ssh("cat /proc/sys/kernel/random/boot_id").strip()
        guest.send("reboot")
        guest.wait(rb"Restarting system", 90)
        guest.login()
        guest.command("rc-service dropbear status")
        wait_ssh()
        assert ssh("cat /proc/sys/kernel/random/boot_id").strip() != boot_id
        assert ssh("cat /etc/machine-id; dropbearkey -y -f /etc/dropbear/dropbear_ed25519_host_key") == identity
        guest.send("poweroff")
        guest.wait(rb"Power down", 90)
        print(f"PASS: {platform} console, job control, DHCP/DNS, SSH users, identity, and reboot", flush=True)
    finally:
        guest.close()
    guest = Guest(platform, False, Path("/work/offline.log"))
    try:
        guest.login()
        guest.command("test \"$(cat /proc/1/comm)\" = init && rc-service dropbear status")
        guest.send("poweroff")
        guest.wait(rb"Power down", 90)
        print(f"PASS: {platform} offline boot without rootfs modules and orderly shutdown", flush=True)
    finally:
        guest.close()

    for name in ("online.log", "offline.log"):
        log = Path("/work", name).read_bytes()
        assert b" * ERROR:" not in log, f"OpenRC service failure in {name}"
        assert b"job control turned off" not in log, f"missing controlling terminal in {name}"


if __name__ == "__main__":
    try:
        main(sys.argv[1])
    except subprocess.CalledProcessError as error:
        print(error.stdout + error.stderr, file=sys.stderr)
        raise
