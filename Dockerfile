# syntax=docker/dockerfile:1@sha256:ecfaec9ed6d810b56388c508f4121597bfbba70d41a6dfeee4d8cad5f295fc32
# check=skip=InvalidDefaultArgInFrom
ARG ALPINE_IMAGE
FROM ${ALPINE_IMAGE} AS rootfs
COPY packages.txt /tmp/packages.txt
RUN xargs apk add --no-cache < /tmp/packages.txt && rm /tmp/packages.txt
COPY rootfs/ /
ARG TARGETPLATFORM
RUN echo 'root:root' | chpasswd && \
    adduser -D -s /bin/ash alpine && echo 'alpine:alpine' | chpasswd && \
    addgroup -S klogd && adduser -S -D -H -G klogd -s /sbin/nologin klogd && \
    adduser alpine wheel && \
    chmod 0600 /etc/wpa_supplicant/wpa_supplicant.conf && \
    chmod 0755 /usr/local/sbin/console-getty && \
    for service in devfs dmesg mdev hwdrivers; do rc-update add "$service" sysinit; done && \
    for service in modules sysctl hostname bootmisc swclock syslog klogd \
                   networking machine-id seedrng; do rc-update add "$service" boot; done && \
    for service in ntpd crond dropbear local; do rc-update add "$service" default; done && \
    for service in killprocs mount-ro savecache; do rc-update add "$service" shutdown; done && \
    mkdir -p /etc/network/interfaces.d /usr/share/mica-alpine /lib/modules /lib/firmware && \
    printf '%s\n' "$TARGETPLATFORM" > /usr/share/mica-alpine/platform && \
    apk --print-arch > /usr/share/mica-alpine/apk-arch && \
    apk info -v | sort > /usr/share/mica-alpine/packages.txt && \
    test -x /sbin/init && test -x /sbin/openrc && test -x /sbin/dhcpcd && \
    sh -n /usr/local/sbin/console-getty
COPY tests/networking.sh /tmp/networking-test.sh
RUN sh /tmp/networking-test.sh && rm /tmp/networking-test.sh

FROM --platform=$BUILDPLATFORM ${ALPINE_IMAGE} AS pack
SHELL ["/bin/ash", "-eo", "pipefail", "-c"]
RUN apk add --no-cache tar gzip python3
COPY --from=rootfs / /rootfs/
COPY scripts/verify-archive.py /verify-archive.py
ARG TARGETPLATFORM
RUN rm -f /rootfs/etc/machine-id \
          /rootfs/etc/dropbear/dropbear_* \
          /rootfs/var/lib/misc/random-seed /rootfs/var/lib/seedrng/seed && \
    printf '127.0.0.1 localhost mica-alpine\n::1 localhost mica-alpine\n' > /rootfs/etc/hosts && \
    printf '# Populated by DHCP after boot.\n' > /rootfs/etc/resolv.conf && \
    mkdir -p /out && \
    tar --sort=name --numeric-owner --xattrs --acls -C /rootfs -cf - . | gzip -n > /out/rootfs.tar.gz && \
    cd /out && sha256sum rootfs.tar.gz > rootfs.tar.gz.sha256 && \
    python3 /verify-archive.py /out/rootfs.tar.gz "$TARGETPLATFORM"

FROM scratch AS artifact
COPY --from=pack /out/ /

# Test-only kernel and matching modules; none enter the delivered archive.
FROM rootfs AS test-kernel
RUN apk add --no-cache linux-virt && \
    mkdir /fixture && cp /boot/vmlinuz-virt /fixture/kernel && \
    cp /boot/initramfs-virt /fixture/initramfs && \
    tar -C / -czf /fixture/modules.tar.gz lib/modules
FROM scratch AS fixture
COPY --from=test-kernel /fixture/ /

FROM --platform=$BUILDPLATFORM ${ALPINE_IMAGE} AS test-tools
RUN apk add --no-cache bash python3 tar gzip e2fsprogs \
    qemu-system-x86_64 qemu-system-aarch64 openssh-client sshpass
COPY scripts/verify-archive.py /usr/local/bin/verify-archive.py
COPY tests/boot.py /usr/local/bin/boot.py
