#!/usr/bin/env python3
"""
OTel Lab — SE Demo Wizard

Provisions a GCP Linux VM, installs K3s, deploys the OpenTelemetry Demo,
and connects everything to Grafana Cloud — all from one interactive wizard.

Usage:
  python3 setup.py                 # Full guided setup
  python3 setup.py --skip-vm       # VM already exists; skip creation
  python3 setup.py --teardown      # Delete the VM and all resources
"""

import argparse
import os
import sys
import subprocess
from pathlib import Path

# ── Bootstrap dependencies before any rich/dotenv imports ────────────────────
def _bootstrap():
    try:
        import rich   # noqa
        import dotenv # noqa
    except ImportError:
        print("Installing required Python packages (rich, python-dotenv)...")
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "--quiet", "rich>=13", "python-dotenv>=1"],
            check=True,
        )

_bootstrap()

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, Confirm
from rich.table import Table
from rich.text import Text
from dotenv import load_dotenv, set_key

from lib.provision import (
    check_preflight,
    create_vm,
    wait_for_ssh,
    install_k3s_and_tools,
    setup_kubernetes,
    deploy_otel_demo,
    validate,
    teardown_vm,
)

console = Console()
SCRIPT_DIR = Path(__file__).parent
ENV_FILE    = SCRIPT_DIR / ".env"

_CONFIG_KEYS = [
    "VM_NAME",
    "GCP_PROJECT_ID",
    "GCP_ZONE",
    "GRAFANA_OTLP_ENDPOINT",
    "GRAFANA_INSTANCE_ID",
    "GRAFANA_API_TOKEN",
]


# ── UI helpers ────────────────────────────────────────────────────────────────

def banner():
    console.print()
    console.print(Panel(
        Text.from_markup(
            "[bold cyan]OTel Lab[/bold cyan]  ·  SE Demo Wizard\n"
            "[dim]GCP VM  ·  K3s  ·  OpenTelemetry Demo  ·  Grafana Cloud[/dim]"
        ),
        border_style="cyan",
        padding=(1, 4),
    ))
    console.print()


def _mask(token: str) -> str:
    if len(token) > 6:
        return token[:3] + "****" + token[-3:]
    return "****"


def show_summary(config: dict):
    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column(style="dim", no_wrap=True)
    table.add_column()
    table.add_row("GCP Project",    config["GCP_PROJECT_ID"])
    table.add_row("GCP Zone",       config["GCP_ZONE"])
    table.add_row("VM Name",        config["VM_NAME"] + "  (e2-standard-4 · Ubuntu 22.04 · 50 GB SSD)")
    table.add_row("OTLP Endpoint",  config["GRAFANA_OTLP_ENDPOINT"])
    table.add_row("Instance ID",    config["GRAFANA_INSTANCE_ID"])
    table.add_row("API Token",      _mask(config["GRAFANA_API_TOKEN"]))
    console.print(Panel(table, title="[bold]Configuration[/bold]", border_style="blue"))
    console.print()


