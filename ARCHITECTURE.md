# Architecture — MCP Workflow Proxy

## Overview

The MCP Workflow Proxy is a **two-phase system** that transforms a raw OpenAPI spec into a lean set of semantic MCP workflow tools. The key insight is separating the expensive AI clustering work (done once, offline) from the lightweight runtime execution (done on every agent request, with zero LLM calls).

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         DESIGN TIME (once)                          │
│                                                                     │
│  OpenAPI Spec ──► parse_spec.py ──► endpoints_summary.yaml         │
│  (133 endpoints)    (Person 1)       (cleaned, token-efficient)     │
│                                              │                      │
│                                              ▼                      │
│                                       Claude LLM                    │
│                                    (clustering prompt)              │
│                                              │                      │
│                                              ▼                      │
│                                       workflows.yaml                │
│                                    (19 workflow blueprints)         │
└─────────────────────────────────────────────────────────────────────┘
                                              │
                                              │ (read at startup)
                                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         RUNTIME (every request)                     │
│                                                                     │
│  AI Agent ──► MCP Client ──► mcp_server.py ──► workflow_engine.py  │
│  (Claude,      (stdio/SSE)    (Person 4)         (Person 3)        │
│   Cursor)                     FastMCP              Reads YAML,      │
│                               22 tools             runs HTTP steps  │
│                                                          │          │
│                                                          ▼          │
│                                              Prism Mock / Real BMC  │
│                                              (localhost:4010)        │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Component Breakdown

### Phase 1 — Spec Ingestion (Person 1)

**Files:** `download_spec.py`, `parse_spec.py`, `fix_spec_for_prism.py`

| Component | Input | Output | Purpose |
|-----------|-------|--------|---------|
| `download_spec.py` | DMTF Redfish schema URLs | `specs/raw/*.yaml` | Downloads 85 schema YAML files |
| `parse_spec.py` | `specs/raw/*.yaml` | `specs/merged/full_spec.yaml`, `specs/cleaned/endpoints_summary.yaml` | Merges schemas, constructs 133 API paths, cleans for LLM |
| `fix_spec_for_prism.py` | `full_spec.yaml` | Patched spec | Removes Prism incompatibilities |

The cleaning step reduces 410,562 tokens to 38,445 — a **90.6% reduction** — before the spec even reaches the LLM. This is critical: the LLM only sees what it needs to cluster endpoints, not the full schema detail.

---

### Phase 2 — AI Clustering (Person 2)

**Files:** `workflows.yaml`, `prompts/workflow_generation_prompt.md`

This is the only point where a large LLM is called. The prompt instructs Claude to:

1. Read all 133 endpoints
2. Group them into 10–30 semantic workflows based on real IT operator mental models
3. Output a structured `workflows.yaml` with exact step definitions, conditions, loops, and variable extraction rules

**Clustering strategy:**
- **By resource domain** — Systems, Chassis, Managers, UpdateService, etc.
- **By operational intent** — monitoring vs configuration vs lifecycle vs security
- **By call sequence** — endpoints that always appear together in real tasks are grouped (e.g., list → get → act)

**Output schema per workflow:**
```yaml
- name: server_health_check
  description: "..."
  category: monitoring
  parameters: [...]
  steps:
    - step_id: get_system
      action: GET
      endpoint: /redfish/v1/Systems/{SystemId}
      extract:
        health_status: $.Status.Health
      condition:
        if: health_status != 'OK'
        then: continue
        else: goto:summary
  raw_endpoints: [...]   # full list of underlying calls
  output_template: "..."
```

---

### Phase 3 — Runtime Engine (Person 3)

**File:** `workflow_engine.py`

A pure-Python execution engine. **Zero LLM calls at runtime.** It reads `workflows.yaml` and executes workflows step-by-step:

