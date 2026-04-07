#!/usr/bin/env bash
# Phase 2: Create the GKE cluster
# Run this once. Takes ~5 minutes.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="${SCRIPT_DIR}/../setup.env"

if [[ ! -f "${ENV_FILE}" ]]; then
  echo "ERROR: setup.env not found."
  echo "  cp ${SCRIPT_DIR}/../setup.env.example ${SCRIPT_DIR}/../setup.env"
  echo "  Then fill in your values."
  exit 1
fi
# shellcheck disable=SC1090
source "${ENV_FILE}"

: "${GCP_PROJECT_ID:?Set GCP_PROJECT_ID in setup.env}"

CLUSTER_NAME="otel-lab"
ZONE="us-central1-a"

echo "━━━ Step 1: Verify gcloud auth ━━━"
ACTIVE_ACCOUNT=$(gcloud auth list --filter=status:ACTIVE --format="value(account)" 2>/dev/null | head -1)
if [[ -z "${ACTIVE_ACCOUNT}" ]]; then
  echo "ERROR: No active gcloud account. Run: gcloud auth login"
  exit 1
fi
echo "  Authenticated as: ${ACTIVE_ACCOUNT}"

echo "━━━ Step 2: Set project ━━━"
gcloud config set project "${GCP_PROJECT_ID}"

echo "━━━ Step 3: Enable required APIs ━━━"
gcloud services enable \
  container.googleapis.com \
  compute.googleapis.com \
  --project="${GCP_PROJECT_ID}"
echo "  APIs enabled."

echo "━━━ Step 4: Create GKE cluster ━━━"
echo "  Cluster: ${CLUSTER_NAME}, Zone: ${ZONE}, Nodes: 3x e2-standard-2"
echo "  This will take ~5 minutes..."

gcloud container clusters create "${CLUSTER_NAME}" \
  --project="${GCP_PROJECT_ID}" \
  --zone="${ZONE}" \
  --machine-type=e2-standard-2 \
  --num-nodes=3 \
  --disk-size=50 \
  --disk-type=pd-standard \
  --release-channel=regular \
  --no-enable-basic-auth \
  --logging=SYSTEM,WORKLOAD \
  --monitoring=SYSTEM

echo "━━━ Step 5: Fetch cluster credentials ━━━"
gcloud container clusters get-credentials "${CLUSTER_NAME}" \
  --zone="${ZONE}" \
  --project="${GCP_PROJECT_ID}"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "SUCCESS: GKE cluster '${CLUSTER_NAME}' is ready."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
kubectl get nodes
