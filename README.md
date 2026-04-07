# OpenTelemetry Demo Wizard — Grafana Cloud

A setup wizard that deploys the [OpenTelemetry Demo](https://opentelemetry.io/docs/demo/) on a GCP VM and connects it to your Grafana Cloud stack — traces, metrics, and logs flowing in under 15 minutes.

One command. No Kubernetes experience required.

---

## What it does

Spins up a GCP VM running K3s, deploys the OTel Demo (a ~20-service fake e-commerce app with a built-in load generator), and configures the OTel Collector to export all telemetry to Grafana Cloud via OTLP. Everything runs continuously so there's always live data to explore.

**Cost:** ~$0.13/hr (~$3/day). Tear it down with `./teardown.sh` when done.

---

## Setup modes

The wizard asks you to choose a mode before it starts:

| Mode | What gets deployed |
|---|---|
| **Guided** | VM + K3s + OTel Demo → Grafana Cloud. You configure Kubernetes Monitoring and Application Observability yourself — good for learning the platform hands-on. |
| **Full Auto** | Everything in Guided, plus Grafana Alloy (k8s-monitoring Helm chart) deployed automatically. Kubernetes Monitoring and Application Observability are ready to use immediately. |

Not sure? Start with **Full Auto**.

---

## What you'll be able to explore

- **Traces** — end-to-end distributed traces across all 20 demo services
- **Metrics** — request rates, error rates, and latency for every service
- **Logs** — structured logs from every service, correlated with traces
- **Application Observability** — service map with RED metrics and trace drilldown
- **Kubernetes Monitoring** — cluster, node, and pod metrics (Full Auto) or self-configure (Guided)

---

## Prerequisites

| Requirement | Notes |
|---|---|
| **macOS or Linux** | Windows: use [WSL2](https://learn.microsoft.com/en-us/windows/wsl/install) |
| **Python 3.8+** | `python3 --version` to check |
| **gcloud CLI** | Install instructions below |
| **A GCP project** | Needs billing enabled — free tier credit covers this lab |
| **A Grafana Cloud account** | Free tier at [grafana.com](https://grafana.com) |

Python dependencies install automatically into a local virtualenv on first run.

---

## Step 1 — Install the gcloud CLI

**macOS**
```bash
brew install google-cloud-sdk
```

No Homebrew? Install it first:
```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

**Linux / WSL2**
```bash
curl -fsSL https://sdk.cloud.google.com | bash
exec -l $SHELL
```

---

## Step 2 — Authenticate with GCP

Run each command in order. The first two open a browser for Google login — complete the flow, then return to your terminal.

```bash
gcloud auth login
```
```bash
gcloud auth application-default login
```
```bash
gcloud config set project YOUR_PROJECT_ID
```

Your project ID is in the top bar of [console.cloud.google.com](https://console.cloud.google.com) — it looks like `my-project-123456`.

---

## Step 3 — Collect your Grafana Cloud credentials

The wizard prompts for these during setup. Find them at **grafana.com → your org → your stack**:

**OTLP Endpoint**
OpenTelemetry tile → Details → OTLP Endpoint URL
(e.g. `https://otlp-gateway-prod-us-east-0.grafana.net/otlp`)

**Instance ID**
Grafana tile → Details → Instance ID (a number like `1035398`)

**API Token**
Access Policies → Create access policy → select your stack → check scopes `metrics:write`, `logs:write`, `traces:write` → Create → Add token → copy the value (you won't see it again)

---

## Step 4 — Clone the repo and run the wizard

```bash
git clone https://github.com/bojurk/glabs-otel-demo
cd glabs-otel-demo
./run.sh
```

The wizard auto-detects your GCP project and zone, prompts for your Grafana Cloud credentials (with inline hints for each value), then builds everything. Total time: ~15 minutes.

---

## Step 5 — Explore your data

Open **grafana.com → your stack → Launch Grafana**.

### Traces
**Drilldown → Traces** — live trace list from the OTel Demo load generator. Click any trace to see the full multi-service waterfall.

### Metrics
**Drilldown → Metrics** — search `http.server` for request metrics across services, or `otelcol_` for collector self-monitoring metrics.

### Logs
**Drilldown → Logs** — structured logs from all services. Filter by `service.name` to focus on a single service. Log entries include a `TraceID` field — clicking it jumps to the matching trace.

### Application Observability
**Application** in the left nav — service map with RED metrics per service and trace drilldown.

### Kubernetes Monitoring
**Kubernetes** in the left nav — cluster, node, and pod metrics from Grafana Alloy.

> **Guided mode:** this section will be empty until you configure Kubernetes Monitoring — see the optional section below.

### Dashboards

Six pre-built dashboards are in `manifests/dashboards/`. To import one:

1. In Grafana: **Dashboards → New → Import → Upload JSON file**
2. Select a file from `manifests/dashboards/`
3. When prompted to select datasources, choose the `grafanacloud-*` options for Prometheus, Tempo, and Loki
4. Click **Import**

Repeat for each dashboard file.

| Dashboard | What it shows |
|---|---|
| **apm-dashboard** | RED metrics per service with one-click trace drilldown |
| **demo-dashboard** | Store-wide throughput and latency overview |
| **spanmetrics-dashboard** | Latency quantiles derived from trace span metrics |
| **exemplars-dashboard** | Metric spikes linked directly to the traces that caused them |
| **postgresql-dashboard** | PostgreSQL metrics from the demo's database service |
| **opentelemetry-collector** | Collector health — spans received/exported, batch sizes, memory |

---

## Optional — Browse the OTel Demo storefront

To generate traces on demand, port-forward the frontend to your local machine.

First, SSH into your VM (your VM name, project, and zone are saved in `.env` in the repo root):

```bash
gcloud compute ssh YOUR_VM_NAME --project YOUR_PROJECT_ID --zone YOUR_ZONE
```

Once inside the VM, run:

```bash
kubectl port-forward -n otel-demo svc/otel-demo-frontendproxy 8080:8080
```

Keep that terminal open and open [http://localhost:8080](http://localhost:8080) in your browser. Add items to the cart, check out — each action generates traces visible in Grafana within seconds.

---

## Optional — Set up Kubernetes Monitoring (Guided mode only)

Grafana Cloud has a guided setup that generates the exact Helm command for your stack:

**grafana.com → your stack → Kubernetes tile → Start sending data**

Uses the same OTLP credentials — no new tokens needed. Run the generated command from inside the VM (SSH in first as shown above).

> **Full Auto mode:** Grafana Alloy is already deployed — no extra steps needed.

---

## Commands

| Command | What it does |
|---|---|
| `./run.sh` | Full setup — creates the VM and installs everything |
| `./run.sh --skip-vm` | Re-run setup on an existing VM (safe to run after a partial failure) |
| `./teardown.sh` | Delete the VM and all resources — stops all charges |

---

## Troubleshooting

**No data in Grafana Cloud after 5 minutes**

SSH into the VM and check the collector logs:
```bash
gcloud compute ssh YOUR_VM_NAME --project YOUR_PROJECT_ID --zone YOUR_ZONE
```
Then from inside the VM:
```bash
kubectl logs -n otel-demo -l app.kubernetes.io/component=otelcol --tail=50
```

- `401 Unauthorized` → wrong Instance ID or API Token
- `connection refused` / `404` → wrong OTLP Endpoint URL

Fix the values in `.env` and re-run `./run.sh --skip-vm` from the repo root.

**Pods stuck in `ImagePullBackOff`**

Normal on first deploy — images are large (~1 GB total) and still pulling. Check status from inside the VM:
```bash
kubectl get pods -n otel-demo
```
Wait a few minutes and run it again.

---

## Architecture

**Guided mode**
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
└──────────────────────────────────────────────────────────────────────────┘
```

**Full Auto mode** (everything above, plus)
```
┌─────────────────────────────── GCP VM ──────────────────────────────────┐
│                                                                          │
│  ┌──────────── monitoring namespace ────────────────────────────────┐   │
│  │                                                                   │   │
│  │  Grafana Alloy ──► Grafana Cloud OTLP gateway                    │   │
│  │  (cluster · node · pod metrics, pod logs, cluster events)        │   │
│  │                                                                   │   │
│  └───────────────────────────────────────────────────────────────── ┘   │
│                                                                          │
└──────────────────────────────────────────────────────────────────────────┘
```

Credentials are stored in Kubernetes Secrets — never written to values files.