def show_completion(config: dict):
    p  = config["GCP_PROJECT_ID"]
    z  = config["GCP_ZONE"]
    vm = config["VM_NAME"]

    console.print()
    console.print("[bold green]✓  Setup complete![/bold green]")
    console.print()

    console.print("[bold]── Verify telemetry in Grafana Cloud ──────────────────[/bold]")
    console.print("  grafana.com → your stack → Launch Grafana")
    console.print("  Then use the [bold]Drilldown[/bold] menu in the left sidebar:")
    console.print()
    console.print("  [bold]Traces[/bold]   Drilldown → Traces")
    console.print("    Confirm you see spans from the demo's services:")
    console.print("    [dim]frontend, checkout, cart, payment, shipping, productcatalog[/dim]")
    console.print("    Click any trace → you should see a full multi-service waterfall.")
    console.print("    Filter by  Service Name = frontend  to see end-to-end request traces.")
    console.print()
    console.print("  [bold]Metrics[/bold]  Drilldown → Metrics")
    console.print("    Search  [bold]http.server[/bold]  → look for metrics like:")
    console.print("    [dim]http.server.request.duration, http.server.active_requests[/dim]")
    console.print("    These confirm HTTP instrumentation is working across all services.")
    console.print("    Search  [bold]otelcol_[/bold]  → confirms the collector itself is healthy:")
    console.print("    [dim]otelcol_exporter_sent_spans, otelcol_receiver_accepted_metric_points[/dim]")
    console.print()
    console.print("  [bold]Logs[/bold]    Drilldown → Logs")
    console.print("    You should see entries from multiple services immediately.")
    console.print("    Filter by  service.name = frontend  or  checkoutservice")
    console.print("    to confirm structured logs are flowing with trace correlation.")
    console.print("    Look for a [bold]TraceID[/bold] field — clicking it jumps to the matching trace.")
    console.print()

    console.print("  [bold]Dashboards[/bold]  Dashboards → Import → Upload JSON")
    console.print("    Pre-built dashboards are in [dim]manifests/dashboards/[/dim] in the repo.")
    console.print("    Import them manually to explore — or build your own as you learn.")
    console.print()

    console.print("[bold]── View the OTel Demo store (optional) ────────────────[/bold]")
    console.print("  The demo is a live fake e-commerce store with always-on traffic.")
    console.print("  Browse it to generate traces on demand — add items, checkout, etc.")
    console.print("  Run this command, then open http://localhost:8080")
    console.print()
    console.print(f"  gcloud compute ssh {vm} --project {p} --zone {z} --ssh-flag=\"-L 8080:localhost:8080\" -- kubectl port-forward -n otel-demo svc/otel-demo-frontendproxy 8080:8080")
    console.print()

    console.print("[bold]── Kubernetes infrastructure monitoring (optional) ──────[/bold]")
    console.print("  Add cluster/node/pod metrics and logs via Grafana Alloy.")
    console.print("  Grafana Cloud walks you through it — go to:")
    console.print("  [bold]grafana.com → your stack → Kubernetes tile → Start sending data[/bold]")
    console.print("  Uses the same OTLP credentials — no new tokens needed.")
    console.print()

    console.print("[bold]── SSH into the VM ─────────────────────────────────────[/bold]")
    console.print(f"  gcloud compute ssh {vm} --project {p} --zone {z}")
    console.print()

    console.print("[bold]── Tear down when done (~$0.13/hr while running) ───────[/bold]")
    console.print("  ./teardown.sh")


# ── Config load / save / prompt ───────────────────────────────────────────────

def _detect_gcp_defaults() -> dict:
    """
    Read GCP project and zone from the active gcloud config so the SE
    doesn't have to look them up — they just hit Enter.
    """
    def _gcloud_value(prop: str) -> str:
        try:
            r = subprocess.run(
                ["gcloud", "config", "get-value", prop],
                capture_output=True, text=True, timeout=5,
            )
            return r.stdout.strip() if r.returncode == 0 else ""
        except Exception:
            return ""

    def _gcloud_account() -> str:
        try:
            r = subprocess.run(
                ["gcloud", "auth", "list", "--filter=status:ACTIVE", "--format=value(account)"],
                capture_output=True, text=True, timeout=5,
            )
            return r.stdout.strip().splitlines()[0] if r.returncode == 0 else ""
        except Exception:
            return ""

    return {
        "GCP_PROJECT_ID": _gcloud_value("project"),
        "GCP_ZONE":       _gcloud_value("compute/zone") or "us-central1-a",
        "account":        _gcloud_account(),
    }



def load_existing_config() -> dict:
    if ENV_FILE.exists():
        load_dotenv(ENV_FILE, override=True)
    return {k: os.environ.get(k, "") for k in _CONFIG_KEYS}


def save_config(config: dict):
    for key in _CONFIG_KEYS:
        if config.get(key):
            set_key(str(ENV_FILE), key, config[key])
    ENV_FILE.chmod(0o600)  # owner read/write only


