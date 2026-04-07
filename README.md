# OTel Lab — SE Demo Wizard

One command spins up a live OpenTelemetry + Grafana Cloud demo environment on GCP.
Pull the repo, answer a few prompts, walk away. Everything else is automated.

---

## What gets built

```
GCP VM  (e2-standard-4 · Ubuntu 22.04 · K3s)
└── otel-demo namespace
    ├── ~20 microservices  (fake e-commerce store with always-on traffic)
    └── OTel Collector     → Grafana Cloud OTLP gateway
                              metrics · traces · logs
```

---

## Before you start — one-time setup

You need three things: **gcloud CLI**, a **GCP project**, and a **Grafana Cloud account**.

### 1. Install gcloud

```bash
brew install google-cloud-sdk
```

> Don't have Homebrew? Install it first:
> `/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"`

### 2. Log in to Google Cloud

```bash
gcloud auth login
gcloud auth application-default login
```

Both commands open a browser window — sign in with your Google account and click Allow.

### 3. Set your GCP project

Find your Project ID at [console.cloud.google.com](https://console.cloud.google.com)
— it's in the top bar and looks like `my-project-123456`.

```bash
gcloud config set project YOUR_PROJECT_ID
```

> Don't have a GCP project? Create one at console.cloud.google.com → New Project.
> Make sure billing is enabled on it.

### 4. Get your Grafana Cloud credentials

You need a free account at [grafana.com](https://grafana.com). Once you have a stack:

| What | Where to find it |
|---|---|
| **Instance ID** | grafana.com → your org → your stack → Details → Instance ID (a number) |
| **API Token** | grafana.com → your org → your stack → Access Policies → Create token — set scopes: `metrics:write`, `logs:write`, `traces:write` |

Keep these handy — the wizard will ask for them.

---

## ⚠️ When you're done — stop the charges

```bash
./teardown.sh
```

This deletes the GCP VM and everything on it. You will be prompted to confirm.
The demo is gone but the repo stays — run `./run.sh` again anytime to rebuild it.

---

## Run the wizard

```bash
git clone https://github.com/YOUR_ORG/otel-lab
cd otel-lab
./run.sh
```

The wizard will:
1. Detect your GCP project automatically
2. Ask for your Grafana Cloud Instance ID and API token
3. Create a VM, install Kubernetes, deploy everything
4. Print instructions for accessing the demo when done

Total time: ~15 minutes.

---

## Commands

| Command | What it does |
|---|---|
| `./run.sh` | Full setup (use this first) |
| `./run.sh --skip-vm` | Re-run setup steps without recreating the VM |
| `./run.sh --teardown` | Delete the VM and stop all charges |

---

## Cost

~$0.13/hr (~$3/day) for the VM. Run `./run.sh --teardown` when you're done demoing.
