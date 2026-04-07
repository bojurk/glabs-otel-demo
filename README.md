# OTel Demo Lab Wizard

New to Grafana Cloud? This wizard spins up a **real, live microservices application** on GCP that automatically streams traces, metrics, and logs into your Grafana Cloud stack — so you can learn by exploring actual data instead of made-up examples.

One command. ~15 minutes. No Kubernetes experience required.

---

## What you get

A fake e-commerce store (~20 microservices) running on a GCP VM with a built-in load generator that continuously makes purchases, browses products, and triggers errors — all flowing into your Grafana Cloud stack in real time.

```
GCP VM  (e2-standard-4 · Ubuntu 22.04 · 50 GB SSD)
└── K3s (lightweight Kubernetes)
    └── otel-demo namespace
        ├── ~20 microservices  — fake e-commerce store with always-on load generator
        └── OTel Collector     — receives all app telemetry, forwards to Grafana Cloud
                                 traces · metrics · logs  (+ collector self-monitoring)
```

Everything flows to **your** Grafana Cloud stack. No in-cluster Grafana, Jaeger, or Prometheus — Grafana Cloud is the only backend.

**Cost:** ~$0.13/hr (~$3/day). Shut it down with `./teardown.sh` when you're done.

---

## What you'll be able to explore in Grafana Cloud

Once the lab is running, you can dive into:

- **Traces** — follow a single user request across all 20 microservices end-to-end
- **Metrics** — request rates, error rates, and latency for every service
- **Logs** — structured logs from every service, correlated with traces
- **Dashboards** — six pre-built dashboards covering APM, span metrics, exemplars, and more
- **Kubernetes monitoring** (optional) — add cluster/node/pod metrics with one extra step

---

## Before you start

Collect the items below **before** running the wizard so you're not hunting for values mid-setup.

### What you need

| Requirement | Notes |
|---|---|
| **macOS or Linux** | Windows: use [WSL2](https://learn.microsoft.com/en-us/windows/wsl/install) |
| **Python 3.8+** | Check: `python3 --version` |
| **gcloud CLI** | Install instructions below |
| **A GCP project** | Free tier works — you just need billing enabled |
| **A Grafana Cloud account** | Free tier at [grafana.com](https://grafana.com) |

Python packages (everything else the wizard needs) install automatically into a local virtualenv when you run `./run.sh`.

---

## Step 1 — Install gcloud

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

```bash
gcloud auth login
gcloud auth application-default login
gcloud config set project YOUR_PROJECT_ID
```

Your project ID is in the top bar of [console.cloud.google.com](https://console.cloud.google.com) — it looks like `my-project-123456`.

---

## Step 3 — Gather your Grafana Cloud credentials

The wizard will prompt you for these. Find them at **grafana.com → your org → your stack**:

| What | Where to find it |
|---|---|
| **OTLP Endpoint** | Click the **OpenTelemetry** tile → Details → **OTLP Endpoint** |
| **Instance ID** | Click the **Grafana** tile → Details → **Instance ID** (a number like `1035398`) |
| **API Token** | **Access Policies** → Create token → scopes: `metrics:write`, `logs:write`, `traces:write` |

---

## Step 4 — Run the wizard

```bash
git clone https://github.com/bojurk/glabs-otel-demo
cd glabs-otel-demo
./run.sh
```

The wizard detects your GCP project automatically, prompts for your Grafana Cloud credentials (with inline hints showing exactly where to find each value), then builds everything. **Total time: ~15 minutes.**

When it finishes, you'll see a confirmation that data is flowing into Grafana Cloud.

---

## Step 5 — Explore your data

Open **grafana.com → your stack → Launch Grafana**.

### Traces
**Drilldown → Traces** — rate, error rate, and duration for every demo microservice. No query needed.

### Metrics
**Drilldown → Metrics** — browse all metrics. Search `http_server` for OTel Demo request metrics, or `otelcol_` for collector self-monitoring.

### Logs
**Drilldown → Logs** — all services ranked by log volume. Click any service → Show logs.

### Dashboards

Six pre-built dashboards are included in `manifests/dashboards/`. Import them manually when you're ready:

**Grafana → Dashboards → New → Import → Upload JSON file**

| Dashboard | What it shows |
|---|---|
| **apm-dashboard** | RED metrics (rate, errors, duration) per service with one-click trace drilldown |
| **demo-dashboard** | Top-level store overview — throughput and latency across all services |
| **spanmetrics-dashboard** | Latency quantiles and error rates derived from trace span metrics |
| **exemplars-dashboard** | Metrics data points linked to specific traces via exemplars |
| **postgresql-dashboard** | PostgreSQL metrics from the demo's database |
| **opentelemetry-collector** | Collector health — spans received/exported, batch sizes, memory |

When importing, Grafana will prompt you to map datasources — select your Grafana Cloud Prometheus, Tempo, and Loki instances.

---

## Optional — Add Kubernetes infrastructure monitoring

Want to see cluster/node/pod metrics and logs too? Grafana Cloud has a built-in guided setup for this:

**grafana.com → your stack → Kubernetes tile → Start sending data**

It generates the exact `helm install` command with your credentials pre-filled. Uses the same OTLP endpoint — no new tokens needed.

---

## Optional — Browse the demo store

You can click around the storefront to trigger real user flows:

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
| `./run.sh --skip-vm` | Re-run setup on an existing VM (use after config changes) |
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

`ImagePullBackOff` on first deploy is normal — images are large (~1 GB total). Wait a few minutes.

**Re-run after a failure**

```bash
./run.sh --skip-vm
```

The wizard is idempotent — safe to re-run at any time.

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
└──────────────────────────────────────────────────────────────────────────┘
```

The OTel Collector is the single exit point for all app telemetry. Credentials are stored in a Kubernetes Secret — never written to values files.
