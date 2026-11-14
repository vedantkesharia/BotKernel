set -euo pipefail
cd /opt/botkernel
free -m
stat -c '%a %n' /etc/botkernel/secrets /etc/botkernel/secrets/metrics_token
test -f compose.metrics-access.yaml
docker compose --env-file runtime.env -f compose.aws-demo.yaml -f compose.metrics-access.yaml --profile observability up -d --no-deps jaeger otel-collector prometheus grafana
free -m