```
run_workflow("server_health_check", {"SystemId": "Server1"})
    │
    ├─ Step 1: GET /redfish/v1/Systems          → extract system_members
    ├─ Step 2: GET /redfish/v1/Systems/Server1  → extract health_status, power_state
    ├─ Step 3: [condition] health_status != OK?
    │           YES → continue to Step 4
    │           NO  → goto:summary (skip 4, 5, 6, 7)
    ├─ Step 4: GET /Systems/Server1/Processors  → extract processor_members
    ├─ Step 5: [loop] GET each processor        → extract processor_health
    ├─ Step 6: GET /Systems/Server1/Memory      → extract memory_members
    ├─ Step 7: [loop] GET each memory module    → extract memory_health
    └─ Step 8: summary (render output_template)
```

**Engine capabilities:**
- Template resolution — `{SystemId}` → `"Server1"` in every URL
- JSONPath extraction — `$.Status.Health` pulls values from JSON responses
- Condition evaluation — `if/then/else` and `goto:step_id` branching
- Loop execution — `loop_over: members` iterates a collection, `break_if` stops early
- Error handling — per-step `on_error: continue | stop | goto:step_id`
- Variable chaining — extracted values from Step N are available in Step N+1

---

### Phase 4 — MCP Server (Person 4)

**File:** `mcp_server.py`

