"""
provision.py — all remote provisioning logic for the OTel Lab wizard.

Each public function maps to one wizard phase.  Functions communicate with
the GCP VM exclusively via `gcloud compute ssh` and `gcloud compute scp` so
the SE's machine needs only gcloud installed — no direct SSH key management.
"""

import base64
import json
import os
import shlex
import shutil
import ssl
import subprocess
import tempfile
import textwrap
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Optional

import certifi

from rich.console import Console

# ── Paths ─────────────────────────────────────────────────────────────────────
_REPO_ROOT     = Path(__file__).parent.parent
_MANIFESTS_DIR = _REPO_ROOT / "manifests"

# ── GCP VM defaults ───────────────────────────────────────────────────────────
_MACHINE_TYPE   = "e2-standard-4"   # 4 vCPU / 16 GB — enough for 20+ microservices
_IMAGE_FAMILY   = "ubuntu-2204-lts"
_IMAGE_PROJECT  = "ubuntu-os-cloud"
_DISK_SIZE      = "50GB"
_VM_TAG         = "otel-lab"
_FW_RULE        = "otel-lab-allow-ssh"


# ── Low-level helpers ─────────────────────────────────────────────────────────

def _local(cmd: list, check=True, capture=True) -> subprocess.CompletedProcess:
    """Run a command on the local machine."""
    return subprocess.run(cmd, check=check, capture_output=capture, text=True)


def _remote(config: dict, command: str, env_vars: Optional[dict] = None,
            check=True) -> subprocess.CompletedProcess:
    """
    Execute a shell command on the GCP VM via gcloud compute ssh.

    Credentials are injected by prepending `export KEY=VALUE;` to the command.
    This is visible in the SSH session's process list — acceptable for an
    ephemeral, single-user demo VM, but not for production workloads.
    """
    if env_vars:
        prefix = " ".join(
            f"export {k}={shlex.quote(str(v))};"
            for k, v in env_vars.items()
        )
        command = f"{prefix} {command}"

    return subprocess.run(
        [
            "gcloud", "compute", "ssh", config["VM_NAME"],
            "--project", config["GCP_PROJECT_ID"],
            "--zone",    config["GCP_ZONE"],
            "--quiet",
            "--command", command,
        ],
        check=check,
        capture_output=True,
        text=True,
    )


def _scp(config: dict, local_path: str, remote_path: str):
    """Copy a local file to the GCP VM."""
    _local([
        "gcloud", "compute", "scp", local_path,
        f"{config['VM_NAME']}:{remote_path}",
        "--project", config["GCP_PROJECT_ID"],
        "--zone",    config["GCP_ZONE"],
        "--quiet",
    ])


def _run_script(config: dict, script: str, env_vars: Optional[dict] = None):
    """
    Write a bash script to a local temp file, SCP it to the VM,
    execute it, then delete it from both locations.
    """
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".sh", prefix="otellab_", delete=False
    ) as f:
        f.write(script)
        local_path = f.name

    remote_path = f"/tmp/{Path(local_path).name}"
    try:
        _scp(config, local_path, remote_path)
        _remote(
            config,
            f"chmod +x {remote_path} && bash {remote_path}",
            env_vars=env_vars,
        )
    finally:
        os.unlink(local_path)
        _remote(config, f"rm -f {remote_path}", check=False)


# ── Phase: preflight ──────────────────────────────────────────────────────────

