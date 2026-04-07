#!/usr/bin/env bash
# Phase 6: Install Grafana Kubernetes Monitoring
# Reads setup.env, renders the values template, then runs helm install.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="${SCRIPT_DIR}/../setup.env"
TEMPLATE="${SCRIPT_DIR}/../k8s-monitoring/values-template.yaml"
RENDERED="${SCRIPT_DIR}/../k8s-monitoring/values-rendered.yaml"

if [[ ! -f "${ENV_FILE}" ]]; then
  echo "ERROR: setup.env not found."
  exit 1
fi

# Check envsubst is available
if ! command -v envsubst &>/dev/null; then
  echo "ERROR: envsubst not found. Install with: brew install gettext && brew link gettext --force"
  exit 1
fi

# shellcheck disable=SC1090
source "${ENV_FILE}"

: "${GRAFANA_METRICS_HOST:?Set GRAFANA_METRICS_HOST in setup.env}"
: "${GRAFANA_METRICS_USERNAME:?Set GRAFANA_METRICS_USERNAME in setup.env}"
: "${GRAFANA_LOGS_HOST:?Set GRAFANA_LOGS_HOST in setup.env}"
: "${GRAFANA_LOGS_USERNAME:?Set GRAFANA_LOGS_USERNAME in setup.env}"
: "${GRAFANA_API_TOKEN:?Set GRAFANA_API_TOKEN in setup.env}"

echo "━━━ Step 1: Render values template ━━━"
# Export vars so envsubst can see them
export GRAFANA_METRICS_HOST GRAFANA_METRICS_USERNAME \
       GRAFANA_LOGS_HOST GRAFANA_LOGS_USERNAME GRAFANA_API_TOKEN

envsubst < "${TEMPLATE}" > "${RENDERED}"
echo "  Rendered: ${RENDERED}"
echo "  NOTE: This file contains secrets — it is git-ignored."

echo "━━━ Step 2: Install Grafana Kubernetes Monitoring ━━━"
helm upgrade --install k8s-monitoring grafana/k8s-monitoring \
  --namespace monitoring \
  --create-namespace \
  --values "${RENDERED}" \
  --timeout 10m \
  --wait

# Remove the rendered file so secrets don't linger on disk
rm -f "${RENDERED}"
echo "  Cleaned up rendered values (secrets removed from disk)."

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "SUCCESS: Grafana Kubernetes Monitoring installed."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
kubectl get pods -n monitoring
