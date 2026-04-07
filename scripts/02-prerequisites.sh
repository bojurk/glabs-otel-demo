#!/usr/bin/env bash
# Phase 3: Install Helm repos, create namespaces, create Kubernetes secrets
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="${SCRIPT_DIR}/../setup.env"

if [[ ! -f "${ENV_FILE}" ]]; then
  echo "ERROR: setup.env not found. See setup.env.example."
  exit 1
fi
# shellcheck disable=SC1090
source "${ENV_FILE}"

# ── Validate required vars ─────────────────────────────────────────────────
: "${GRAFANA_INSTANCE_ID:?Set GRAFANA_INSTANCE_ID in setup.env}"
: "${GRAFANA_API_TOKEN:?Set GRAFANA_API_TOKEN in setup.env}"
: "${GRAFANA_METRICS_HOST:?Set GRAFANA_METRICS_HOST in setup.env}"
: "${GRAFANA_METRICS_USERNAME:?Set GRAFANA_METRICS_USERNAME in setup.env}"
: "${GRAFANA_LOGS_HOST:?Set GRAFANA_LOGS_HOST in setup.env}"
: "${GRAFANA_LOGS_USERNAME:?Set GRAFANA_LOGS_USERNAME in setup.env}"

echo "━━━ Step 1: Check required tools ━━━"
check_tool() {
  if ! command -v "$1" &>/dev/null; then
    echo "  ERROR: '$1' not found. Please install it."
    exit 1
  fi
  echo "  ✓ $1"
}
check_tool gcloud
check_tool kubectl
check_tool helm

echo "━━━ Step 2: Add Helm repositories ━━━"
helm repo add open-telemetry https://open-telemetry.github.io/opentelemetry-helm-charts
helm repo add grafana https://grafana.github.io/helm-charts
helm repo update
echo "  Helm repos ready."

echo "━━━ Step 3: Create namespaces ━━━"
kubectl create namespace otel-demo --dry-run=client -o yaml | kubectl apply -f -
kubectl create namespace monitoring --dry-run=client -o yaml | kubectl apply -f -
echo "  Namespaces: otel-demo, monitoring"

echo "━━━ Step 4: Create Kubernetes secrets ━━━"

# Secret for the OTel Demo collector (used in otel-demo namespace)
kubectl create secret generic grafana-credentials \
  --namespace=otel-demo \
  --from-literal=GRAFANA_INSTANCE_ID="${GRAFANA_INSTANCE_ID}" \
  --from-literal=GRAFANA_API_TOKEN="${GRAFANA_API_TOKEN}" \
  --dry-run=client -o yaml | kubectl apply -f -
echo "  ✓ grafana-credentials (otel-demo)"

# Secret for Grafana Kubernetes Monitoring (used in monitoring namespace)
kubectl create secret generic grafana-cloud-credentials \
  --namespace=monitoring \
  --from-literal=prometheus-host="${GRAFANA_METRICS_HOST}" \
  --from-literal=prometheus-username="${GRAFANA_METRICS_USERNAME}" \
  --from-literal=prometheus-password="${GRAFANA_API_TOKEN}" \
  --from-literal=loki-host="${GRAFANA_LOGS_HOST}" \
  --from-literal=loki-username="${GRAFANA_LOGS_USERNAME}" \
  --from-literal=loki-password="${GRAFANA_API_TOKEN}" \
  --dry-run=client -o yaml | kubectl apply -f -
echo "  ✓ grafana-cloud-credentials (monitoring)"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "SUCCESS: Prerequisites complete."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
kubectl get namespaces | grep -E "otel-demo|monitoring"