def check_preflight(console: Console):
    """Verify system requirements are met before starting."""
    import platform
    import sys

    # ── Python version ────────────────────────────────────────────────────────
    major, minor = sys.version_info[:2]
    if (major, minor) < (3, 8):
        console.print(f"  [red]✗ Python 3.8+ required (found {major}.{minor})[/red]")
        console.print("  Download: https://www.python.org/downloads/")
        raise SystemExit(1)
    console.print(f"  [green]✓[/green] Python {major}.{minor}")

    # ── gcloud ────────────────────────────────────────────────────────────────
    if not shutil.which("gcloud"):
        console.print("  [red]✗ gcloud CLI not found.[/red]")
        system = platform.system()
        if system == "Darwin":
            console.print("  Install:  [bold]brew install google-cloud-sdk[/bold]")
        elif system == "Linux":
            console.print("  Install:  [bold]curl -fsSL https://sdk.cloud.google.com | bash[/bold]")
        else:
            console.print("  Install:  https://cloud.google.com/sdk/docs/install")
        raise SystemExit(1)
    console.print("  [green]✓[/green] gcloud")

    # ── gcloud auth ───────────────────────────────────────────────────────────
    result = _local(
        ["gcloud", "auth", "list", "--filter=status:ACTIVE", "--format=value(account)"],
        check=False,
    )
    account = result.stdout.strip()
    if not account:
        console.print("  [red]✗ gcloud not authenticated.[/red]")
        console.print("  Run: [bold]gcloud auth login[/bold]")
        console.print("  Then: [bold]gcloud auth application-default login[/bold]")
        raise SystemExit(1)
    console.print(f"  [green]✓[/green] gcloud — authenticated as [bold]{account}[/bold]")


# ── Phase: create VM ──────────────────────────────────────────────────────────

def create_vm(config: dict, console: Console):
    """Create a GCP Compute Engine VM and an SSH firewall rule."""
    project = config["GCP_PROJECT_ID"]
    zone    = config["GCP_ZONE"]
    vm      = config["VM_NAME"]

    console.print(f"  [dim]Enabling Compute API...[/dim]")
    _local(["gcloud", "services", "enable", "compute.googleapis.com",
            "--project", project])

    # Firewall rule — idempotent (ignore error if already exists)
    _local([
        "gcloud", "compute", "firewall-rules", "create", _FW_RULE,
        "--project",    project,
        "--allow",      "tcp:22",
        "--target-tags", _VM_TAG,
        "--description", "OTel Lab: allow SSH",
        "--quiet",
    ], check=False)

    console.print(f"  [dim]Creating VM {vm} ({_MACHINE_TYPE}) in {zone}...[/dim]")
    _local([
        "gcloud", "compute", "instances", "create", vm,
        "--project",         project,
        "--zone",            zone,
        "--machine-type",    _MACHINE_TYPE,
        "--image-family",    _IMAGE_FAMILY,
        "--image-project",   _IMAGE_PROJECT,
        "--boot-disk-size",  _DISK_SIZE,
        "--boot-disk-type",  "pd-ssd",
        "--tags",            _VM_TAG,
        "--quiet",
    ])
    console.print(f"  [dim]VM created.[/dim]")


# ── Phase: wait for SSH ───────────────────────────────────────────────────────

def wait_for_ssh(config: dict, console: Console, timeout_sec: int = 180):
    """Poll until SSH is available on the newly created VM."""
    console.print("  [dim]Polling for SSH access (may take ~30s on first boot)...[/dim]")
    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        result = _remote(config, "echo ready", check=False)
        if result.returncode == 0 and "ready" in result.stdout:
            console.print("  [dim]SSH is up.[/dim]")
            return
        time.sleep(8)
    raise RuntimeError(f"SSH not available after {timeout_sec}s — check VM status in GCP Console")


# ── Phase: K3s + Helm ─────────────────────────────────────────────────────────

def install_k3s_and_tools(config: dict, console: Console):
    """
    Install K3s (lightweight Kubernetes), copy kubeconfig, install Helm,
    and add the required Helm repositories — all on the remote VM.
    """
    console.print("  [dim]This takes ~2 minutes on a fresh VM...[/dim]")

    script = textwrap.dedent("""\
        #!/bin/bash
        set -euo pipefail

        echo "==> Installing K3s..."
        # --disable=traefik: we don't need the built-in ingress controller
        # --write-kubeconfig-mode=644: lets non-root users read the config
        curl -sfL https://get.k3s.io | \\
          sudo INSTALL_K3S_EXEC="--disable=traefik --write-kubeconfig-mode=644" sh -

        echo "==> Waiting for node to be Ready..."
        timeout 120 bash -c \\
          'until sudo kubectl --kubeconfig=/etc/rancher/k3s/k3s.yaml get nodes 2>/dev/null \\
             | grep -q " Ready"; do sleep 4; done'

        echo "==> Copying kubeconfig for current user..."
        mkdir -p ~/.kube
        sudo cp /etc/rancher/k3s/k3s.yaml ~/.kube/config
        sudo chown "$(id -u):$(id -g)" ~/.kube/config

        echo "==> Installing Helm..."
        curl -fsSL https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 \\
          | sudo bash

        echo "==> Adding Helm repositories..."
        helm repo add open-telemetry https://open-telemetry.github.io/opentelemetry-helm-charts
        helm repo add grafana         https://grafana.github.io/helm-charts
        helm repo update

        echo "==> K3s $(kubectl version --short 2>/dev/null | head -1) ready."
        echo "==> Helm $(helm version --short) ready."
    """)

    _run_script(config, script)


