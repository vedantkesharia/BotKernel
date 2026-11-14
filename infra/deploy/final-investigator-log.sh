set -euo pipefail
cd /opt/botkernel
docker compose --env-file runtime.env -f compose.aws-demo.yaml logs --since 15m --no-color api 2>&1 | grep -E 'invalid_model|validation|51922|bedrock|investigation' | tail -20