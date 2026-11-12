#!/bin/bash
set -euo pipefail

dnf install -y docker
systemctl enable --now docker
systemctl enable --now amazon-ssm-agent
install -d -o root -g root -m 0750 /opt/botkernel
install -d -o root -g root -m 0700 /etc/botkernel/secrets

