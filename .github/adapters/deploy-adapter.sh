#!/usr/bin/env bash
# =============================================================================
# Deploy Adapter — Spinnaker (stub implementation)
# =============================================================================
#
# Provides a provider-agnostic interface to deployment systems.
# The pr_to_cicd pipeline calls this script instead of hitting Spinnaker directly.
#
# USAGE:
#   deploy-adapter.sh trigger  <build_id> [env]   → prints EXECUTION_ID
#   deploy-adapter.sh status   <execution_id>     → prints RUNNING|SUCCEEDED|FAILED|CANCELED
#   deploy-adapter.sh logs     <execution_id>     → prints execution log
#   deploy-adapter.sh rollback <execution_id>     → prints ROLLBACK_EXECUTION_ID
#
# CONFIGURATION:
#   Reads from .github/project.json → deploy block
#   Auth from environment variable named in project.json → deploy.auth_env
#
# MODES:
#   1. MCP mode  — if MCP tools are available (detected via mcp_servers config)
#   2. curl mode — direct Spinnaker REST API calls
#   3. stub mode — returns mock data for dry-run testing (default)
#
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
PROJECT_JSON="$PROJECT_ROOT/.github/project.json"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

die() {
  echo "ERROR: $*" >&2
  exit 1
}

read_config() {
  local key="$1"
  if command -v jq &>/dev/null; then
    jq -r "$key // empty" "$PROJECT_JSON" 2>/dev/null || echo ""
  else
    grep -oP "(?<=\"${key#.}\":\s\")[^\"]*" "$PROJECT_JSON" 2>/dev/null || echo ""
  fi
}

detect_mode() {
  # Check if MCP servers are configured
  local mcp_config
  mcp_config=$(read_config '.mcp_servers.spinnaker')
  if [[ -n "$mcp_config" ]]; then
    echo "mcp"
    return
  fi

  # Check if deploy URL is configured (curl mode)
  local deploy_url
  deploy_url=$(read_config '.deploy.pipeline_url')
  if [[ -n "$deploy_url" ]]; then
    echo "curl"
    return
  fi

  # Default to stub mode
  echo "stub"
}

# ---------------------------------------------------------------------------
# Stub implementations (for dry-run testing)
# ---------------------------------------------------------------------------

stub_trigger() {
  local build_id="$1"
  local env="${2:-production}"
  local exec_id="STUB-EXEC-$(date +%s)"
  echo "$exec_id"
}

stub_status() {
  local execution_id="$1"
  # Stub always returns SUCCEEDED
  echo "SUCCEEDED"
}

stub_logs() {
  local execution_id="$1"
  cat <<EOF
=== Deployment Log (STUB MODE) ===
Execution ID: $execution_id
Mode: stub (no Spinnaker configured)
Timestamp: $(date -u +"%Y-%m-%dT%H:%M:%SZ")

[STAGE] Configuration
  ✓ Loaded pipeline configuration
  ✓ Resolved artefact references

[STAGE] Bake
  ✓ Docker image built: app:latest
  ✓ Image pushed to registry

[STAGE] Deploy
  ✓ Rolling update initiated
  ✓ 3/3 instances healthy
  ✓ Old instances terminated

[STAGE] Verify
  ✓ Health check passed
  ✓ Smoke tests passed

RESULT: SUCCEEDED
=== End of Deployment Log ===
EOF
}

stub_rollback() {
  local execution_id="$1"
  local rollback_id="STUB-ROLLBACK-$(date +%s)"
  echo "$rollback_id"
}

# ---------------------------------------------------------------------------
# Curl implementations (Spinnaker Gate API)
# ---------------------------------------------------------------------------