# ── Phase: Kubernetes namespaces + secrets ────────────────────────────────────

def setup_kubernetes(config: dict, console: Console):
    """Create namespaces and inject Grafana Cloud credentials as K8s Secrets."""

    basic_auth_header = "Basic " + base64.b64encode(
        f"{config['GRAFANA_INSTANCE_ID']}:{config['GRAFANA_API_TOKEN']}".encode()
    ).decode()

    # NOTE: This is a plain string (not an f-string).
    # The $VARIABLE references are bash variables set by the env_vars dict below.
    script = textwrap.dedent("""\
        #!/bin/bash
        set -euo pipefail

        echo "==> Creating namespace..."
        kubectl create namespace otel-demo --dry-run=client -o yaml | kubectl apply -f -

        echo "==> Creating secret: grafana-credentials (otel-demo)..."
        kubectl create secret generic grafana-credentials \\
          --namespace=otel-demo \\
          --from-literal=GRAFANA_INSTANCE_ID="$GRAFANA_INSTANCE_ID" \\
          --from-literal=GRAFANA_API_TOKEN="$GRAFANA_API_TOKEN" \\
          --from-literal=GRAFANA_CLOUD_OTLP_ENDPOINT="$GRAFANA_CLOUD_OTLP_ENDPOINT" \\
          --from-literal=GRAFANA_CLOUD_BASIC_AUTH_HEADER="$GRAFANA_CLOUD_BASIC_AUTH_HEADER" \\
          --dry-run=client -o yaml | kubectl apply -f -

        echo "==> Secrets created."
    """)

    _run_script(config, script, env_vars={
        "GRAFANA_INSTANCE_ID":             config["GRAFANA_INSTANCE_ID"],
        "GRAFANA_API_TOKEN":               config["GRAFANA_API_TOKEN"],
        "GRAFANA_CLOUD_OTLP_ENDPOINT":     config["GRAFANA_OTLP_ENDPOINT"].removesuffix("/otlp"),
        "GRAFANA_CLOUD_BASIC_AUTH_HEADER": basic_auth_header,
    })


# ── Phase: OTel Demo ──────────────────────────────────────────────────────────

def deploy_otel_demo(config: dict, console: Console):
    """
    Upload the Helm values file and install the OpenTelemetry Demo.
    The values file references the K8s Secret for credentials — no secrets
    are written to the values file itself.
    """
    console.print("  [dim]Uploading values and running helm install (~5 min for image pulls)...[/dim]")

    values_src    = str(_MANIFESTS_DIR / "otel-demo-values.yaml")
    remote_values = "/tmp/otel-demo-values.yaml"

    _scp(config, values_src, remote_values)
    _remote(config, (
        f"helm upgrade --install otel-demo open-telemetry/opentelemetry-demo "
        f"--namespace otel-demo "
        f"--values {remote_values} "
        f"--timeout 12m --wait"
    ))
    _remote(config, f"rm -f {remote_values}", check=False)


# ── Phase: Kubernetes Monitoring ──────────────────────────────────────────────

