#!/usr/bin/env bash
# Phase 7: Validate the full stack
set -euo pipefail

PASS=0
FAIL=0

check() {
  local label="$1"
  local cmd="$2"
  local expected="$3"

  result=$(eval "${cmd}" 2>&1)
  if echo "${result}" | grep -q "${expected}"; then
    echo "  ✓ ${label}"
    ((PASS++)) || true
  else
    echo "  ✗ ${label}"
    echo "    Expected to find: '${expected}'"
    echo "    Got: ${result:0:200}"
    ((FAIL++)) || true
  fi
}

echo "━━━ Kubernetes cluster ━━━"
check "Nodes are Ready" \
  "kubectl get nodes --no-headers" \
  "Ready"

echo ""
echo "━━━ OTel Demo pods ━━━"
check "All otel-demo pods Running" \
  "kubectl get pods -n otel-demo --no-headers | grep -v Running | wc -l | tr -d ' '" \
  "^0$"

echo ""
echo "━━━ OTel Collector logs ━━━"
COLLECTOR_POD=$(kubectl get pods -n otel-demo -l app.kubernetes.io/component=otelcol --no-headers -o custom-columns=NAME:.metadata.name 2>/dev/null | head -1)
if [[ -n "${COLLECTOR_POD}" ]]; then
  LOGS=$(kubectl logs -n otel-demo "${COLLECTOR_POD}" --tail=50 2>&1)
  if echo "${LOGS}" | grep -qi "error\|failed"; then
    echo "  ✗ Collector has errors — check with:"
    echo "    kubectl logs -n otel-demo ${COLLECTOR_POD} --tail=100"
    ((FAIL++)) || true
  else
    echo "  ✓ Collector logs look clean"
    ((PASS++)) || true
  fi
  # Check for successful export
  if echo "${LOGS}" | grep -qi "otlphttp/grafana\|Exporting\|export"; then
    echo "  ✓ Collector is exporting data"
    ((PASS++)) || true
  fi
else
  echo "  ! Could not find collector pod — is the demo deployed?"
  ((FAIL++)) || true
fi

echo ""
echo "━━━ Grafana Kubernetes Monitoring pods ━━━"
check "k8s-monitoring pods Running" \
  "kubectl get pods -n monitoring --no-headers | grep Running | wc -l | tr -d ' '" \
  "[1-9]"

echo ""
echo "━━━ Alloy logs (k8s-monitoring) ━━━"
ALLOY_POD=$(kubectl get pods -n monitoring -l app.kubernetes.io/name=alloy-metrics --no-headers -o custom-columns=NAME:.metadata.name 2>/dev/null | head -1)
if [[ -n "${ALLOY_POD}" ]]; then
  ALLOY_LOGS=$(kubectl logs -n monitoring "${ALLOY_POD}" --tail=30 2>&1)
  if echo "${ALLOY_LOGS}" | grep -qi "error"; then
    echo "  ! Alloy has log entries with 'error' — check with:"
    echo "    kubectl logs -n monitoring ${ALLOY_POD} --tail=100"
  else
    echo "  ✓ Alloy logs look clean"
    ((PASS++)) || true
  fi
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Results: ${PASS} passed, ${FAIL} failed"
if [[ "${FAIL}" -eq 0 ]]; then
  echo "All checks passed. Open Grafana Cloud to verify data."
else
  echo "Some checks failed. See output above and Phase 8 troubleshooting guide."
fi
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

echo ""
echo "Useful commands:"
echo "  # Watch collector export activity:"
echo "  kubectl logs -n otel-demo -l app.kubernetes.io/component=otelcol -f"
echo ""
echo "  # Port-forward the OTel Demo frontend:"
echo "  kubectl port-forward -n otel-demo svc/otel-demo-frontendproxy 8080:8080"
echo "  Then open: http://localhost:8080"
