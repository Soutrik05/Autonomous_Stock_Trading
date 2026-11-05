#!/bin/bash
# First-boot setup for Amazon Linux 2023: Docker + compose, persistent data disk, swap.
set -euxo pipefail

dnf install -y docker
systemctl enable --now docker
mkdir -p /usr/local/lib/docker/cli-plugins
curl -fsSL "https://github.com/docker/compose/releases/download/v2.29.7/docker-compose-linux-x86_64" \
  -o /usr/local/lib/docker/cli-plugins/docker-compose
chmod +x /usr/local/lib/docker/cli-plugins/docker-compose

# Data volume (EBS attaches as /dev/sdf, appears as nvme1n1 on Nitro instances). Format only if blank.
for i in $(seq 1 30); do
  DEV=$(lsblk -dpno NAME,SERIAL | awk '/vol/ && $1 !~ /nvme0/ {print $1; exit}'); [ -n "${DEV:-}" ] && break; sleep 5
done
if [ -n "${DEV:-}" ]; then
  blkid "$DEV" || mkfs.xfs "$DEV"
  mkdir -p /mnt/data
  UUID=$(blkid -s UUID -o value "$DEV")
  grep -q "$UUID" /etc/fstab || echo "UUID=$UUID /mnt/data xfs defaults,nofail 0 2" >> /etc/fstab
  mount -a
fi
mkdir -p /mnt/data/storage /mnt/data/backups /opt/stockminds
ln -sfn /mnt/data/storage /opt/stockminds/storage
ln -sfn /mnt/data/backups /opt/stockminds/backups
chown -R 1000:1000 /mnt/data/storage /mnt/data/backups   # container user "app" is uid 1000

# 2 GB swap: FinBERT load spikes memory
if [ ! -f /swapfile ]; then
  dd if=/dev/zero of=/swapfile bs=1M count=2048 && chmod 600 /swapfile && mkswap /swapfile
  echo "/swapfile none swap sw 0 0" >> /etc/fstab
fi
swapon -a
