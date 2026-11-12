#!/usr/bin/env bash
set -euo pipefail

env_file="${BOTKERNEL_RUNTIME_ENV_FILE:-/opt/botkernel/runtime.env}"
compose_file="${BOTKERNEL_COMPOSE_FILE:-/opt/botkernel/compose.aws-demo.yaml}"

if [[ "${BOTKERNEL_DEPLOY_APPROVED:-false}" != "true" ]]; then
  echo "Set BOTKERNEL_DEPLOY_APPROVED=true only after a separately approved deployment." >&2
  exit 1
fi
if [[ ! -r "$env_file" || ! -r "$compose_file" ]]; then
  echo "Runtime env and deployment Compose files must exist and be readable." >&2
  exit 1
fi

read_setting() {
  local key="$1"
  local count line
  count="$(grep -c "^${key}=" "$env_file" || true)"
  if [[ "$count" != "1" ]]; then
    echo "Expected exactly one ${key} setting in runtime env." >&2
    exit 1
  fi
  line="$(grep -m1 "^${key}=" "$env_file")"
  printf '%s' "${line#*=}"
}

require_setting() {
  local key="$1"
  local expected="$2"
  local actual
  actual="$(read_setting "$key")"
  if [[ "$actual" != "$expected" ]]; then
    echo "Unsafe or missing required setting: ${key}=${expected}" >&2
    exit 1
  fi
}

require_setting CLOUD_MODE mock
require_setting AWS_DEPLOY_ALLOWED false
require_setting BEDROCK_ENABLED false
require_setting BEDROCK_SPEND_AUTHORIZED false
require_setting AI_ACTION_EXECUTION_ENABLED false

aws_region="$(read_setting AWS_REGION)"
registry="$(read_setting BOTKERNEL_ECR_REGISTRY)"
if [[ ! "$aws_region" =~ ^[a-z]{2}(-gov)?-[a-z]+-[0-9]+$ ]]; then
  echo "AWS_REGION is not a valid region identifier." >&2
  exit 1
fi
if [[ ! "$registry" =~ ^[0-9]{12}\.dkr\.ecr\.[a-z0-9-]+\.amazonaws\.com(\.cn)?$ ]]; then
  echo "BOTKERNEL_ECR_REGISTRY is not a valid ECR registry hostname." >&2
  exit 1
fi

docker compose --env-file "$env_file" -f "$compose_file" config --quiet

aws ecr get-login-password --region "$aws_region" |
  docker login --username AWS --password-stdin "$registry"
docker compose --env-file "$env_file" -f "$compose_file" pull
docker compose --env-file "$env_file" -f "$compose_file" up -d
