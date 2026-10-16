#!/bin/sh
set -eu

test "$(ifquery --list --auto)" = lo
! ifquery --list | grep -q '^eth'
ifquery wlan0 | grep -Eq '^[[:space:]]+use wifi$'
! ifquery wlan0 | grep -Eq '^[[:space:]]+use dhcp$'
ifquery wlan0 | grep -Eq '^[[:space:]]+wifi-config-path /etc/wpa_supplicant/wpa_supplicant.conf$'
test -x /sbin/wpa_supplicant
test -x /usr/libexec/ifupdown-ng/wifi
test -L /etc/runlevels/boot/dhcpcd
for level in sysinit boot default; do
    test ! -e "/etc/runlevels/$level/wpa_supplicant"
done
grep -qx 'allowinterfaces eth\* en\* wlan\*' /etc/dhcpcd.conf
! grep -qx background /etc/dhcpcd.conf
echo 'PASS: dhcpcd manages eth*, en*, and wlan*; ifupdown authenticates Wi-Fi'