Wraps the engine in a [FastMCP](https://github.com/jlowin/fastmcp) server. At startup it:

1. Instantiates `WorkflowEngine` (loads `workflows.yaml`)
2. Dynamically registers one MCP tool per workflow using a factory closure (avoids Python's loop-variable capture bug)
3. Registers 3 meta-tools for hierarchical exposure

```python
# Dynamic registration — one tool per workflow
for wf in engine.list_workflows():
    fn = _make_workflow_tool(wf["name"], wf["description"], wf["parameters"])
    mcp.tool()(fn)
```

**Transport:** stdio (for Claude Desktop / Cursor). Can also run as SSE for HTTP clients.

**Hierarchical Exposure — the Tier Toggle:**

```
Normal path:    Agent calls server_health_check(params)
                └─ Engine executes 8 steps → returns aggregated result

Fallback path:  Agent calls list_raw_endpoints("server_health_check")
                └─ Returns: ["GET /redfish/v1/Systems", "GET /redfish/v1/Systems/{SystemId}", ...]
                Agent calls run_raw_endpoint("GET", "/redfish/v1/Systems/Server1")
                └─ Returns: raw HTTP response
```

This lets the agent handle edge cases without breaking the abstraction entirely.

---

### Phase 5 — Integration Layer (Person 5)

**Files:** `calculate_metrics.py`, `pitch_dashboard/index.html`, `claude_desktop_config.json`

Validates and proves the system meets acceptance criteria:

- **`calculate_metrics.py`** — computes before/after token and tool counts from the actual artifacts
- **`specs/after_metrics.json`** — serialized proof: 83.5% tool reduction, 73.2% token reduction
- **`pitch_dashboard/index.html`** — standalone HTML pitch deck with Chart.js visualizations

---

## Data Flow Diagram

```
                    DESIGN TIME
                    ───────────
DMTF Schema YAMLs
       │
       ▼
  parse_spec.py ──────────────────────────────► specs/merged/full_spec.yaml
       │                                               │
       ▼                                               ▼
specs/cleaned/                                   npx prism mock
endpoints_summary.yaml                           (mock server :4010)
       │
       ▼
 Claude LLM (1 call)
       │
       ▼
  workflows.yaml
       │
       ├──────────────────────────────────────────────┐
       │                                              │
       ▼                RUNTIME                       │
  workflow_engine.py ◄──────────────── mcp_server.py │
  (reads YAML,         registered as   (FastMCP,      │
   runs steps)         22 tools)        stdio/SSE)    │
       │                                              │
       ▼                                              │
  HTTP requests                                       │
  to :4010 (Prism)                                   │
  or real BMC                                         │
       │                                              │
       ▼                                              │
  JSON responses                                      │
  → extracted variables                               │
  → rendered output                                   │
  → returned to agent ◄─────────────────────────────-┘
```

---

## Workflow Clustering Strategy

The clustering is performed by Claude using the prompt in `prompts/workflow_generation_prompt.md`. The strategy enforces:

### 1. IT Operator Mental Models
Workflows map to what an IT operator would actually say to a colleague:
- ❌ `GET_Systems_SystemId_Processors_ProcessorId` (machine-centric)
- ✅ `server_health_check` (operator-centric)

### 2. Resource Affinity
Endpoints on the same resource tree are grouped together. Example:
```
server_health_check covers:
  /redfish/v1/Systems
  /redfish/v1/Systems/{SystemId}
  /redfish/v1/Systems/{SystemId}/Processors
  /redfish/v1/Systems/{SystemId}/Processors/{ProcessorId}
  /redfish/v1/Systems/{SystemId}/Memory
  /redfish/v1/Systems/{SystemId}/Memory/{MemoryId}
  /redfish/v1/Chassis/{ChassisId}/Thermal
```

### 3. Operational Sequence
Endpoints that are always called in sequence become a single workflow. `firmware_update` covers the full operation: check → list → get version → compare → push → poll task.

### 4. Conditional Fast-Paths
Workflows include skip/goto logic so healthy systems return after 2 calls instead of 8:
```yaml
condition:
  if: health_status != 'OK'
  then: continue       # deep-dive only when degraded
  else: goto:summary   # fast exit when healthy
```

---

## Key Trade-offs

### Trade-off 1: Static Clustering vs Dynamic
**Chosen:** Static clustering at design time (one LLM call)
**Alternative:** Dynamic clustering at request time (LLM decides which tools to combine)
**Why:** Static clustering means zero LLM overhead at runtime, fully deterministic execution, and auditable workflows. Dynamic approaches add latency, cost, and non-determinism on every request.

### Trade-off 2: Granularity of Workflows
**Chosen:** 19 workflows (average 7 endpoints each)
**Alternative:** Fewer, coarser workflows (e.g., 5) or more fine-grained (e.g., 40)
**Why:** 19 is the sweet spot — enough detail for the agent to pick the right tool, few enough to stay well within context limits. The 3 meta-tools provide a drill-down escape hatch for edge cases.

### Trade-off 3: Hierarchical Exposure vs Flat Tool Set
**Chosen:** Two-tier model — 19 high-level tools + 3 meta-tools for raw access
**Alternative:** Pure high-level only (no escape hatch)
**Why:** Production systems always have edge cases. The tier-toggle lets the AI handle novel situations without requiring a new workflow to be defined.

### Trade-off 4: YAML-driven vs Code-driven Workflows
**Chosen:** YAML blueprint (`workflows.yaml`) interpreted at runtime
**Alternative:** Hardcoded Python functions for each workflow
**Why:** YAML is human-readable, version-controllable, and editable without touching Python. A new IT operation can be added by editing the YAML — no code change required.

---

## Extensibility — Adding a New API

```
1. Place OpenAPI YAML spec in specs/raw/
2. python parse_spec.py --raw-dir specs/raw/
   → generates specs/cleaned/endpoints_summary.yaml

3. Open prompts/workflow_generation_prompt.md
   → paste contents of endpoints_summary.yaml at the bottom
   → send to Claude

4. Save Claude's output as workflows.yaml

5. python mcp_server.py
   → new workflows auto-registered as MCP tools
```

**Time: ~5 minutes.** No code changes required.

---

## Security Considerations

- The MCP server runs over stdio (local only) — no network exposure by default
- Prism mock server is local-only on `:4010`
- For production use against real BMC hardware, add Basic Auth or X-Auth-Token headers in `workflow_engine.py`'s `_http_request` method
- `workflows.yaml` acts as an allowlist — only endpoints explicitly defined in workflows can be called via the high-level tools
- `run_raw_endpoint` (the escape hatch) bypasses this allowlist — restrict or remove it in production if needed
