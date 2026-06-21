import os
import re
import textwrap

import requests
import yaml

RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY", "").strip()
RAPIDAPI_HOST = os.getenv("RAPIDAPI_HOST", "google-gemini-pro.p.rapidapi.com").strip()


def _strip_code_fence(text: str) -> str:
    text = text.strip()
    if text.startswith("```yaml"):
        text = text[7:]
    elif text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    return text.strip()


def _load_workflows_document() -> dict:
    base_dir = os.path.dirname(os.path.abspath(__file__))
    workflows_path = os.path.join(base_dir, "workflows.yaml")
    with open(workflows_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _workflow_name_from_prompt(prompt: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", prompt.lower()).strip("_")
    slug = re.sub(r"_+", "_", slug)
    return f"custom_{slug[:40]}" if slug else "custom_dynamic_workflow"


def _unique_workflow_name(existing_names: set, candidate: str) -> str:
    if candidate not in existing_names:
        return candidate

    index = 2
    while f"{candidate}_{index}" in existing_names:
        index += 1
    return f"{candidate}_{index}"


def _serialize_workflow_item(workflow: dict) -> str:
    return yaml.safe_dump([workflow], sort_keys=False, default_flow_style=False).strip()


def _build_local_workflow(prompt: str) -> dict:
    prompt_lower = prompt.lower()

    if ("health" in prompt_lower or "check" in prompt_lower) and (
        "firmware" in prompt_lower or "update" in prompt_lower
    ):
        return {
            "name": "health_guarded_firmware_update",
            "category": "maintenance",
            "description": "Check server health first and only proceed with a firmware update when the system is healthy.",
            "parameters": [
                {"name": "SystemId", "type": "string", "required": True, "description": "Target system identifier."},
                {"name": "ImageURI", "type": "string", "required": True, "description": "Firmware image location."},
            ],
            "steps": [
                {
                    "step_id": "get_system_health",
                    "description": "Read the target system health status.",
                    "action": "GET",
                    "endpoint": "/redfish/v1/Systems/{SystemId}",
                    "extract": {"health_status": "$.Status.Health"},
                },
                {
                    "step_id": "simple_update",
                    "description": "Trigger the update only when the server is healthy.",
                    "action": "POST",
                    "endpoint": "/redfish/v1/UpdateService/Actions/UpdateService.SimpleUpdate",
                    "condition": {"if": "health_status == 'OK'", "then": "continue", "else": "skip"},
                    "request_body": {"ImageURI": "{ImageURI}"},
                },
                {
                    "step_id": "poll_update_service",
                    "description": "Confirm update service state after the request.",
                    "action": "GET",
                    "endpoint": "/redfish/v1/UpdateService",
                    "extract": {"service_state": "$.Status.State"},
                },
            ],
            "raw_endpoints": [
                "GET /redfish/v1/Systems/{SystemId}",
                "POST /redfish/v1/UpdateService/Actions/UpdateService.SimpleUpdate",
                "GET /redfish/v1/UpdateService",
            ],
            "output_template": """## Firmware Update\n| Property | Value |\n|----------|-------|\n| Health | {health_status} |\n| Update Service State | {service_state} |""",
        }

    if "firmware" in prompt_lower or "update" in prompt_lower:
        return {
            "name": "firmware_update_workflow",
            "category": "maintenance",
            "description": "Check the update service and trigger a firmware update request for the target server.",
            "parameters": [
                {"name": "SystemId", "type": "string", "required": True, "description": "Target system identifier."},
                {"name": "ImageURI", "type": "string", "required": True, "description": "Firmware image location."},
            ],
            "steps": [
                {
                    "step_id": "get_update_service",
                    "description": "Read the update service metadata.",
                    "action": "GET",
                    "endpoint": "/redfish/v1/UpdateService",
                    "extract": {"service_state": "$.Status.State"},
                },
                {
                    "step_id": "simple_update",
                    "description": "Submit a firmware update job.",
                    "action": "POST",
                    "endpoint": "/redfish/v1/UpdateService/Actions/UpdateService.SimpleUpdate",
                    "request_body": {"ImageURI": "{ImageURI}"},
                    "extract": {"task_uri": "$.@odata.id"},
                },
            ],
            "raw_endpoints": [
                "GET /redfish/v1/UpdateService",
                "POST /redfish/v1/UpdateService/Actions/UpdateService.SimpleUpdate",
            ],
            "output_template": """## Firmware Update\n| Property | Value |\n|----------|-------|\n| Update Service State | {service_state} |\n| Task | {task_uri} |""",
        }

    if "log" in prompt_lower or "clear" in prompt_lower:
        return {
            "name": "clear_system_logs",
            "category": "diagnostics",
            "description": "Inspect the log services and clear the selected system event log.",
            "parameters": [
                {"name": "SystemId", "type": "string", "required": True, "description": "Target system identifier."},
                {"name": "LogServiceId", "type": "string", "required": False, "description": "Log service to clear.", "default": "SystemEventLog"},
            ],
            "steps": [
                {
                    "step_id": "list_log_services",
                    "description": "List the available log services.",
                    "action": "GET",
                    "endpoint": "/redfish/v1/Systems/{SystemId}/LogServices",
                    "extract": {"log_members": "$.Members[*].@odata.id"},
                },
                {
                    "step_id": "clear_log",
                    "description": "Clear the selected log service.",
                    "action": "POST",
                    "endpoint": "/redfish/v1/Systems/{SystemId}/LogServices/{LogServiceId}/Actions/LogService.ClearLog",
                    "request_body": {},
                },
            ],
            "raw_endpoints": [
                "GET /redfish/v1/Systems/{SystemId}/LogServices",
                "POST /redfish/v1/Systems/{SystemId}/LogServices/{LogServiceId}/Actions/LogService.ClearLog",
            ],
            "output_template": """## Log Maintenance\n| Property | Value |\n|----------|-------|\n| Log Service | {LogServiceId} |""",
        }

    if "power" in prompt_lower or "restart" in prompt_lower or "shutdown" in prompt_lower:
        return {
            "name": "server_power_operations",
            "category": "lifecycle",
            "description": "Inspect the server and issue a power-control action.",
            "parameters": [
                {"name": "SystemId", "type": "string", "required": True, "description": "Target system identifier."},
                {"name": "ResetType", "type": "string", "required": False, "description": "Reset type for the power action.", "default": "GracefulRestart"},
            ],
            "steps": [
                {
                    "step_id": "get_system",
                    "description": "Read the current power state.",
                    "action": "GET",
                    "endpoint": "/redfish/v1/Systems/{SystemId}",
                    "extract": {"power_state": "$.PowerState"},
                },
                {
                    "step_id": "reset_system",
                    "description": "Issue the requested power operation.",
                    "action": "POST",
                    "endpoint": "/redfish/v1/Systems/{SystemId}/Actions/ComputerSystem.Reset",
                    "request_body": {"ResetType": "{ResetType}"},
                },
            ],
            "raw_endpoints": [
                "GET /redfish/v1/Systems/{SystemId}",
                "POST /redfish/v1/Systems/{SystemId}/Actions/ComputerSystem.Reset",
            ],
            "output_template": """## Power Operation\n| Property | Value |\n|----------|-------|\n| Power State | {power_state} |\n| Reset Type | {ResetType} |""",
        }

    if "virtual media" in prompt_lower or "iso" in prompt_lower:
        return {
            "name": "virtual_media_operations",
            "category": "lifecycle",
            "description": "Mount or unmount a virtual media image for the target system.",
            "parameters": [
                {"name": "SystemId", "type": "string", "required": True, "description": "Target system identifier."},
                {"name": "VirtualMediaId", "type": "string", "required": False, "description": "Virtual media slot to use.", "default": "CD"},
                {"name": "ImageURI", "type": "string", "required": False, "description": "Image to mount."},
            ],
            "steps": [
                {
                    "step_id": "list_virtual_media",
                    "description": "List available virtual media devices.",
                    "action": "GET",
                    "endpoint": "/redfish/v1/Systems/{SystemId}/VirtualMedia",
                    "extract": {"media_members": "$.Members[*].@odata.id"},
                },
                {
                    "step_id": "insert_media",
                    "description": "Insert the requested image.",
                    "action": "POST",
                    "endpoint": "/redfish/v1/Systems/{SystemId}/VirtualMedia/{VirtualMediaId}/Actions/VirtualMedia.InsertMedia",
                    "condition": {"if": "ImageURI != null", "then": "continue", "else": "skip"},
                    "request_body": {"Image": "{ImageURI}"},
                },
            ],
            "raw_endpoints": [
                "GET /redfish/v1/Systems/{SystemId}/VirtualMedia",
                "POST /redfish/v1/Systems/{SystemId}/VirtualMedia/{VirtualMediaId}/Actions/VirtualMedia.InsertMedia",
            ],
            "output_template": """## Virtual Media\n| Property | Value |\n|----------|-------|\n| Slot | {VirtualMediaId} |\n| Image | {ImageURI} |""",
        }

    if "bios" in prompt_lower or "boot" in prompt_lower:
        return {
            "name": "bios_configuration",
            "category": "configuration",
            "description": "Inspect BIOS settings and apply a targeted configuration change.",
            "parameters": [
                {"name": "SystemId", "type": "string", "required": True, "description": "Target system identifier."},
            ],
            "steps": [
                {
                    "step_id": "get_bios",
                    "description": "Read current BIOS settings.",
                    "action": "GET",
                    "endpoint": "/redfish/v1/Systems/{SystemId}/Bios",
                    "extract": {"bios_attributes": "$.Attributes"},
                },
                {
                    "step_id": "reset_bios",
                    "description": "Reset BIOS to defaults when requested.",
                    "action": "POST",
                    "endpoint": "/redfish/v1/Systems/{SystemId}/Bios/Actions/Bios.ResetBios",
                    "condition": {"if": "reset_requested == true", "then": "continue", "else": "skip"},
                    "request_body": {},
                },
            ],
            "raw_endpoints": [
                "GET /redfish/v1/Systems/{SystemId}/Bios",
                "POST /redfish/v1/Systems/{SystemId}/Bios/Actions/Bios.ResetBios",
            ],
            "output_template": """## BIOS Configuration\n| Property | Value |\n|----------|-------|\n| Attributes | {bios_attributes} |""",
        }

    return {
        "name": _workflow_name_from_prompt(prompt),
        "category": "diagnostics",
        "description": f"Generated workflow for: {prompt}",
        "parameters": [
            {"name": "SystemId", "type": "string", "required": True, "description": "Target system identifier."},
        ],
        "steps": [
            {
                "step_id": "get_system",
                "description": "Fetch the target system as a safe default action.",
                "action": "GET",
                "endpoint": "/redfish/v1/Systems/{SystemId}",
                "extract": {"system_health": "$.Status.Health"},
            }
        ],
        "raw_endpoints": ["GET /redfish/v1/Systems/{SystemId}"],
        "output_template": """## Custom Workflow\n| Property | Value |\n|----------|-------|\n| Health | {system_health} |""",
    }


def generate_workflow_yaml(prompt: str) -> str:
    """Generate a single YAML workflow item from a prompt."""
    system_instruction = textwrap.dedent("""
    You are an expert Redfish API automation engineer building workflows for a Model Context Protocol (MCP) server.

    You will be given the existing workflows.yaml file as context for the required syntax.
    Your task is to generate a NEW workflow item based on the user's natural language request.

    RULES:
    1. Output ONLY the raw YAML array item starting with `- name: your_workflow_name`.
    2. Do NOT wrap the output in ```yaml or any markdown blocks.
    3. The steps must use valid endpoints (e.g. /redfish/v1/Systems/{SystemId}).
    4. Follow the exact schema seen in the context.
    """)

    try:
        doc = _load_workflows_document()
        example_context = yaml.safe_dump({"workflows": doc.get("workflows", [])[:3]}, sort_keys=False)
    except Exception:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        workflows_path = os.path.join(base_dir, "workflows.yaml")
        with open(workflows_path, "r", encoding="utf-8") as f:
            example_context = f.read()[:5000]

    full_prompt = f"{system_instruction}\n\nCONTEXT (Existing Workflows):\n{example_context}\n\nUSER REQUEST:\n{prompt}\n\nNEW WORKFLOW YAML:"

    if RAPIDAPI_KEY:
        url = f"https://{RAPIDAPI_HOST}/v1/models/gemini-pro:generateContent"
        headers = {
            "x-rapidapi-key": RAPIDAPI_KEY,
            "x-rapidapi-host": RAPIDAPI_HOST,
            "Content-Type": "application/json",
        }
        payload = {
            "contents": [{"parts": [{"text": full_prompt}]}]
        }

        try:
            response = requests.post(url, json=payload, headers=headers, timeout=15)
            if response.status_code == 200:
                data = response.json()
                yaml_text = data["candidates"][0]["content"]["parts"][0]["text"]
                return _strip_code_fence(yaml_text)
            print(f"RapidAPI HTTP {response.status_code}: {response.text}")
        except Exception as e:
            print(f"LLM API Exception: {e}")

    print("Falling back to local workflow synthesis...")
    return _serialize_workflow_item(_build_local_workflow(prompt))


def append_workflow(yaml_content: str) -> bool:
    """Append a generated workflow item into the workflows list and refresh metadata."""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    workflows_path = os.path.join(base_dir, "workflows.yaml")

    try:
        raw_content = _strip_code_fence(yaml_content)
        try:
            workflow_doc = yaml.safe_load(raw_content)
        except yaml.YAMLError:
            workflow_doc = yaml.safe_load(textwrap.dedent(raw_content).strip())
        if isinstance(workflow_doc, list):
            workflow = workflow_doc[0] if workflow_doc else None
        elif isinstance(workflow_doc, dict) and "workflows" in workflow_doc:
            workflows = workflow_doc.get("workflows") or []
            workflow = workflows[0] if workflows else None
        else:
            workflow = workflow_doc

        if not isinstance(workflow, dict) or not workflow.get("name"):
            return False

        with open(workflows_path, "r", encoding="utf-8") as f:
            document = yaml.safe_load(f)

        if not isinstance(document, dict) or not isinstance(document.get("workflows"), list):
            return False

        existing_names = {item.get("name") for item in document["workflows"] if isinstance(item, dict)}
        workflow["name"] = _unique_workflow_name(existing_names, workflow["name"])
        document["workflows"].append(workflow)
        document.setdefault("meta", {})
        document["meta"]["total_workflows"] = len(document["workflows"])
        document["meta"]["total_raw_endpoints"] = sum(
            len(item.get("raw_endpoints", [])) for item in document["workflows"] if isinstance(item, dict)
        )

        with open(workflows_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(document, f, sort_keys=False, allow_unicode=False)

        return True
    except Exception as e:
        print(f"Failed to append workflow: {e}")
        return False