curl_trigger() {
  local build_id="$1"
  local env="${2:-production}"
  local pipeline_url
  pipeline_url=$(read_config '.deploy.pipeline_url')
  local application
  application=$(read_config '.deploy.application')
  local pipeline_name
  pipeline_name=$(read_config '.deploy.pipeline_name')
  local auth_env
  auth_env=$(read_config '.deploy.auth_env')

  [[ -z "$pipeline_url" ]] && die "deploy.pipeline_url not configured in project.json"
  [[ -z "$application" ]] && die "deploy.application not configured in project.json"
  [[ -z "$pipeline_name" ]] && die "deploy.pipeline_name not configured in project.json"

  local auth_header=""
  if [[ -n "$auth_env" ]] && [[ -n "${!auth_env:-}" ]]; then
    auth_header="-H \"Authorization: Bearer ${!auth_env}\""
  fi

  # Trigger Spinnaker pipeline
  local payload
  payload=$(cat <<PAYLOAD
{
  "type": "manual",
  "parameters": {
    "build_id": "$build_id",
    "environment": "$env"
  }
}
PAYLOAD
  )

  local response
  response=$(eval curl -s -X POST \
    "$pipeline_url/$application/$pipeline_name" \
    -H "Content-Type: application/json" \
    "$auth_header" \
    -d "'$payload'" \
    -w '\n%{http_code}')

  local http_code body
  http_code=$(echo "$response" | tail -1)
  body=$(echo "$response" | sed '$d')

  if [[ "$http_code" -ge 200 && "$http_code" -lt 300 ]]; then
    # Extract execution ID (Spinnaker returns ref in response)
    local exec_ref
    exec_ref=$(echo "$body" | jq -r '.ref // empty' 2>/dev/null)
    if [[ -n "$exec_ref" ]]; then
      # ref is like /pipelines/<id>, extract just the ID
      echo "${exec_ref##*/}"
    else
      die "Could not extract execution ID from Spinnaker response"
    fi
  else
    die "Spinnaker trigger failed with HTTP $http_code: $body"
  fi
}

curl_status() {
  local execution_id="$1"
  local pipeline_url
  pipeline_url=$(read_config '.deploy.pipeline_url')
  local auth_env
  auth_env=$(read_config '.deploy.auth_env')

  local auth_header=""
  if [[ -n "$auth_env" ]] && [[ -n "${!auth_env:-}" ]]; then
    auth_header="-H \"Authorization: Bearer ${!auth_env}\""
  fi

  local response
  response=$(eval curl -s "$pipeline_url/pipelines/$execution_id" "$auth_header")

  local status
  status=$(echo "$response" | jq -r '.status // empty' 2>/dev/null)

  case "$status" in
    RUNNING|NOT_STARTED|PAUSED)
      echo "RUNNING"
      ;;
    SUCCEEDED|TERMINAL)
      # Spinnaker uses TERMINAL for some success states; check if it suceeded
      local result
      result=$(echo "$response" | jq -r '.result // empty' 2>/dev/null)
      if [[ "$status" == "SUCCEEDED" ]] || [[ "$result" == "SUCCEEDED" ]]; then
        echo "SUCCEEDED"
      else
        echo "FAILED"
      fi
      ;;
    CANCELED)
      echo "CANCELED"
      ;;
    *)
      echo "RUNNING"  # Unknown status, assume still running
      ;;
  esac
}

curl_logs() {
  local execution_id="$1"
  local pipeline_url
  pipeline_url=$(read_config '.deploy.pipeline_url')
  local auth_env
  auth_env=$(read_config '.deploy.auth_env')

  local auth_header=""
  if [[ -n "$auth_env" ]] && [[ -n "${!auth_env:-}" ]]; then
    auth_header="-H \"Authorization: Bearer ${!auth_env}\""
  fi

  # Fetch full pipeline execution details
  local response
  response=$(eval curl -s "$pipeline_url/pipelines/$execution_id" "$auth_header")

  # Format execution stages as a readable log
  echo "=== Spinnaker Execution Log ==="
  echo "Execution ID: $execution_id"
  echo "Status: $(echo "$response" | jq -r '.status // "UNKNOWN"')"
  echo ""

  # List each stage with status
  echo "$response" | jq -r '
    .stages[]? |
    "[\(.type // "unknown")] \(.name // "unnamed") — \(.status // "UNKNOWN")"
  ' 2>/dev/null || echo "(could not parse stages)"

  echo ""
  echo "=== End of Execution Log ==="
}

