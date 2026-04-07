# OTel Lab — SE Demo Wizard

One command spins up a live OpenTelemetry + Grafana Cloud demo on GCP.
Clone the repo, answer a few prompts, walk away. Everything else is automated.

---

## What gets built

```
GCP VM  (e2-standard-4 · Ubuntu 22.04 · 50 GB SSD)
└── K3s (lightweight Kubernetes)
    ├── otel-demo namespace
    │   ├── ~20 microservices  — fake e-commerce store with always-on load generator
    │   └── OTel Collector     — receives all app telemetry, forwards to Grafana Cloud
    │                            traces · metrics · logs  (+ collector self-monitoring)
    └── monitoring namespace  (optional)
        └── Grafana Alloy      — scrapes Kubernetes cluster/node/pod metrics
```

Everything flows to **your** Grafana Cloud stack via the OTLP gateway.
No in-cluster Grafana, Jaeger, or Prometheus — Grafana Cloud is the backend.

**Cost:** ~$0.13/hr (~$3/day). Run `./teardown.sh` when done.

---

## Prerequisites

### 1 — Install gcloud

```bash
brew install google-cloud-sdk
```

No Homebrew?  Install it first:
```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

### 2 — Authenticate with Google Cloud

```bash
gcloud auth login
gcloud auth application-default login
```

Both open a browser window — sign in and click Allow.

### 3 — Set your GCP project

```bash
gcloud config set project YOUR_PROJECT_ID
```

Your Project ID is in the top bar of [console.cloud.google.com](https://console.cloud.google.com) — it looks like `my-project-123456`.

Don't have a project? Create one at console.cloud.google.com → New Project. Make sure billing is enabled.

### 4 — Gather your Grafana Cloud credentials

You need a free Grafana Cloud account at [grafana.com](https://grafana.com).

Go to **grafana.com → your org → your stack**. The wizard will ask for:

#### Required

| Credential | Where to find it |
|---|---|
| **OTLP Endpoint** | Click the **OpenTelemetry** tile → Details → OTLP Endpoint URL |
| **Grafana Instance ID** | Click the **Grafana** tile → Details → Instance ID (a number) |
| **API Token** | Access Policies → Create token — set scopes: `metrics:write`, `logs:write`, `traces:write` |

#### Optional — Kubernetes infrastructure monitoring

Enabling this deploys Grafana Alloy alongside the demo to scrape cluster/node/pod metrics.
If you skip it, the OTel Demo still sends all traces, metrics, and logs — you just won't have Kubernetes host-level dashboards.

| Credential | Where to find it |
|---|---|
| **Prometheus Host** | Click the **Prometheus** tile → Details → Remote Write Endpoint — copy only the host (e.g. `https://prometheus-prod-13-prod-us-east-0.grafana.net`) |
| **Prometheus Username** | Same Details page → Username (a number) |
| **Loki Host** | Click the **Loki** tile → Details → URL — copy only the host (e.g. `https://logs-prod-us-east-0.grafana.net`) |
| **Loki Username** | Same Details page → Username (a number) |

---

## Run the wizard

```bash
git clone https://github.com/YOUR_ORG/otel-lab
cd otel-lab
./run.sh
```

The wizard will:
1. Detect your GCP project from `gcloud config`
2. Ask for your Grafana Cloud credentials
3. Create the VM, install Kubernetes, deploy everything
4. Print instructions for viewing the demo

**Total time: ~15 minutes** (mostly image pulls on first run).

---

## Viewing your data in Grafana Cloud

Once setup completes, open Grafana Cloud → your stack → Launch Grafana.

### Traces
**Drilldown → Traces**
Shows rate, error rate, and duration for every demo microservice.
No query needed — data appears automatically.

### Metrics
**Drilldown → Metrics**
Browse all metrics. Search `http_server` for OTel Demo request metrics, or `otelcol_` for collector self-monitoring.

### Logs
**Drilldown → Logs**
All services ranked by log volume. Click any service → Show logs for live lines.

### Collector Overview dashboard
Search dashboards for **OpenTelemetry Collector** — shows the collector's internal health:
spans received/exported, batch sizes, memory usage. Populated by `otelcol_*` metrics
that the collector sends about itself.

---

## Browse the demo store (optional)

The demo app is a fully functional fake e-commerce store. To open it locally:

```bash
gcloud compute ssh YOUR_VM_NAME \
  --project YOUR_PROJECT \
  --zone YOUR_ZONE \
  --ssh-flag="-L 8080:localhost:8080" \
  -- kubectl port-forward -n otel-demo svc/otel-demo-frontendproxy 8080:8080
```

Then open [http://localhost:8080](http://localhost:8080).

---

## Commands

| Command | What it does |
|---|---|
| `./run.sh` | Full setup — creates VM, installs everything |
| `./run.sh --skip-vm` | Re-run setup steps on an existing VM (use after config changes) |
| `./teardown.sh` | Delete the VM and stop all charges |

---

## Updating credentials or enabling k8s monitoring later

If you skipped Kubernetes monitoring and want to enable it later, or if your API token changes:

```bash
./run.sh --skip-vm
```

This re-runs all install steps against your existing VM without recreating it.
The wizard will prompt for credentials again — previous values are pre-filled.

---

## Troubleshooting

**No data in Grafana Cloud after 5 minutes**

Check the collector logs on the VM:
```bash
gcloud compute ssh YOUR_VM_NAME --zone YOUR_ZONE -- \
  kubectl logs -n otel-demo -l app.kubernetes.io/component=otelcol --tail=50
```

Look for `401 Unauthorized` → wrong `GRAFANA_INSTANCE_ID` or `GRAFANA_API_TOKEN`.
Look for `connection refused` → wrong `GRAFANA_OTLP_ENDPOINT` region.

**Pods not starting**

```bash
gcloud compute ssh YOUR_VM_NAME --zone YOUR_ZONE -- \
  kubectl get pods -n otel-demo
```

`ImagePullBackOff` is normal on first deploy — images are large. Wait a few minutes and check again.

**Re-run after a failure**

```bash
./run.sh --skip-vm
```

The wizard is idempotent — helm upgrades and kubectl applies are safe to re-run.

---

## Architecture

```
┌─────────────────────────────── GCP VM ──────────────────────────────────┐
│                                                                          │
│  ┌──────────── otel-demo namespace ─────────────────────────────────┐   │
│  │                                                                   │   │
│  │  frontend  ──┐                                                    │   │
│  │  cart      ──┤                                                    │   │
│  │  checkout  ──┤──► OTel Collector ──► Grafana Cloud OTLP gateway  │   │
│  │  payment   ──┤     (all signals)      traces / metrics / logs     │   │
│  │  ... +15   ──┘     self-monitoring ──► otelcol_* metrics         │   │
│  │                                                                   │   │
│  └───────────────────────────────────────────────────────────────── ┘   │
│                                                                          │
│  ┌──────────── monitoring namespace (optional) ─────────────────────┐   │
│  │                                                                   │   │
│  │  Grafana Alloy ──► Prometheus remote_write  ─► Grafana Cloud     │   │
│  │  (k8s-monitoring)  Loki push                                     │   │
│  │                                                                   │   │
│  └───────────────────────────────────────────────────────────────── ┘   │
│                                                                          │
└──────────────────────────────────────────────────────────────────────────┘
```

The OTel Collector is the single exit point for all demo app telemetry.
Credentials are stored in a Kubernetes Secret — never written to values files.
