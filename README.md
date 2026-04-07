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

## System requirements

| Requirement | Version | Notes |
|---|---|---|
| **OS** | macOS or Linux | Windows: use [WSL2](https://learn.microsoft.com/en-us/windows/wsl/install) |
| **Python** | 3.8+ | Check with `python3 --version` |
| **gcloud CLI** | any recent | See install instructions below |
| **Python packages** | — | Installed automatically by `run.sh` into a local venv |

Everything else (kubectl, Helm, K3s) runs on the GCP VM — nothing to install locally beyond the three items above.

### Install gcloud

**macOS**
```bash
brew install google-cloud-sdk
```

**Linux**
```bash
curl -fsSL https://sdk.cloud.google.com | bash
exec -l $SHELL
```

**Windows (WSL2)**
Follow the Linux instructions above inside your WSL2 terminal.

---

## Before you start — gather everything first

The wizard will ask for credentials interactively. Collect these **before** running it so you're not switching between windows mid-setup.

### GCP (required)

| What | Where |
|---|---|
| **Project ID** | [console.cloud.google.com](https://console.cloud.google.com) — top bar dropdown, looks like `my-project-123456` |
| **gcloud authenticated** | Run `gcloud auth login` and `gcloud auth application-default login` |

### Grafana Cloud — core (required)

All found at **grafana.com → your org → your stack**:

| What | Where exactly |
|---|---|
| **OTLP Endpoint** | Click the **OpenTelemetry** tile → Details → **OTLP Endpoint** |
| **Instance ID** | Click the **Grafana** tile → Details → **Instance ID** (a number like `1035398`) |
| **API Token** | **Access Policies** → Create token → scopes: `metrics:write`, `logs:write`, `traces:write` |

### Grafana Cloud — Kubernetes infrastructure monitoring (optional)

Deploys Grafana Alloy to collect cluster/node/pod metrics. Skip this if you only want the OTel Demo app signals.

All found at **grafana.com → your org → your stack**:

| What | Where exactly |
|---|---|
| **Prometheus URL** | Click the **Prometheus** tile → Details → **Remote Write Endpoint** (paste the full URL — path is stripped automatically) |
| **Prometheus Username** | Same Details page → **Username** (a number) |
| **Loki URL** | Click the **Loki** tile → Details → **URL** (paste the full URL — path is stripped automatically) |
| **Loki Username** | Same Details page → **Username** (a number) |

---

## Setup

### 1 — Install gcloud

```bash
brew install google-cloud-sdk
```

No Homebrew? Install it first:
```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

### 2 — Authenticate and set your project

```bash
gcloud auth login
gcloud auth application-default login
gcloud config set project YOUR_PROJECT_ID
```

### 3 — Run the wizard

```bash
git clone https://github.com/bojurk/glabs-otel-demo
cd glabs-otel-demo
./run.sh
```

The wizard detects your GCP project automatically, prompts for credentials (with inline hints showing exactly where to find each value), then builds everything. **Total time: ~15 minutes.**

---

## Viewing your data in Grafana Cloud

Once setup completes, open grafana.com → your stack → **Launch Grafana**.

### Traces
**Drilldown → Traces** — rate, error rate, and duration for every demo microservice. No query needed.

### Metrics
**Drilldown → Metrics** — browse all metrics. Search `http_server` for OTel Demo request metrics, or `otelcol_` for collector self-monitoring.

### Logs
**Drilldown → Logs** — all services ranked by log volume. Click any service → Show logs.

### Dashboards

Six pre-built dashboards are included in `manifests/dashboards/` in this repo. They are **not imported automatically** — import them manually when you're ready to explore them.

**To import:** Grafana → Dashboards → New → Import → Upload JSON file

| Dashboard | What it shows |
|---|---|
| **apm-dashboard** | RED metrics (rate, errors, duration) per service with one-click trace drilldown |
| **demo-dashboard** | Top-level store overview — throughput and latency across all services |
| **spanmetrics-dashboard** | Latency quantiles and error rates derived from trace span metrics |
| **exemplars-dashboard** | Metrics data points linked to specific traces via exemplars |
| **postgresql-dashboard** | PostgreSQL metrics from the demo's database |
| **opentelemetry-collector** | Collector internal health — spans received/exported, batch sizes, memory |

When importing, Grafana will prompt you to map each datasource — select your Grafana Cloud Prometheus, Tempo, and Loki datasources.

---

## Browse the demo store (optional)

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
| `./run.sh --skip-vm` | Re-run setup on an existing VM (use after config changes or to enable optional features) |
| `./teardown.sh` | Delete the VM and stop all charges |

---

## Troubleshooting

**No data in Grafana Cloud after 5 minutes**

```bash
gcloud compute ssh YOUR_VM_NAME --zone YOUR_ZONE -- \
  kubectl logs -n otel-demo -l app.kubernetes.io/component=otelcol --tail=50
```

- `401 Unauthorized` → wrong Instance ID or API Token
- `connection refused` / `404` → wrong OTLP Endpoint region

**Pods not starting**

```bash
gcloud compute ssh YOUR_VM_NAME --zone YOUR_ZONE -- kubectl get pods -n otel-demo
```

`ImagePullBackOff` is normal on first deploy — images are large (~1 GB total). Wait a few minutes.

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