curl_rollback() {
  local execution_id="$1"
  local pipeline_url
  pipeline_url=$(read_config '.deploy.pipeline_url')
  local auth_env
  auth_env=$(read_config '.deploy.auth_env')

  local auth_header=""
  if [[ -n "$auth_env" ]] && [[ -n "${!auth_env:-}" ]]; then
    auth_header="-H \"Authorization: Bearer ${!auth_env}\""
  fi

  # Cancel current execution first
  eval curl -s -X PUT \
    "$pipeline_url/pipelines/$execution_id/cancel" \
    "$auth_header" >/dev/null 2>&1

  # Trigger rollback pipeline (convention: same pipeline with rollback=true)
  local application
  application=$(read_config '.deploy.application')
  local pipeline_name
  pipeline_name=$(read_config '.deploy.pipeline_name')

  local payload
  payload=$(cat <<PAYLOAD
{
  "type": "manual",
  "parameters": {
    "rollback": "true",
    "original_execution": "$execution_id"
  }
}
PAYLOAD
  )

  local response
  response=$(eval curl -s -X POST \
    "$pipeline_url/$application/$pipeline_name" \
    -H "Content-Type: application/json" \
    "$auth_header" \
    -d "'$payload'" \
    -w '\n%{http_code}')

  local http_code body
  http_code=$(echo "$response" | tail -1)
  body=$(echo "$response" | sed '$d')

  if [[ "$http_code" -ge 200 && "$http_code" -lt 300 ]]; then
    local exec_ref
    exec_ref=$(echo "$body" | jq -r '.ref // empty' 2>/dev/null)
    echo "${exec_ref##*/}"
  else
    die "Spinnaker rollback trigger failed with HTTP $http_code: $body"
  fi
}

# ---------------------------------------------------------------------------
# MCP implementations (placeholder)
# ---------------------------------------------------------------------------

mcp_trigger() {
  echo "WARN: MCP mode not yet implemented, falling back to curl" >&2
  curl_trigger "$@"
}

mcp_status() {
  echo "WARN: MCP mode not yet implemented, falling back to curl" >&2
  curl_status "$@"
}

mcp_logs() {
  echo "WARN: MCP mode not yet implemented, falling back to curl" >&2
  curl_logs "$@"
}

mcp_rollback() {
  echo "WARN: MCP mode not yet implemented, falling back to curl" >&2
  curl_rollback "$@"
}

# ---------------------------------------------------------------------------
# Main dispatch
# ---------------------------------------------------------------------------

main() {
  local command="${1:-}"
  shift || true

  [[ -f "$PROJECT_JSON" ]] || die "project.json not found at $PROJECT_JSON"

  local mode
  mode=$(detect_mode)

  case "$command" in
    trigger)
      local build_id="${1:-}"
      local env="${2:-production}"
      [[ -z "$build_id" ]] && die "Usage: deploy-adapter.sh trigger <build_id> [env]"
      "${mode}_trigger" "$build_id" "$env"
      ;;
    status)
      local execution_id="${1:-}"
      [[ -z "$execution_id" ]] && die "Usage: deploy-adapter.sh status <execution_id>"
      "${mode}_status" "$execution_id"
      ;;
    logs)
      local execution_id="${1:-}"
      [[ -z "$execution_id" ]] && die "Usage: deploy-adapter.sh logs <execution_id>"
      "${mode}_logs" "$execution_id"
      ;;
    rollback)
      local execution_id="${1:-}"
      [[ -z "$execution_id" ]] && die "Usage: deploy-adapter.sh rollback <execution_id>"
      "${mode}_rollback" "$execution_id"
      ;;
    *)
      cat <<USAGE
Deploy Adapter — provider-agnostic deployment interface

USAGE:
  deploy-adapter.sh trigger  <build_id> [env]   Trigger deployment
  deploy-adapter.sh status   <execution_id>     Check deployment status
  deploy-adapter.sh logs     <execution_id>     Fetch deployment log
  deploy-adapter.sh rollback <execution_id>     Trigger rollback

MODES:
  stub  — Mock responses for dry-run testing (default)
  curl  — Spinnaker Gate API (when deploy.pipeline_url is configured)
  mcp   — MCP tool integration (when mcp_servers.spinnaker is configured)

Current mode: $(detect_mode)
USAGE
      exit 1
      ;;
  esac
}

main "$@"
