# MCP Workflow Proxy — Redfish Edition

> **83.5% tool reduction · 73.2% token savings · 133 endpoints → 22 intelligent MCP tools**

A Model Context Protocol (MCP) server that transforms a raw 133-endpoint Redfish/OpenAPI spec into 19 semantic workflow tools — letting an AI agent manage entire server infrastructure with plain English, instead of wrestling with hundreds of low-level API calls.

---

## The Problem

Enterprise APIs like DMTF Redfish expose **100–500+ endpoints**. Auto-generating one MCP tool per endpoint gives an LLM agent 133 tools to reason over — causing:

- **Context overload** — tool definitions alone consume 400,000+ tokens
- **Poor tool selection** — the agent can't distinguish `GET /Systems/{id}/Processors` from `GET /Systems/{id}/Memory` without deep domain knowledge
- **Complex multi-step tasks** — a "firmware update" requires 7+ sequential API calls; the agent has to orchestrate them manually every time

## The Solution

The MCP Workflow Proxy sits between the AI agent and the raw API. It:

1. **Ingests** the OpenAPI spec and extracts all endpoints
2. **Clusters** them into semantic workflow groups using an LLM (once, at design time)
3. **Exposes** 19 high-level workflow tools via a standard MCP server
4. **Executes** multi-step workflows — with conditions, loops, and variable chaining — so the agent just calls `firmware_update` and gets back a result

```
Before:  Claude sees 133 tools  →  confused, high token cost, error-prone
After:   Claude sees 22 tools   →  clear, cheap, reliable
```

---

## Key Metrics

| Metric | Before | After | Reduction |
|--------|--------|-------|-----------|
| MCP tools exposed | 133 | 22 | **83.5% ✅** |
| Token cost (tool definitions) | 12,595 | 3,374 | **73.2% ✅** |
| Token cost (vs full spec) | 410,562 | 3,374 | **99.2%** |
| Threshold required | — | — | ≥ 80% tools, ≥ 70% tokens |

---

## Repository Structure

```
MCP-Workflow/
├── download_spec.py          # Person 1: Downloads DMTF Redfish schema YAML files
├── parse_spec.py             # Person 1: Merges + cleans 133 endpoints for LLM input
├── fix_spec_for_prism.py     # Person 1: Patches merged spec for Prism mock server
├── workflows.yaml            # Person 2: 19 workflow blueprints (AI-generated clustering)
├── workflow_engine.py        # Person 3: Runtime executor — runs HTTP chains from YAML
├── mcp_server.py             # Person 4: FastMCP server exposing 22 tools
├── calculate_metrics.py      # Person 5: Computes before/after token & tool metrics
├── claude_desktop_config.json # Person 5: Drop-in Claude Desktop config
├── pitch_dashboard/
│   └── index.html            # Person 5: Interactive hackathon pitch deck
├── prompts/
│   └── workflow_generation_prompt.md  # The exact LLM prompt used for clustering
├── specs/
│   ├── raw/                  # 85 raw DMTF Redfish YAML schema files
│   ├── merged/full_spec.yaml # Consolidated OpenAPI 3.0 spec (for Prism)
│   ├── cleaned/              # Token-efficient endpoint summaries for LLM input
│   ├── baseline_metrics.json # Before: 133 endpoints, 410,562 tokens
│   └── after_metrics.json    # After:  22 tools, 3,374 tokens
├── PERSON4_README.md         # MCP server implementation guide
├── PERSON5_README.md         # Integration + Claude Desktop setup guide
└── ARCHITECTURE.md           # System design, diagrams, trade-offs
```

---

## Quick Start

### Prerequisites

| Tool | Version | Purpose |
|------|---------|---------|
| Python | 3.10+ | Runtime |
| Node.js | 18+ | Prism mock server |

### 1. Install dependencies

```bash
pip install -r requirements.txt
pip install "mcp[cli]"
```

### 2. Start the Prism mock server (simulates real Redfish hardware)

```bash
npx @stoplight/prism-cli mock specs/merged/full_spec.yaml --port 4010
```

### 3. Run the MCP server

```bash
python mcp_server.py
```

The server starts on stdio and exposes **22 tools** to any MCP client.

### 4. Test with the MCP inspector

```bash
mcp dev mcp_server.py
```

Opens a browser UI — click any tool, fill in parameters, and hit **Run**.

---

## The 22 MCP Tools

### 19 Workflow Tools

