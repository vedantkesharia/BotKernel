#!/usr/bin/env bash
set -euo pipefail

secret_dir="${BOTKERNEL_SECRET_DIR:-/etc/botkernel/secrets}"
password_file="${secret_dir}/postgres_password"
url_file="${secret_dir}/database_url"

if [[ -e "$password_file" || -e "$url_file" ]]; then
  echo "Refusing to overwrite existing BotKernel database secrets." >&2
  exit 1
fi

install -d -o root -g root -m 0700 "$secret_dir"
umask 077
password="$(openssl rand -hex 32)"
printf '%s' "$password" > "$password_file"
printf 'postgresql+psycopg://botkernel:%s@postgres:5432/botkernel' "$password" > "$url_file"
chmod 0600 "$password_file" "$url_file"
unset password
printf 'Created host-only database secrets in %s.\n' "$secret_dir"
