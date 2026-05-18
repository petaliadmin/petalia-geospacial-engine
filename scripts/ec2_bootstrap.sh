#!/usr/bin/env bash
# Run ONCE on a fresh EC2 instance (Amazon Linux 2023 or Ubuntu 22.04)
# Usage: sudo bash ec2_bootstrap.sh
set -euo pipefail

echo "==> Installing Docker"
if command -v apt-get &>/dev/null; then
  apt-get update -y
  apt-get install -y ca-certificates curl gnupg
  install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
    https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
    > /etc/apt/sources.list.d/docker.list
  apt-get update -y
  apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
else
  # Amazon Linux 2023
  dnf install -y docker
  systemctl enable --now docker
  dnf install -y docker-compose-plugin
fi

echo "==> Adding ec2-user to docker group"
usermod -aG docker ec2-user 2>/dev/null || usermod -aG docker ubuntu 2>/dev/null || true
systemctl enable --now docker

echo "==> Creating project directory"
mkdir -p /opt/petalia/secrets
chmod 700 /opt/petalia/secrets

echo ""
echo "Bootstrap complete. Next manual steps:"
echo "  1. Copy .env.production     → /opt/petalia/.env.production"
echo "  2. Copy gee_service_account.json → /opt/petalia/secrets/gee_service_account.json"
echo "  3. Copy docker-compose.prod.yml + docker/prometheus.yml → /opt/petalia/"
echo "  4. Set DOCKERHUB_USERNAME, IMAGE_TAG, and run:"
echo "       cd /opt/petalia && docker compose -f docker-compose.prod.yml pull"
echo "       docker compose -f docker-compose.prod.yml up -d"
