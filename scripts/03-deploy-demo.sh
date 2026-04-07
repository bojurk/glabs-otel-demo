#!/usr/bin/env bash
# Phase 4 + 5: Deploy the OpenTelemetry Demo with Grafana Cloud export
# The collector config and secret are already embedded in otel-demo/values.yaml
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VALUES="${SCRIPT_DIR}/../otel-demo/values.yaml"

echo "━━━ Deploy OpenTelemetry Demo ━━━"
echo "  This installs ~20 microservices. First pull takes 3-5 minutes."

helm upgrade --install otel-demo open-telemetry/opentelemetry-demo \
  --namespace otel-demo \
  --create-namespace \
  --values "${VALUES}" \
  --timeout 10m \
  --wait

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "SUCCESS: OTel Demo deployed."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
kubectl get pods -n otel-demo