def deploy_k8s_monitoring(config: dict, console: Console):
    """
    Render the k8s-monitoring values template with real credentials,
    upload to the VM, run helm install, then immediately delete the
    rendered file from both local disk and the VM.
    """
    console.print("  [dim]Rendering values template and running helm install...[/dim]")

    template = (_MANIFESTS_DIR / "k8s-monitoring-values.yaml").read_text()

    rendered = template
    for placeholder, value in {
        "${GRAFANA_OTLP_ENDPOINT}": config["GRAFANA_OTLP_ENDPOINT"],
        "${GRAFANA_INSTANCE_ID}":   config["GRAFANA_INSTANCE_ID"],
        "${GRAFANA_API_TOKEN}":     config["GRAFANA_API_TOKEN"],
    }.items():
        rendered = rendered.replace(placeholder, value)

    remote_values = "/tmp/k8s-monitoring-values.yaml"

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".yaml", prefix="k8smon_", delete=False
    ) as tmp:
        tmp.write(rendered)
        local_tmp = tmp.name

    try:
        _scp(config, local_tmp, remote_values)
        _remote(config, (
            f"helm upgrade --install k8s-monitoring grafana/k8s-monitoring "
            f"--namespace monitoring --create-namespace "
            f"--values {remote_values} "
            f"--timeout 10m --wait"
        ))
    finally:
        os.unlink(local_tmp)
        _remote(config, f"rm -f {remote_values}", check=False)


# ── Phase: validate ───────────────────────────────────────────────────────────

def validate(config: dict, console: Console):
    """Post-install sanity checks — pod counts and collector log scan."""

    r = _remote(
        config,
        "kubectl get pods -n otel-demo --no-headers "
        "| grep -v -E 'Running|Completed' | wc -l",
        check=False,
    )
    not_ready = r.stdout.strip() if r.returncode == 0 else "?"
    if not_ready == "0":
        console.print("  [green]✓[/green] OTel Demo: all pods Running")
    else:
        console.print(
            f"  [yellow]⚠[/yellow]  OTel Demo: {not_ready} pod(s) not yet Running "
            f"(images may still be pulling — this is normal)"
        )

    # Scan collector logs for auth errors
    r = _remote(
        config,
        "kubectl logs -n otel-demo -l app.kubernetes.io/component=otelcol "
        "--tail=30 2>/dev/null || true",
        check=False,
    )
    logs = r.stdout.lower()
    if "401" in logs or "unauthorized" in logs:
        console.print(
            "  [yellow]⚠[/yellow]  Collector log shows auth errors — "
            "double-check GRAFANA_INSTANCE_ID and GRAFANA_API_TOKEN"
        )
    elif "error" in logs:
        console.print(
            "  [yellow]⚠[/yellow]  Collector log contains errors — run:\n"
            f"    gcloud compute ssh {config['VM_NAME']} "
            f"--zone {config['GCP_ZONE']} -- "
            "kubectl logs -n otel-demo -l app.kubernetes.io/component=otelcol --tail=50"
        )
    else:
        console.print("  [green]✓[/green] Collector logs look clean")


# ── Phase: import dashboards ─────────────────────────────────────────────────

def _grafana_request(grafana_url: str, method: str, path: str,
                     token: str, payload: Optional[dict] = None) -> dict:
    """Make an authenticated request to the Grafana HTTP API."""
    url = f"{grafana_url.rstrip('/')}{path}"
    data = json.dumps(payload).encode() if payload else None
    req = urllib.request.Request(
        url, data=data, method=method,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )
    ssl_ctx = ssl.create_default_context(cafile=certifi.where())
    try:
        with urllib.request.urlopen(req, timeout=15, context=ssl_ctx) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")
        raise RuntimeError(f"Grafana API {method} {path} → {e.code}: {body[:300]}")


