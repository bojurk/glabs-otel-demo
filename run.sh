#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# OTel Lab — bootstrap entry point
#
# SEs pull this repo and run: ./run.sh
# That's it. The wizard handles everything else.
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="${SCRIPT_DIR}/.venv"

# ── Require Python 3.8+ ───────────────────────────────────────────────────────
if ! command -v python3 &>/dev/null; then
  echo "ERROR: python3 not found."
  echo "  Mac:   brew install python"
  echo "  Other: https://www.python.org/downloads/"
  exit 1
fi

PY_MINOR=$(python3 -c "import sys; print(sys.version_info.minor)")
PY_MAJOR=$(python3 -c "import sys; print(sys.version_info.major)")
if [[ "${PY_MAJOR}" -lt 3 ]] || [[ "${PY_MAJOR}" -eq 3 && "${PY_MINOR}" -lt 8 ]]; then
  echo "ERROR: Python 3.8+ required (found 3.${PY_MINOR})."
  exit 1
fi

# ── Create virtual environment (once) ────────────────────────────────────────
if [[ ! -d "${VENV_DIR}" ]]; then
  echo "Creating Python virtual environment..."
  python3 -m venv "${VENV_DIR}"
fi

# ── Activate and install deps ─────────────────────────────────────────────────
# shellcheck disable=SC1091
source "${VENV_DIR}/bin/activate"
pip install --quiet --upgrade pip
pip install --quiet -r "${SCRIPT_DIR}/requirements.txt"

# ── Cache GCP SSH key so the wizard never prompts for a passphrase ───────────
GCP_KEY="${HOME}/.ssh/google_compute_engine"
if [[ -f "${GCP_KEY}" ]]; then
  ssh-add "${GCP_KEY}" 2>/dev/null || true
fi

# ── Run wizard, forwarding all arguments ─────────────────────────────────────
python3 "${SCRIPT_DIR}/setup.py" "$@"
