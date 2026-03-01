#!/usr/bin/env bash
# =============================================================================
# CI Adapter — Jenkins (stub implementation)
# =============================================================================
#
# Provides a provider-agnostic interface to CI systems.
# The pr_to_cicd pipeline calls this script instead of hitting Jenkins directly.
#
# USAGE:
#   ci-adapter.sh trigger <commit_sha>   → prints BUILD_ID
#   ci-adapter.sh status  <build_id>     → prints RUNNING|SUCCESS|FAILURE|ABORTED
#   ci-adapter.sh logs    <build_id>     → prints console log
#
# CONFIGURATION:
#   Reads from .github/project.json → ci block
#   Auth from environment variable named in project.json → ci.auth_env
#
# MODES:
#   1. MCP mode  — if MCP tools are available (detected via mcp_servers config)
#   2. curl mode — direct Jenkins REST API calls
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
    # Fallback: grep-based extraction (fragile, prefer jq)
    grep -oP "(?<=\"${key#.}\":\s\")[^\"]*" "$PROJECT_JSON" 2>/dev/null || echo ""
  fi
}

detect_mode() {
  # Check if MCP servers are configured
  local mcp_config
  mcp_config=$(read_config '.mcp_servers.jenkins')
  if [[ -n "$mcp_config" ]]; then
    echo "mcp"
    return
  fi

  # Check if CI URL is configured (curl mode)
  local ci_url
  ci_url=$(read_config '.ci.job_url')
  if [[ -n "$ci_url" ]]; then
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
  local commit_sha="$1"
  local build_id="STUB-BUILD-$(date +%s)"
  echo "$build_id"
}

stub_status() {
  local build_id="$1"
  # Stub always returns SUCCESS
  echo "SUCCESS"
}

stub_logs() {
  local build_id="$1"
  cat <<EOF
=== CI Build Log (STUB MODE) ===
Build ID: $build_id
Mode: stub (no Jenkins configured)
Timestamp: $(date -u +"%Y-%m-%dT%H:%M:%SZ")

[INFO] Building project...
[INFO] Running tests...
[INFO] ✓ backend: 55 tests passed
[INFO] ✓ frontend: 19 tests passed
[INFO] ✓ lint: no issues
[INFO] ✓ typecheck: no errors
[INFO] Build completed successfully.

RESULT: SUCCESS
=== End of Build Log ===
EOF
}

# ---------------------------------------------------------------------------
# Curl implementations (Jenkins REST API)
# ---------------------------------------------------------------------------

curl_trigger() {
  local commit_sha="$1"
  local job_url
  job_url=$(read_config '.ci.job_url')
  local auth_env
  auth_env=$(read_config '.ci.auth_env')

  [[ -z "$job_url" ]] && die "ci.job_url not configured in project.json"

  local auth_header=""
  if [[ -n "$auth_env" ]] && [[ -n "${!auth_env:-}" ]]; then
    auth_header="-H \"Authorization: Bearer ${!auth_env}\""
  fi

  # Trigger Jenkins build with commit parameter
  local response
  response=$(eval curl -s -X POST \
    "$job_url/buildWithParameters?COMMIT_SHA=$commit_sha" \
    "$auth_header" \
    -D /tmp/ci-adapter-headers.txt \
    -o /tmp/ci-adapter-response.txt \
    -w '%{http_code}')

  if [[ "$response" -ge 200 && "$response" -lt 300 ]]; then
    # Extract queue item URL from Location header
    local queue_url
    queue_url=$(grep -i 'Location:' /tmp/ci-adapter-headers.txt | tr -d '\r' | awk '{print $2}')
    # Poll queue until build starts and we get a build number
    for i in $(seq 1 10); do
      sleep 2
      local queue_info
      queue_info=$(curl -s "${queue_url}api/json" ${auth_header:+"$auth_header"})
      local build_number
      build_number=$(echo "$queue_info" | jq -r '.executable.number // empty' 2>/dev/null)
      if [[ -n "$build_number" ]]; then
        echo "$build_number"
        return 0
      fi
    done
    die "Timed out waiting for build to start from queue"
  else
    die "Jenkins trigger failed with HTTP $response"
  fi
}

curl_status() {
  local build_id="$1"
  local job_url
  job_url=$(read_config '.ci.job_url')
  local auth_env
  auth_env=$(read_config '.ci.auth_env')

  local auth_header=""
  if [[ -n "$auth_env" ]] && [[ -n "${!auth_env:-}" ]]; then
    auth_header="-H \"Authorization: Bearer ${!auth_env}\""
  fi

  local response
  response=$(eval curl -s "$job_url/$build_id/api/json" "$auth_header")

  local building result
  building=$(echo "$response" | jq -r '.building' 2>/dev/null)
  result=$(echo "$response" | jq -r '.result // empty' 2>/dev/null)

  if [[ "$building" == "true" ]]; then
    echo "RUNNING"
  elif [[ "$result" == "SUCCESS" ]]; then
    echo "SUCCESS"
  elif [[ "$result" == "FAILURE" ]]; then
    echo "FAILURE"
  elif [[ "$result" == "ABORTED" ]]; then
    echo "ABORTED"
  else
    echo "RUNNING"  # Unknown state, assume still running
  fi
}

curl_logs() {
  local build_id="$1"
  local job_url
  job_url=$(read_config '.ci.job_url')
  local auth_env
  auth_env=$(read_config '.ci.auth_env')

  local auth_header=""
  if [[ -n "$auth_env" ]] && [[ -n "${!auth_env:-}" ]]; then
    auth_header="-H \"Authorization: Bearer ${!auth_env}\""
  fi

  eval curl -s "$job_url/$build_id/consoleText" "$auth_header"
}

# ---------------------------------------------------------------------------
# MCP implementations (placeholder — activated when MCP tools are available)
# ---------------------------------------------------------------------------

mcp_trigger() {
  # MCP integration would call the Jenkins MCP tool here.
  # For now, fall back to curl.
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
      local commit_sha="${1:-}"
      [[ -z "$commit_sha" ]] && die "Usage: ci-adapter.sh trigger <commit_sha>"
      "${mode}_trigger" "$commit_sha"
      ;;
    status)
      local build_id="${1:-}"
      [[ -z "$build_id" ]] && die "Usage: ci-adapter.sh status <build_id>"
      "${mode}_status" "$build_id"
      ;;
    logs)
      local build_id="${1:-}"
      [[ -z "$build_id" ]] && die "Usage: ci-adapter.sh logs <build_id>"
      "${mode}_logs" "$build_id"
      ;;
    *)
      cat <<USAGE
CI Adapter — provider-agnostic CI interface

USAGE:
  ci-adapter.sh trigger <commit_sha>   Trigger a CI build
  ci-adapter.sh status  <build_id>     Check build status
  ci-adapter.sh logs    <build_id>     Fetch build console log

MODES:
  stub  — Mock responses for dry-run testing (default)
  curl  — Jenkins REST API (when ci.job_url is configured)
  mcp   — MCP tool integration (when mcp_servers.jenkins is configured)

Current mode: $(detect_mode)
USAGE
      exit 1
      ;;
  esac
}

main "$@"