| Tool | Category | Steps | Endpoints Covered |
|------|----------|-------|-------------------|
| `discover_service_root` | monitoring | 1 | 1 |
| `server_health_check` | monitoring | 8 | 7 |
| `hardware_inventory_report` | monitoring | 11 | 11 |
| `thermal_and_power_monitoring` | monitoring | 17 | 16 |
| `telemetry_metrics_collection` | monitoring | 6 | 6 |
| `storage_management` | configuration | 10 | 10 |
| `bios_configuration` | configuration | 6 | 6 |
| `network_configuration` | configuration | 8 | 8 |
| `event_subscription_management` | configuration | 8 | 8 |
| `server_power_operations` | lifecycle | 3 | 3 |
| `bmc_manager_operations` | lifecycle | 5 | 5 |
| `virtual_media_operations` | lifecycle | 10 | 10 |
| `task_management` | lifecycle | 4 | 4 |
| `firmware_update` | maintenance | 9 | 8 |
| `secure_boot_management` | security | 3 | 3 |
| `user_account_management` | security | 9 | 9 |
| `session_management` | security | 6 | 6 |
| `certificate_management` | security | 6 | 6 |
| `log_collection` | diagnostics | 10 | 10 |

### 3 Meta-Tools (Hierarchical Exposure)

| Tool | Purpose |
|------|---------|
| `list_workflows_meta` | Discovery — lists all 19 workflow tools with descriptions |
| `list_raw_endpoints` | Tier Toggle — reveals the underlying Redfish endpoints for any workflow |
| `run_raw_endpoint` | Escape Hatch — calls a single raw Redfish endpoint directly |

---

## Connect to Claude Desktop

Add this to your `claude_desktop_config.json` (find it at `%APPDATA%\Claude\` on Windows):

```json
{
  "mcpServers": {
    "redfish-workflow-proxy": {
      "command": "python",
      "args": ["C:\\path\\to\\MCP-Workflow\\mcp_server.py"],
      "env": {}
    }
  }
}
```

Then restart Claude Desktop. You'll see all 22 tools available. Try:

- *"Check the health of server Server1"* → invokes `server_health_check`
- *"Update firmware on my rack"* → invokes `firmware_update`
- *"Is my chassis overheating?"* → invokes `thermal_and_power_monitoring`
- *"Show me all available workflows"* → invokes `list_workflows_meta`

---

## How to Onboard a New API

1. **Download the spec** — place OpenAPI YAML files in `specs/raw/`
2. **Parse and clean** — `python parse_spec.py` → generates `specs/cleaned/endpoints_summary.yaml`
3. **Cluster with LLM** — use `prompts/workflow_generation_prompt.md` with Claude → save output as `workflows.yaml`
4. **Restart the server** — `python mcp_server.py` → new workflows auto-registered

Total time: ~5 minutes.

---

## Verify the Metrics

```bash
python calculate_metrics.py
```

Output:
```
  TOOL COUNT REDUCTION
  Before (133 raw endpoints as tools):   133
  After  (22 MCP workflow tools):         22
  Reduction:                             111 tools
  Reduction %:                           83.5%
  >=80% threshold:                       PASSES

  TOKEN REDUCTION
  Full spec tokens (baseline):           410,562
  MCP tool descriptions tokens:            3,374
  Reduction vs full spec:                 99.2%
  Reduction vs raw-as-tools:              73.2%
```

---

## Architecture

See [ARCHITECTURE.md](./ARCHITECTURE.md) for the full system design, component breakdown, workflow clustering strategy, and trade-off analysis.

---

## Pitch Deck

Open `pitch_dashboard/index.html` in any browser for the interactive hackathon presentation — animated metrics, pipeline diagrams, workflow catalog, and demo prompts.

---

## Team

Built by 5 engineers as a modular pipeline — each person's output feeds directly into the next:

| Person | Role | Deliverable |
|--------|------|-------------|
| Person 1 | Data & Mock Engineer | `download_spec.py`, `parse_spec.py`, Prism setup, baseline metrics |
| Person 2 | AI Clustering Architect | `workflows.yaml` — 19 workflow blueprints |
| Person 3 | Runtime Engine Builder | `workflow_engine.py` — HTTP execution engine |
| Person 4 | MCP Server Developer | `mcp_server.py` — 22 FastMCP tools |
| Person 5 | Integrator & Pitch Master | Metrics, dashboard, Claude Desktop config |