def _discover_datasource_uids(grafana_url: str, token: str) -> dict:
    """
    Return a mapping of placeholder → real UID for the three datasource types
    we need: prometheus, tempo, loki.

    Grafana Cloud stacks always have exactly one hosted datasource of each type.
    If multiple exist (e.g. after enabling k8s-monitoring) we prefer the one
    whose name contains 'grafanacloud' or whose type matches exactly.
    """
    datasources = _grafana_request(grafana_url, "GET", "/api/datasources", token)

    # Loki datasource UIDs that are not general-purpose log stores
    _LOKI_EXCLUDE = {"grafanacloud-alert-state-history", "grafanacloud-usage-insights"}

    def _pick(type_name: str) -> str:
        matches = [d for d in datasources if d.get("type") == type_name]
        if not matches:
            raise RuntimeError(
                f"No '{type_name}' datasource found in Grafana — "
                f"make sure telemetry is flowing and the datasource is provisioned."
            )
        # For Loki, exclude special-purpose datasources (alert state, usage insights)
        if type_name == "loki":
            matches = [d for d in matches if d.get("uid") not in _LOKI_EXCLUDE] or matches
        # Prefer the Grafana Cloud hosted logs datasource (uid ends with -logs)
        # then any grafanacloud- prefixed one, then first match
        for preference in [
            lambda d: d.get("uid", "").endswith("-logs"),
            lambda d: "grafanacloud" in d.get("name", "").lower(),
        ]:
            preferred = [d for d in matches if preference(d)]
            if preferred:
                return preferred[0]["uid"]
        return matches[0]["uid"]

    return {
        "__DS_PROMETHEUS__": _pick("prometheus"),
        "__DS_TEMPO__":      _pick("tempo"),
        "__DS_LOKI__":       _pick("loki"),
    }


def import_dashboards(config: dict, console: Console):
    """
    Import the pre-patched OTel Demo dashboards into Grafana Cloud via the
    Grafana HTTP API.  Datasource placeholder UIDs are replaced with the real
    UIDs discovered from the target Grafana instance.
    """
    grafana_url = config["GRAFANA_URL"].rstrip("/")
    token       = config["GRAFANA_SA_TOKEN"]

    console.print("  [dim]Discovering datasource UIDs...[/dim]")
    try:
        uid_map = _discover_datasource_uids(grafana_url, token)
    except RuntimeError as e:
        console.print(f"  [yellow]⚠[/yellow]  {e}")
        console.print("  [dim]Skipping dashboard import — run again once data is flowing.[/dim]")
        return

    dashboards_dir = _REPO_ROOT / "manifests" / "dashboards"
    dashboard_files = sorted(dashboards_dir.glob("*.json"))

    if not dashboard_files:
        console.print("  [yellow]⚠[/yellow]  No dashboard files found in manifests/dashboards/")
        return

    # Ensure a folder exists for the demo dashboards
    try:
        folder_resp = _grafana_request(
            grafana_url, "POST", "/api/folders", token,
            {"title": "OTel Demo"},
        )
        folder_uid = folder_resp["uid"]
    except RuntimeError:
        # Folder may already exist — find it
        folders = _grafana_request(grafana_url, "GET", "/api/folders", token)
        existing = [f for f in folders if f.get("title") == "OTel Demo"]
        folder_uid = existing[0]["uid"] if existing else None

    for path in dashboard_files:
        text = path.read_text()
        for placeholder, uid in uid_map.items():
            text = text.replace(f'"{placeholder}"', f'"{uid}"')

        dashboard = json.loads(text)
        payload = {
            "dashboard":  dashboard,
            "folderUid":  folder_uid,
            "overwrite":  True,
            "message":    "imported by otel-lab wizard",
        }
        try:
            _grafana_request(grafana_url, "POST", "/api/dashboards/db", token, payload)
            console.print(f"  [green]✓[/green] {path.stem}")
        except RuntimeError as e:
            console.print(f"  [yellow]⚠[/yellow]  {path.stem}: {e}")


# ── Phase: teardown ───────────────────────────────────────────────────────────

def teardown_vm(config: dict, console: Console):
    """Delete the GCP VM and the SSH firewall rule."""
    console.print(f"  Deleting VM [bold]{config['VM_NAME']}[/bold]...")
    _local([
        "gcloud", "compute", "instances", "delete", config["VM_NAME"],
        "--project", config["GCP_PROJECT_ID"],
        "--zone",    config["GCP_ZONE"],
        "--quiet",
    ])
    console.print("  [dim]Deleting firewall rule...[/dim]")
    _local([
        "gcloud", "compute", "firewall-rules", "delete", _FW_RULE,
        "--project", config["GCP_PROJECT_ID"],
        "--quiet",
    ], check=False)
    console.print("  [green]✓[/green] Torn down.")