def prompt_config(existing: dict) -> dict:
    config = dict(existing)

    # Fill GCP fields from gcloud config if not already saved in .env
    gcp_defaults = _detect_gcp_defaults()
    for key, val in gcp_defaults.items():
        if not config.get(key) and val:
            config[key] = val

    console.rule("[bold]GCP[/bold]")
    console.print()
    console.print("  [bold]Project ID[/bold]  →  [link=https://console.cloud.google.com]console.cloud.google.com[/link] — top bar dropdown")
    console.print("  [bold]Zone[/bold]        →  leave blank to use [dim]us-central1-a[/dim]")
    console.print()

    config["GCP_PROJECT_ID"] = Prompt.ask(
        "  Project ID",
        default=config.get("GCP_PROJECT_ID") or "",
    )
    config["GCP_ZONE"] = Prompt.ask(
        "  Zone",
        default=config.get("GCP_ZONE") or "us-central1-a",
    )

    # Build a default VM name from the gcloud account (e.g. jsmith@grafana.com → otel-lab-jsmith)
    _account = _detect_gcp_defaults().get("account", "")
    _username = _account.split("@")[0] if "@" in _account else ""
    _slug = "".join(c if c.isalnum() or c == "-" else "-" for c in _username.lower()).strip("-")
    _vm_default = f"otel-lab-{_slug}" if _slug else "otel-lab-vm"

    config["VM_NAME"] = Prompt.ask(
        "  VM Name [dim](must be unique within the GCP project)[/dim]",
        default=config.get("VM_NAME") or _vm_default,
    )

    console.print()
    console.rule("[bold]Grafana Cloud — Core[/bold]")
    console.print()
    console.print("  Open [bold]grafana.com → your org → your stack[/bold], then:")
    console.print()
    console.print("  [bold]OTLP Endpoint[/bold]   →  OpenTelemetry tile → Details → OTLP Endpoint URL")
    console.print("  [bold]Instance ID[/bold]     →  Grafana tile → Details → Instance ID  [dim](a number)[/dim]")
    console.print("  [bold]API Token[/bold]       →  Access Policies → Create token")
    console.print("                    Scopes: [dim]metrics:write  logs:write  traces:write[/dim]")
    console.print()

    config["GRAFANA_OTLP_ENDPOINT"] = Prompt.ask(
        "  OTLP Endpoint",
        default=config.get("GRAFANA_OTLP_ENDPOINT") or "https://otlp-gateway-prod-us-east-0.grafana.net/otlp",
    )
    config["GRAFANA_INSTANCE_ID"] = Prompt.ask(
        "  Instance ID",
        default=config.get("GRAFANA_INSTANCE_ID") or "",
    )
    config["GRAFANA_API_TOKEN"] = Prompt.ask(
        "  API Token",
        default=config.get("GRAFANA_API_TOKEN") or "",
        password=True,
    )

    return config


# ── Main orchestration ────────────────────────────────────────────────────────

def run_setup(config: dict, skip_vm: bool):
    phases = []

    if not skip_vm:
        phases += [
            ("Creating GCP VM",   lambda: create_vm(config, console)),
            ("Waiting for SSH",   lambda: wait_for_ssh(config, console)),
        ]

    phases += [
        ("Installing K3s + Helm",   lambda: install_k3s_and_tools(config, console)),
        ("Configuring Kubernetes",  lambda: setup_kubernetes(config, console)),
        ("Deploying OTel Demo",     lambda: deploy_otel_demo(config, console)),
        ("Validating",              lambda: validate(config, console)),
    ]

    total = len(phases)
    for idx, (label, fn) in enumerate(phases, 1):
        console.print(f"\n[bold cyan][{idx}/{total}][/bold cyan] {label}...")
        try:
            fn()
            console.print(f"  [green]✓[/green] {label}")
        except subprocess.CalledProcessError as exc:
            console.print(f"\n  [red]✗ {label} failed.[/red]")
            if exc.stderr:
                console.print(f"  [dim]{exc.stderr.strip()[:600]}[/dim]")
            console.print(
                "\n[yellow]Tip:[/yellow] If the VM exists but setup failed mid-way, "
                "re-run with [bold]--skip-vm[/bold] to skip creation and retry from K3s."
            )
            sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="OTel Lab SE Demo Wizard",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--teardown", action="store_true",
        help="Delete the GCP VM and all resources",
    )
    parser.add_argument(
        "--skip-vm", action="store_true",
        help="Skip VM creation (use when VM already exists)",
    )
    args = parser.parse_args()

    banner()

    # ── Teardown path ──────────────────────────────────────────────────────────
    if args.teardown:
        config = load_existing_config()
        if not config.get("GCP_PROJECT_ID"):
            console.print("[red]No .env found — nothing to tear down.[/red]")
            sys.exit(0)
        confirmed = Confirm.ask(
            f"Delete VM [bold]{config['VM_NAME']}[/bold] in project "
            f"[bold]{config['GCP_PROJECT_ID']}[/bold]?",
            default=False,
        )
        if confirmed:
            teardown_vm(config, console)
        else:
            console.print("Cancelled.")
        return

    # ── Setup path ─────────────────────────────────────────────────────────────
    console.print("[bold]Checking required tools...[/bold]")
    check_preflight(console)

    existing = load_existing_config()
    config = prompt_config(existing)

    save_config(config)
    console.print(f"\n[dim]Credentials saved to {ENV_FILE} (mode 600)[/dim]")

    console.print()
    show_summary(config)

    if not Confirm.ask("Proceed with setup?", default=True):
        console.print("Aborted.")
        sys.exit(0)

    run_setup(config, skip_vm=args.skip_vm)
    show_completion(config)


if __name__ == "__main__":
    main()
