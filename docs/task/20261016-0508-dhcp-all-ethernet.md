# 20261016-0508-dhcp-all-ethernet DHCP on every eth* interface

- **status**: completed
- **priority**: P1
- **owner**: worker-root/dhcp-20261016-0508-dhcp-all-ethernet
- **createdAt**: 2026-10-16 05:08

## Description

Every interface whose name starts with `eth` acquires an address by DHCP
automatically, including interfaces that appear after boot. SSH (dropbear)
starts automatically regardless of link state. Acceptance: QEMU boot with two
NICs gets DHCP leases on eth0 and eth1 without configuration; boot without NICs
starts dropbear without errors.

## ActiveForm

Switching Ethernet DHCP to a dhcpcd manager covering eth*.

## Dependencies

- **blocked by**: (none)
- **blocks**: (none)

## Notes

- Full tier: network overlay, runlevels, archive/boot tests, README.

- complete: amd64 verify and QEMU smoke pass; arm not boot-tested
