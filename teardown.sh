#!/usr/bin/env bash
# Deletes the OTel Lab VM and all associated GCP resources.
# Run this when you're done demoing to stop all charges.
set -euo pipefail
"$(dirname "$0")/run.sh" --teardown
