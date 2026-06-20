# PROMPT FOR CLAUDE — Workflow Generation

## How to use:
## 1. Open a new Claude chat (Claude Pro)
## 2. Paste everything below the "---START PROMPT---" line as your message
## 3. When Claude asks for the endpoint data (or in the same message), paste the contents of endpoints_summary.yaml
## 4. Claude will output workflows.yaml — save it to your project

---START PROMPT---

You are an expert API architect specializing in IT infrastructure management. I need you to analyze a Redfish API endpoint listing and group the low-level CRUD endpoints into high-level, workflow-oriented tool definitions.

## Context

I have a Redfish API (used to manage server hardware like Dell iDRAC / BMC) with 133 individual endpoints. Exposing all 133 as individual tools to an AI agent causes context window overload and poor tool selection. I need you to group them into 10-30 meaningful workflow-level tools that map to how an IT operator actually thinks and works.

## Your Task

1. Analyze all the endpoints in the data I provide below
2. Identify logical workflow groupings based on real-world IT operations
3. Output a `workflows.yaml` file in the EXACT schema format shown below

## Target Output Schema

Output valid YAML following this exact structure:

```yaml
meta:
  spec_source: "DMTF Redfish API"
  generated_by: "claude"
  total_workflows: <number>
  total_raw_endpoints: 133

workflows:
  - name: "<snake_case_workflow_name>"
    description: "<1-2 sentence description of what this workflow does, written for an IT operator>"
    category: "<one of: monitoring, configuration, maintenance, security, lifecycle, diagnostics>"
    
    parameters:
      - name: "<param_name>"
        type: "string"
        required: true/false
        description: "<what this parameter is>"
        default: "<optional default value>"
    
    steps:
      - step_id: "<unique_step_id>"
        description: "<what this step does>"
        action: "GET|POST|PATCH|DELETE"
        endpoint: "<the actual API path with {param} placeholders>"
        
        # Extract variables from the response for use in later steps
        extract:
          <variable_name>: "<JSONPath expression to extract from response>"
        
        # Optional: conditional branching
        condition:
          if: "<expression using previously extracted variables, e.g., health_status != 'OK'>"
          then: "continue"       # execute this step normally
          else: "skip"           # skip this step
          # OR use goto for branching to a specific step:
          # then: "goto:step_id_name"
          # else: "goto:another_step_id"
        
        # Optional: loop over a collection from a previous step
        loop_over: "<variable containing an array, e.g., system_members>"
        loop_variable: "<name for current item, e.g., system>"
        
        # Optional: error handling
        on_error: "continue|stop|goto:step_id"
        
        # Optional: request body for POST/PATCH
        request_body:
          <key>: "<value or {variable_reference}>"
    
    # All raw endpoints that this workflow covers (for hierarchical drill-down)
    raw_endpoints:
      - "GET /redfish/v1/Systems"
      - "GET /redfish/v1/Systems/{SystemId}"
      # ... list every endpoint this workflow touches
    
    # Expected output format returned to the user
    output_template: |
      ## <Title>
      | Property | Value |
      |----------|-------|
      | <key>    | {extracted_variable} |
```

## Rules & Constraints

1. **10-30 workflows total** — aim for around 15-20 as the sweet spot
2. **Every one of the 133 endpoints must appear in at least one workflow's `raw_endpoints` list** — no endpoint left behind
3. **Endpoints can appear in multiple workflows** — e.g., `GET /Systems/{id}` might be in both `server_health_check` and `server_inventory`
4. **Use realistic JSONPath expressions** for the `extract` fields (e.g., `$.Status.Health`, `$.PowerState`, `$.Members@odata.count`)
5. **Include conditional logic** where it makes sense (e.g., "only check thermal if health is not OK")
6. **Parameters should use the path variable names** from the endpoints (e.g., `SystemId`, `ChassisId`, `ManagerId`)
7. **Workflow names should be intuitive** for an IT operator — think about what they'd actually say: "check server health", "update firmware", "manage user accounts"
8. **Categories must be one of:** monitoring, configuration, maintenance, security, lifecycle, diagnostics
9. **Include branching and loops** — At least 3-4 workflows should have `condition` blocks with if/then/else branching. Use `loop_over` when iterating over collection members (e.g., looping through all drives, all systems). Use `goto:step_id` for non-linear flows (e.g., if firmware is already up-to-date, skip the update step). Use `on_error` for steps that might fail (e.g., continue to next drive if one drive read fails).

## Suggested Workflow Ideas (but use your judgment)

Here are some workflow concepts — you may merge, split, or add new ones:

- Server health check (system status, power state, processor/memory summary)
- Hardware inventory / asset report (list all components)
- Thermal & power monitoring (temperatures, fans, power consumption)
- Storage management (list drives, volumes, create/delete volumes)
- Firmware update workflow (check current versions, trigger update, monitor task)
- Network configuration (view/modify ethernet interfaces)
- User account management (list/create/modify/delete accounts, roles)
- Event subscription management (create/manage alert subscriptions)
- Log collection & analysis (gather logs from system, manager, chassis)
- BMC/iDRAC manager operations (reset BMC, network settings)
- Session management (create/list/delete sessions)
- Certificate management (view certs, generate CSR, replace certs)
- BIOS configuration (view/modify BIOS settings, reset to defaults)
- Secure boot management
- Virtual media operations (mount/unmount ISO images)
- Telemetry & metrics collection
- Server power operations (power on/off/restart/graceful shutdown)

## Endpoint Data

Below is the cleaned endpoint summary. Analyze it and generate the `workflows.yaml`:

<PASTE THE CONTENTS OF endpoints_summary.yaml HERE>
