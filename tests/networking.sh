#!/bin/sh
set -eu

automatic=$(ifquery --list --auto)
test "$(printf '%s\n' "$automatic" | sort)" = "$(printf 'eth0\nlo')"
for iface in eth0 eth1 wlan0; do
    ifquery "$iface" | grep -Eq '^[[:space:]]+use dhcp$'
    # Exercise the installed executor without starting a real DHCP client.
    command=$(MOCK=echo PHASE=up IFACE="$iface" /usr/libexec/ifupdown-ng/dhcp)
    test "$command" = "/sbin/dhcpcd $iface"
    command=$(MOCK=echo PHASE=down IFACE="$iface" /usr/libexec/ifupdown-ng/dhcp)
    test "$command" = "/sbin/dhcpcd -k $iface"
done
ifquery wlan0 | grep -Eq '^[[:space:]]+use wifi$'
ifquery wlan0 | grep -Eq '^[[:space:]]+wifi-config-path /etc/wpa_supplicant/wpa_supplicant.conf$'
test -x /sbin/wpa_supplicant
test -x /usr/libexec/ifupdown-ng/wifi
for level in sysinit boot default; do
    test ! -e "/etc/runlevels/$level/dhcpcd"
    test ! -e "/etc/runlevels/$level/wpa_supplicant"
done
grep -qx background /etc/dhcpcd.conf
! grep -q '^denyinterfaces ' /etc/dhcpcd.conf
echo 'PASS: interfaces parser, per-interface DHCP start/stop, and Wi-Fi executor configuration'
