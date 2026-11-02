#!/usr/bin/env bash
# One-time preparation of a fresh Ubuntu 24.04/22.04 LTS (amd64) host for the hosted evaluation.
# Run as a sudo-capable user:  bash deploy/bootstrap-host.sh
set -euo pipefail
. /etc/os-release
[ "$ID" = ubuntu ] || { echo "Ubuntu 22.04/24.04 LTS expected (found $ID $VERSION_ID)"; exit 1; }
[ "$(uname -m)" = x86_64 ] || { echo "amd64 (x86_64) host expected"; exit 1; }
if ! command -v docker >/dev/null; then curl -fsSL https://get.docker.com | sudo sh; fi
sudo usermod -aG docker "$USER" || true
# The browser jail creates unprivileged user/network/PID/mount namespaces inside the container.
# Ubuntu 23.10+ restricts that for unconfined processes; allow it (the container still runs as a
# non-root user with all capabilities dropped).
echo 'kernel.apparmor_restrict_unprivileged_userns=0' | sudo tee /etc/sysctl.d/60-agent-readiness-userns.conf >/dev/null
echo 'user.max_user_namespaces=15000' | sudo tee -a /etc/sysctl.d/60-agent-readiness-userns.conf >/dev/null
sudo sysctl --system >/dev/null
# Firewall: SSH + HTTP(S) only (Caddy needs 80 for the certificate challenge).
if command -v ufw >/dev/null; then sudo ufw allow OpenSSH >/dev/null; sudo ufw allow 80/tcp >/dev/null; sudo ufw allow 443/tcp >/dev/null; sudo ufw --force enable >/dev/null; fi
sudo mkdir -p /srv/agent-readiness
unshare -Urn true && echo "user+net namespaces: OK" || echo "user+net namespaces: BLOCKED (check sysctl output above)"
echo "Done. Log out and back in (docker group), then continue with deploy/DEPLOY.md step 3."
