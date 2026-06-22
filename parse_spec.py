"""
parse_spec.py - Person 1+2: Merge, Clean & Compress OpenAPI Specs for LLM
==========================================================================
Takes the downloaded per-resource YAML schema files and:
  1. CONSTRUCTS proper Redfish API paths from the schema definitions
  2. MERGES everything into a single consolidated OpenAPI 3.0.x spec
  3. CLEANS verbose descriptions, redundant schemas, and boilerplate
  4. COMPRESSES into a token-efficient summary for LLM consumption
  5. COUNTS tokens to establish the baseline metric

The DMTF Redfish YAML files are schema-only (no paths section).
We construct the standard Redfish URI tree based on the resource hierarchy.

Outputs:
  - specs/merged/full_spec.yaml           -> Full OpenAPI spec (for Prism mock server)
  - specs/cleaned/endpoints_summary.yaml  -> Cleaned summary (for LLM input)
  - specs/cleaned/all_endpoints.json      -> Raw endpoint listing
  - specs/baseline_metrics.json           -> Token count metrics

Usage:
    python parse_spec.py
    python parse_spec.py --raw-dir ./specs/raw
"""

import os
import re
import json
import yaml
import argparse
from pathlib import Path
from collections import defaultdict


# ============================================================================
# Redfish URI Tree - Standard paths that define the API surface
# ============================================================================
# This defines the standard Redfish resource tree with proper URI patterns.
# Each entry: (path, resource_type, methods, description)
REDFISH_PATHS = [
    # ---- Service Root ----
    ("/redfish/v1", "ServiceRoot", ["get"],
     "The service root for the Redfish service"),
    
    # ---- Computer Systems ----
    ("/redfish/v1/Systems", "ComputerSystemCollection", ["get"],
     "Collection of computer systems"),
    ("/redfish/v1/Systems/{SystemId}", "ComputerSystem", ["get", "patch"],
     "A specific computer system instance"),
    ("/redfish/v1/Systems/{SystemId}/Actions/ComputerSystem.Reset", None, ["post"],
     "Reset (reboot/power off/on) a computer system"),
    ("/redfish/v1/Systems/{SystemId}/Processors", "ProcessorCollection", ["get"],
     "Collection of processors in a system"),
    ("/redfish/v1/Systems/{SystemId}/Processors/{ProcessorId}", "Processor", ["get"],
     "A specific processor instance"),
    ("/redfish/v1/Systems/{SystemId}/Memory", "MemoryCollection", ["get"],
     "Collection of memory modules in a system"),
    ("/redfish/v1/Systems/{SystemId}/Memory/{MemoryId}", "Memory", ["get"],
     "A specific memory module instance"),
    ("/redfish/v1/Systems/{SystemId}/EthernetInterfaces", "EthernetInterfaceCollection", ["get"],
     "Collection of Ethernet interfaces in a system"),
    ("/redfish/v1/Systems/{SystemId}/EthernetInterfaces/{InterfaceId}", "EthernetInterface", ["get", "patch"],
     "A specific Ethernet interface"),
    ("/redfish/v1/Systems/{SystemId}/Storage", "StorageCollection", ["get"],
     "Collection of storage subsystems in a system"),
    ("/redfish/v1/Systems/{SystemId}/Storage/{StorageId}", "Storage", ["get"],
     "A specific storage subsystem"),
    ("/redfish/v1/Systems/{SystemId}/Storage/{StorageId}/Drives/{DriveId}", "Drive", ["get"],
     "A specific drive in a storage subsystem"),
    ("/redfish/v1/Systems/{SystemId}/Storage/{StorageId}/Volumes", "VolumeCollection", ["get", "post"],
     "Collection of volumes in a storage subsystem"),
    ("/redfish/v1/Systems/{SystemId}/Storage/{StorageId}/Volumes/{VolumeId}", "Volume", ["get", "patch", "delete"],
     "A specific volume"),
    ("/redfish/v1/Systems/{SystemId}/SimpleStorage", "SimpleStorageCollection", ["get"],
     "Collection of simple storage instances"),
    ("/redfish/v1/Systems/{SystemId}/SimpleStorage/{SimpleStorageId}", "SimpleStorage", ["get"],
     "A specific simple storage instance"),
    ("/redfish/v1/Systems/{SystemId}/NetworkInterfaces", "NetworkAdapterCollection", ["get"],
     "Collection of network interfaces"),
    ("/redfish/v1/Systems/{SystemId}/Bios", "Bios", ["get", "patch"],
     "BIOS settings for a system"),
    ("/redfish/v1/Systems/{SystemId}/Bios/Actions/Bios.ResetBios", None, ["post"],
     "Reset BIOS settings to default"),
    ("/redfish/v1/Systems/{SystemId}/Bios/Actions/Bios.ChangePassword", None, ["post"],
     "Change the BIOS password"),
    ("/redfish/v1/Systems/{SystemId}/SecureBoot", "SecureBoot", ["get", "patch"],
     "UEFI Secure Boot settings"),
    ("/redfish/v1/Systems/{SystemId}/SecureBoot/Actions/SecureBoot.ResetKeys", None, ["post"],
     "Reset Secure Boot keys"),
    ("/redfish/v1/Systems/{SystemId}/BootOptions", "BootOptionCollection", ["get"],
     "Collection of boot options"),
    ("/redfish/v1/Systems/{SystemId}/BootOptions/{BootOptionId}", "BootOption", ["get"],
     "A specific boot option"),
    ("/redfish/v1/Systems/{SystemId}/LogServices", "LogServiceCollection", ["get"],
     "Collection of log services for a system"),
    ("/redfish/v1/Systems/{SystemId}/LogServices/{LogServiceId}", "LogService", ["get"],
     "A specific log service"),
    ("/redfish/v1/Systems/{SystemId}/LogServices/{LogServiceId}/Entries", "LogEntryCollection", ["get"],
     "Collection of log entries"),
    ("/redfish/v1/Systems/{SystemId}/LogServices/{LogServiceId}/Entries/{EntryId}", "LogEntry", ["get"],
     "A specific log entry"),
    ("/redfish/v1/Systems/{SystemId}/LogServices/{LogServiceId}/Actions/LogService.ClearLog", None, ["post"],
     "Clear all log entries"),
    ("/redfish/v1/Systems/{SystemId}/VirtualMedia", "VirtualMediaCollection", ["get"],
     "Collection of virtual media"),
    ("/redfish/v1/Systems/{SystemId}/VirtualMedia/{VirtualMediaId}", "VirtualMedia", ["get", "patch"],
     "A specific virtual media device"),
    ("/redfish/v1/Systems/{SystemId}/VirtualMedia/{VirtualMediaId}/Actions/VirtualMedia.InsertMedia", None, ["post"],
     "Insert (mount) virtual media"),
    ("/redfish/v1/Systems/{SystemId}/VirtualMedia/{VirtualMediaId}/Actions/VirtualMedia.EjectMedia", None, ["post"],
     "Eject (unmount) virtual media"),
    ("/redfish/v1/Systems/{SystemId}/PCIeDevices", "PCIeDeviceCollection", ["get"],
     "Collection of PCIe devices"),
    ("/redfish/v1/Systems/{SystemId}/PCIeDevices/{PCIeDeviceId}", "PCIeDevice", ["get"],
     "A specific PCIe device"),
    ("/redfish/v1/Systems/{SystemId}/PCIeDevices/{PCIeDeviceId}/PCIeFunctions", "PCIeFunctionCollection", ["get"],
     "Collection of PCIe functions"),
    ("/redfish/v1/Systems/{SystemId}/PCIeDevices/{PCIeDeviceId}/PCIeFunctions/{FunctionId}", "PCIeFunction", ["get"],
     "A specific PCIe function"),
    
    # ---- Chassis (Physical) ----
    ("/redfish/v1/Chassis", "ChassisCollection", ["get"],
     "Collection of chassis"),
    ("/redfish/v1/Chassis/{ChassisId}", "Chassis", ["get", "patch"],
     "A specific chassis instance"),
    ("/redfish/v1/Chassis/{ChassisId}/Power", "Power", ["get", "patch"],
     "Power information for a chassis"),
    ("/redfish/v1/Chassis/{ChassisId}/Thermal", "Thermal", ["get", "patch"],
     "Thermal information for a chassis (temperatures, fans)"),
    ("/redfish/v1/Chassis/{ChassisId}/Sensors", "SensorCollection", ["get"],
     "Collection of sensors in a chassis"),
    ("/redfish/v1/Chassis/{ChassisId}/Sensors/{SensorId}", "Sensor", ["get"],
     "A specific sensor reading"),
    ("/redfish/v1/Chassis/{ChassisId}/EnvironmentMetrics", "EnvironmentMetrics", ["get"],
     "Environmental metrics (power consumption, temperature summary)"),
    ("/redfish/v1/Chassis/{ChassisId}/PowerSubsystem/PowerSupplies", "PowerSupplyCollection", ["get"],
     "Collection of power supplies"),
    ("/redfish/v1/Chassis/{ChassisId}/PowerSubsystem/PowerSupplies/{PowerSupplyId}", "PowerSupply", ["get"],
     "A specific power supply"),
    ("/redfish/v1/Chassis/{ChassisId}/PowerSubsystem/Batteries", "BatteryCollection", ["get"],
     "Collection of batteries"),
    ("/redfish/v1/Chassis/{ChassisId}/PowerSubsystem/Batteries/{BatteryId}", "Battery", ["get"],
     "A specific battery"),
    ("/redfish/v1/Chassis/{ChassisId}/ThermalSubsystem/Fans", "FanCollection", ["get"],
     "Collection of fans"),
    ("/redfish/v1/Chassis/{ChassisId}/ThermalSubsystem/Fans/{FanId}", "Fan", ["get"],
     "A specific fan"),
    ("/redfish/v1/Chassis/{ChassisId}/Assembly", "Assembly", ["get"],
     "Assembly information (FRU data)"),
    ("/redfish/v1/Chassis/{ChassisId}/NetworkAdapters", "NetworkAdapterCollection", ["get"],
     "Collection of network adapters"),
    ("/redfish/v1/Chassis/{ChassisId}/NetworkAdapters/{NetworkAdapterId}", "NetworkAdapter", ["get"],
     "A specific network adapter"),
    ("/redfish/v1/Chassis/{ChassisId}/Drives", "DriveCollection", ["get"],
     "Collection of drives in a chassis"),
    ("/redfish/v1/Chassis/{ChassisId}/Drives/{DriveId}", "Drive", ["get"],
     "A specific drive in a chassis"),
    ("/redfish/v1/Chassis/{ChassisId}/LogServices", "LogServiceCollection", ["get"],
     "Collection of log services for a chassis"),
    
    # ---- Managers (BMC/iDRAC) ----
    ("/redfish/v1/Managers", "ManagerCollection", ["get"],
     "Collection of management controllers (BMC/iDRAC)"),
    ("/redfish/v1/Managers/{ManagerId}", "Manager", ["get", "patch"],
     "A specific management controller"),
    ("/redfish/v1/Managers/{ManagerId}/Actions/Manager.Reset", None, ["post"],
     "Reset the management controller (BMC reboot)"),
    ("/redfish/v1/Managers/{ManagerId}/Actions/Manager.ResetToDefaults", None, ["post"],
     "Reset manager to factory defaults"),
    ("/redfish/v1/Managers/{ManagerId}/EthernetInterfaces", "EthernetInterfaceCollection", ["get"],
     "Collection of manager network interfaces"),
    ("/redfish/v1/Managers/{ManagerId}/EthernetInterfaces/{InterfaceId}", "EthernetInterface", ["get", "patch"],
     "A specific manager network interface"),
    ("/redfish/v1/Managers/{ManagerId}/LogServices", "LogServiceCollection", ["get"],
     "Collection of log services for a manager"),
    ("/redfish/v1/Managers/{ManagerId}/LogServices/{LogServiceId}", "LogService", ["get"],
     "A specific manager log service"),
    ("/redfish/v1/Managers/{ManagerId}/LogServices/{LogServiceId}/Entries", "LogEntryCollection", ["get"],
     "Collection of manager log entries"),
    ("/redfish/v1/Managers/{ManagerId}/LogServices/{LogServiceId}/Entries/{EntryId}", "LogEntry", ["get"],
     "A specific manager log entry"),
    ("/redfish/v1/Managers/{ManagerId}/VirtualMedia", "VirtualMediaCollection", ["get"],
     "Collection of virtual media on manager"),
    ("/redfish/v1/Managers/{ManagerId}/VirtualMedia/{VirtualMediaId}", "VirtualMedia", ["get", "patch"],
     "A specific virtual media instance on manager"),
    ("/redfish/v1/Managers/{ManagerId}/VirtualMedia/{VirtualMediaId}/Actions/VirtualMedia.InsertMedia", None, ["post"],
     "Insert virtual media on manager"),
    ("/redfish/v1/Managers/{ManagerId}/VirtualMedia/{VirtualMediaId}/Actions/VirtualMedia.EjectMedia", None, ["post"],
     "Eject virtual media on manager"),
    ("/redfish/v1/Managers/{ManagerId}/NetworkProtocol", None, ["get", "patch"],
     "Network protocol settings (HTTPS, SSH, IPMI, etc.)"),
    
    # ---- Account Service ----
    ("/redfish/v1/AccountService", "AccountService", ["get", "patch"],
     "Account service configuration"),
    ("/redfish/v1/AccountService/Accounts", "ManagerAccountCollection", ["get", "post"],
     "Collection of user accounts"),
    ("/redfish/v1/AccountService/Accounts/{AccountId}", "ManagerAccount", ["get", "patch", "delete"],
     "A specific user account"),
    ("/redfish/v1/AccountService/Roles", "RoleCollection", ["get"],
     "Collection of roles"),
    ("/redfish/v1/AccountService/Roles/{RoleId}", "Role", ["get"],
     "A specific role definition"),
    
    # ---- Session Service ----
    ("/redfish/v1/SessionService", "SessionService", ["get", "patch"],
     "Session service configuration"),
    ("/redfish/v1/SessionService/Sessions", "SessionCollection", ["get", "post"],
     "Collection of active sessions"),
    ("/redfish/v1/SessionService/Sessions/{SessionId}", "Session", ["get", "delete"],
     "A specific session"),
    
    # ---- Event Service ----
    ("/redfish/v1/EventService", "EventService", ["get", "patch"],
     "Event service configuration"),
    ("/redfish/v1/EventService/Actions/EventService.SubmitTestEvent", None, ["post"],
     "Submit a test event"),
    ("/redfish/v1/EventService/Subscriptions", "EventDestinationCollection", ["get", "post"],
     "Collection of event subscriptions"),
    ("/redfish/v1/EventService/Subscriptions/{SubscriptionId}", "EventDestination", ["get", "patch", "delete"],
     "A specific event subscription"),
    
    # ---- Update Service (Firmware) ----
    ("/redfish/v1/UpdateService", "UpdateService", ["get", "patch"],
     "Firmware update service"),
    ("/redfish/v1/UpdateService/Actions/UpdateService.SimpleUpdate", None, ["post"],
     "Trigger a simple firmware update from a URI"),
    ("/redfish/v1/UpdateService/FirmwareInventory", "SoftwareInventoryCollection", ["get"],
     "Collection of installed firmware"),
    ("/redfish/v1/UpdateService/FirmwareInventory/{SoftwareId}", "SoftwareInventory", ["get"],
     "A specific firmware inventory entry"),
    ("/redfish/v1/UpdateService/SoftwareInventory", "SoftwareInventoryCollection", ["get"],
     "Collection of installed software"),
    ("/redfish/v1/UpdateService/SoftwareInventory/{SoftwareId}", "SoftwareInventory", ["get"],
     "A specific software inventory entry"),
    
    # ---- Task Service ----
    ("/redfish/v1/TaskService", "TaskService", ["get"],
     "Task service for monitoring long-running operations"),
    ("/redfish/v1/TaskService/Tasks", "TaskCollection", ["get"],
     "Collection of tasks"),
    ("/redfish/v1/TaskService/Tasks/{TaskId}", "Task", ["get", "delete"],
     "A specific task (firmware update progress, etc.)"),
    
    # ---- Certificate Service ----
    ("/redfish/v1/CertificateService", "CertificateService", ["get"],
     "Certificate management service"),
    ("/redfish/v1/CertificateService/Actions/CertificateService.GenerateCSR", None, ["post"],
     "Generate a Certificate Signing Request"),
    ("/redfish/v1/CertificateService/Actions/CertificateService.ReplaceCertificate", None, ["post"],
     "Replace an existing certificate"),
    ("/redfish/v1/Managers/{ManagerId}/Certificates", "CertificateCollection", ["get"],
     "Collection of certificates on a manager"),
    ("/redfish/v1/Managers/{ManagerId}/Certificates/{CertificateId}", "Certificate", ["get", "delete"],
     "A specific certificate"),
    
    # ---- Telemetry ----
    ("/redfish/v1/TelemetryService", "TelemetryService", ["get", "patch"],
     "Telemetry service for metrics collection"),
    ("/redfish/v1/TelemetryService/MetricDefinitions", "MetricDefinitionCollection", ["get"],
     "Collection of metric definitions"),
    ("/redfish/v1/TelemetryService/MetricDefinitions/{MetricDefinitionId}", "MetricDefinition", ["get"],
     "A specific metric definition"),
    ("/redfish/v1/TelemetryService/MetricReports", "MetricReportCollection", ["get"],
     "Collection of metric reports"),
    ("/redfish/v1/TelemetryService/MetricReports/{MetricReportId}", "MetricReport", ["get"],
     "A specific metric report"),
]


# ============================================================================
# YAML output setup
# ============================================================================
def str_representer(dumper, data):
    if '\n' in data:
        return dumper.represent_scalar('tag:yaml.org,2002:str', data, style='|')
    return dumper.represent_scalar('tag:yaml.org,2002:str', data)

yaml.add_representer(str, str_representer)


# ============================================================================
# STEP 1: Build the full OpenAPI spec from schemas + path tree
# ============================================================================
def build_full_spec(raw_dir: Path) -> tuple:
    """
    Build a complete OpenAPI 3.0 spec by:
    1. Loading all downloaded schema YAML files
    2. Constructing paths from the REDFISH_PATHS tree
    3. Linking paths to their schema definitions
    
    Returns: (full_spec_dict, endpoint_list)
    """
    print("[1/4] Building full OpenAPI spec from schemas + path tree...")
    
    # Load all schema files
    schemas = {}
    loaded = 0
    
    yaml_files = sorted(raw_dir.glob("*.yaml"))
    for filepath in yaml_files:
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                spec = yaml.safe_load(f)
            
            if spec and isinstance(spec, dict):
                # Extract schemas from components
                if "components" in spec and "schemas" in spec["components"]:
                    for name, defn in spec["components"]["schemas"].items():
                        schemas[name] = defn
                loaded += 1
        except Exception as e:
            print(f"  WARNING: Could not parse {filepath.name}: {e}")
    
    print(f"  Loaded {loaded} schema files, {len(schemas)} schema definitions")
    
    # Build the OpenAPI paths
    paths = {}
    endpoints = []
    
    for path, resource_type, methods, description in REDFISH_PATHS:
        path_item = {}
        
        for method in methods:
            operation = {
                "summary": description,
                "description": description,
                "operationId": _make_operation_id(method, path),
                "tags": [_extract_tag(path)],
                "responses": {},
            }
            
            # Add path parameters
            params = re.findall(r'\{(\w+)\}', path)
            if params:
                operation["parameters"] = [
                    {
                        "name": p,
                        "in": "path",
                        "required": True,
                        "schema": {"type": "string"},
                        "description": f"The ID of the {_humanize(p)}"
                    }
                    for p in params
                ]
            
            # Add response schemas
            if method == "get":
                operation["responses"]["200"] = {
                    "description": f"Successful response"
                }
                if resource_type:
                    # Find the main schema for this resource
                    main_schema = _find_main_schema(resource_type, schemas)
                    if main_schema:
                        operation["responses"]["200"]["content"] = {
                            "application/json": {
                                "schema": {"$ref": f"#/components/schemas/{main_schema}"}
                            }
                        }
            elif method == "post":
                operation["responses"]["200"] = {"description": "Successful operation"}
                operation["responses"]["201"] = {"description": "Resource created"}
                operation["responses"]["202"] = {"description": "Accepted (async task started)"}
                
                if "Actions" in path:
                    # Find request body schema for actions
                    action_name = path.split("/")[-1]
                    req_schema = _find_action_request_schema(action_name, schemas)
                    if req_schema:
                        operation["requestBody"] = {
                            "required": True,
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": f"#/components/schemas/{req_schema}"}
                                }
                            }
                        }
                elif resource_type:
                    main_schema = _find_main_schema(resource_type, schemas)
                    if main_schema:
                        operation["requestBody"] = {
                            "required": True,
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": f"#/components/schemas/{main_schema}"}
                                }
                            }
                        }
            elif method in ("patch", "put"):
                operation["responses"]["200"] = {"description": "Resource updated successfully"}
                if resource_type:
                    main_schema = _find_main_schema(resource_type, schemas)
                    if main_schema:
                        operation["requestBody"] = {
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": f"#/components/schemas/{main_schema}"}
                                }
                            }
                        }
            elif method == "delete":
                operation["responses"]["200"] = {"description": "Resource deleted successfully"}
                operation["responses"]["204"] = {"description": "No content (deleted)"}
            
            # Common error responses
            operation["responses"]["404"] = {"description": "Resource not found"}
            
            path_item[method] = operation
            
            # Track endpoint for metrics
            endpoints.append({
                "method": method.upper(),
                "path": path,
                "summary": description,
                "resource_type": resource_type or "Action",
                "tags": [_extract_tag(path)],
                "parameters": [p for p in re.findall(r'\{(\w+)\}', path)],
            })
        
        paths[path] = path_item
    
    # Build the full spec
    full_spec = {
        "openapi": "3.0.3",
        "info": {
            "title": "Redfish API - Server Infrastructure Management",
            "description": (
                "Consolidated DMTF Redfish API specification for server infrastructure management. "
                "Covers systems, chassis, managers (BMC/iDRAC), storage, networking, firmware, "
                "events, and telemetry. Designed for use with Prism mock server."
            ),
            "version": "2024.3",
            "contact": {
                "name": "DMTF Redfish Forum",
                "url": "https://www.dmtf.org/standards/redfish"
            },
        },
        "servers": [
            {
                "url": "http://localhost:4010",
                "description": "Prism Mock Server (local)"
            },
            {
                "url": "https://{host}",
                "description": "Live iDRAC/BMC",
                "variables": {
                    "host": {
                        "default": "192.168.1.100",
                        "description": "iDRAC/BMC IP address"
                    }
                }
            }
        ],
        "paths": paths,
        "components": {
            "schemas": schemas,
        },
    }
    
    print(f"  Total paths: {len(paths)}")
    print(f"  Total endpoints (method+path): {len(endpoints)}")
    
    # Count by method
    method_counts = defaultdict(int)
    for ep in endpoints:
        method_counts[ep["method"]] += 1
    for m, c in sorted(method_counts.items()):
        print(f"    {m}: {c}")
    
    return full_spec, endpoints


# ============================================================================
# STEP 2: Clean and compress for LLM consumption
# ============================================================================
def clean_for_llm(endpoints: list, schemas: dict) -> dict:
    """
    Create a token-efficient summary of all endpoints.
    This is what gets fed to the LLM for workflow discovery.
    """
    print("[2/4] Cleaning and compressing for LLM input...")
    
    # Group endpoints by their top-level resource area
    groups = defaultdict(list)
    for ep in endpoints:
        tag = ep["tags"][0] if ep.get("tags") else "Other"
        groups[tag].append({
            "method": ep["method"],
            "path": ep["path"],
            "summary": ep["summary"],
        })
    
    # Extract key schema properties (simplified)
    schema_summaries = _extract_key_schemas(schemas)
    
    cleaned = {
        "metadata": {
            "title": "Redfish API Endpoint Summary for Workflow Discovery",
            "description": (
                "This is a cleaned listing of all Redfish API endpoints for a server "
                "infrastructure management system (e.g., Dell iDRAC). Each endpoint is "
                "a low-level CRUD operation. Your task is to group these into 10-30 "
                "higher-level workflow tools."
            ),
            "total_endpoints": len(endpoints),
            "total_resource_groups": len(groups),
            "resource_groups_list": sorted(groups.keys()),
        },
        "endpoints_by_resource_group": dict(groups),
        "key_schemas": schema_summaries,
        "known_actions": _extract_actions(endpoints),
    }
    
    print(f"  Cleaned endpoints: {len(endpoints)}")
    print(f"  Resource groups: {len(groups)}")
    print(f"  Key schemas extracted: {len(schema_summaries)}")
    
    return cleaned


def _extract_key_schemas(schemas: dict, max_schemas: int = 30) -> dict:
    """Extract the most important schema properties for LLM context."""
    summaries = {}
    
    # Priority schemas - the main resource types
    priority_patterns = [
        "ComputerSystem", "Chassis", "Manager", "Processor", "Memory",
        "Storage", "Drive", "Volume", "EthernetInterface", "Power",
        "Thermal", "Sensor", "UpdateService", "EventService", "LogEntry",
        "ManagerAccount", "Session", "Task", "Bios", "SecureBoot",
        "SoftwareInventory", "Certificate", "Fan", "PowerSupply",
        "VirtualMedia", "NetworkAdapter", "Battery", "EnvironmentMetrics",
    ]
    
    for pattern in priority_patterns:
        if len(summaries) >= max_schemas:
            break
        
        for name, schema in schemas.items():
            if not isinstance(schema, dict):
                continue
            
            # Match the main resource schema (e.g., ComputerSystem_v1_x_x_ComputerSystem)
            if pattern in name and name.endswith(f"_{pattern}"):
                props = schema.get("properties", {})
                if props:
                    # Extract just property names and their simple types
                    prop_summary = {}
                    for pname, pdef in props.items():
                        if pname.startswith("@odata") or pname.startswith("x-"):
                            continue
                        if isinstance(pdef, dict):
                            ptype = pdef.get("type", "")
                            if not ptype and "$ref" in pdef:
                                ref = pdef["$ref"]
                                ptype = ref.split("/")[-1] if "/" in ref else ref
                            desc = pdef.get("description", "")
                            if desc:
                                desc = desc[:80]
                            prop_summary[pname] = {
                                "type": ptype,
                                "description": desc,
                                "readOnly": pdef.get("readOnly", False),
                            }
                    
                    if prop_summary:
                        summaries[pattern] = {
                            "description": _truncate(_clean_text(schema.get("description", "")), 150),
                            "properties": prop_summary,
                        }
                        break
    
    return summaries


def _extract_actions(endpoints: list) -> list:
    """Extract all action endpoints for easy LLM reference."""
    actions = []
    for ep in endpoints:
        if "Actions" in ep["path"]:
            action_name = ep["path"].split("/")[-1]
            actions.append({
                "name": action_name,
                "method": ep["method"],
                "path": ep["path"],
                "description": ep["summary"],
            })
    return actions


# ============================================================================
# STEP 3: Token counting & metrics
# ============================================================================
def count_tokens(text: str) -> int:
    """Count tokens using tiktoken (cl100k_base encoding)."""
    try:
        import tiktoken
        enc = tiktoken.get_encoding("cl100k_base")
        return len(enc.encode(text))
    except ImportError:
        # Rough approximation: 1 token ≈ 4 characters
        return len(text) // 4


def calculate_metrics(full_spec: dict, cleaned: dict, endpoints: list) -> dict:
    """Calculate baseline metrics for the hackathon pitch."""
    print("[4/4] Calculating baseline metrics...")
    
    full_yaml = yaml.dump(full_spec, default_flow_style=False, allow_unicode=True)
    cleaned_yaml = yaml.dump(cleaned, default_flow_style=False, allow_unicode=True)
    
    full_tokens = count_tokens(full_yaml)
    cleaned_tokens = count_tokens(cleaned_yaml)
    
    endpoint_count = len(endpoints)
    target_workflows = max(10, min(30, endpoint_count // 10))
    
    metrics = {
        "raw_endpoints": endpoint_count,
        "target_workflows": target_workflows,
        "projected_tool_reduction_pct": round(100 - (target_workflows / endpoint_count * 100), 1),
        "full_spec_tokens": full_tokens,
        "full_spec_chars": len(full_yaml),
        "cleaned_summary_tokens": cleaned_tokens,
        "cleaned_summary_chars": len(cleaned_yaml),
        "token_reduction_pct": round(100 - (cleaned_tokens / max(full_tokens, 1) * 100), 1),
    }
    
    print(f"\n{'='*60}")
    print(f"  BASELINE METRICS (Hackathon Deliverable)")
    print(f"{'='*60}")
    print(f"  Raw endpoints (1:1 MCP tools):   {endpoint_count}")
    print(f"  Target workflows:                ~{target_workflows}")
    print(f"  Projected tool reduction:        {metrics['projected_tool_reduction_pct']}%")
    print(f"")
    print(f"  Full spec tokens:                {full_tokens:,}")
    print(f"  Cleaned summary tokens:          {cleaned_tokens:,}")
    print(f"  Token reduction (cleaning):      {metrics['token_reduction_pct']}%")
    print(f"")
    print(f"  Full spec size:                  {len(full_yaml):,} chars")
    print(f"  Cleaned summary size:            {len(cleaned_yaml):,} chars")
    print(f"{'='*60}")
    
    return metrics


# ============================================================================
# Helper functions
# ============================================================================
def _make_operation_id(method: str, path: str) -> str:
    """Generate a clean operationId from method + path."""
    parts = path.replace("/redfish/v1/", "").split("/")
    clean_parts = [p.replace("{", "").replace("}", "") for p in parts if p != "Actions"]
    return f"{method}_{'_'.join(clean_parts)}".lower()


def _extract_tag(path: str) -> str:
    """Extract the top-level resource tag from a path."""
    parts = path.replace("/redfish/v1/", "").split("/")
    if parts:
        return parts[0].replace("{", "").replace("}", "")
    return "Root"


def _humanize(param_name: str) -> str:
    """Convert SystemId -> system."""
    name = re.sub(r'Id$', '', param_name)
    return re.sub(r'([A-Z])', r' \1', name).strip().lower()


def _find_main_schema(resource_type: str, schemas: dict) -> str:
    """Find the main schema name for a resource type."""
    # Look for patterns like ComputerSystem_v1_x_x_ComputerSystem
    for name in schemas:
        if name.endswith(f"_{resource_type}") and resource_type in name:
            return name
    # Fallback: look for Collection patterns
    for name in schemas:
        if resource_type in name and "Collection" in name and "Collection" in resource_type:
            return name
    return None


def _find_action_request_schema(action_name: str, schemas: dict) -> str:
    """Find the request body schema for an action."""
    # Actions have schemas like ComputerSystem_v1_x_x_ResetRequestBody
    clean_action = action_name.split(".")[-1]
    for name in schemas:
        if f"{clean_action}RequestBody" in name:
            return name
    return None


def _truncate(text: str, max_len: int) -> str:
    if not text:
        return ""
    text = text.strip()
    return text[:max_len-3] + "..." if len(text) > max_len else text


def _clean_text(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r'Copyright.*?(?:\n|$)', '', text, flags=re.IGNORECASE)
    text = re.sub(r'x-longDescription.*?(?:\n|$)', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


# ============================================================================
# Main
# ============================================================================
def main():
    parser = argparse.ArgumentParser(
        description="Parse, merge, and clean Redfish OpenAPI specs for LLM consumption"
    )
    parser.add_argument(
        "--raw-dir", type=str, default="./specs/raw",
        help="Directory containing downloaded YAML files (default: ./specs/raw)"
    )
    parser.add_argument(
        "--output-dir", type=str, default="./specs",
        help="Base output directory (default: ./specs)"
    )
    args = parser.parse_args()
    
    raw_dir = Path(args.raw_dir)
    output_dir = Path(args.output_dir)
    
    print("=" * 60)
    print("  REDFISH SPEC PARSER & CLEANER")
    print("  Person 1+2 - Build, Merge, Clean")
    print("=" * 60)
    print()
    
    if not raw_dir.exists() or not list(raw_dir.glob("*.yaml")):
        print(f"ERROR: No YAML files in {raw_dir}. Run 'python download_spec.py' first!")
        return
    
    # Step 1: Build full spec from schemas + path tree
    full_spec, endpoints = build_full_spec(raw_dir)
    
    # Save full merged spec (for Prism mock server)
    merged_dir = output_dir / "merged"
    merged_dir.mkdir(parents=True, exist_ok=True)
    merged_path = merged_dir / "full_spec.yaml"
    with open(merged_path, 'w', encoding='utf-8') as f:
        yaml.dump(full_spec, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
    print(f"\n  Saved full spec: {merged_path}")
    
    # Step 2: Clean for LLM
    schemas = full_spec.get("components", {}).get("schemas", {})
    cleaned = clean_for_llm(endpoints, schemas)
    
    # Save cleaned outputs
    cleaned_dir = output_dir / "cleaned"
    cleaned_dir.mkdir(parents=True, exist_ok=True)
    
    cleaned_yaml_path = cleaned_dir / "endpoints_summary.yaml"
    with open(cleaned_yaml_path, 'w', encoding='utf-8') as f:
        yaml.dump(cleaned, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
    
    cleaned_json_path = cleaned_dir / "endpoints_summary.json"
    with open(cleaned_json_path, 'w', encoding='utf-8') as f:
        json.dump(cleaned, f, indent=2, ensure_ascii=False)
    
    endpoints_path = cleaned_dir / "all_endpoints.json"
    with open(endpoints_path, 'w', encoding='utf-8') as f:
        json.dump(endpoints, f, indent=2, ensure_ascii=False)
    
    print(f"  Saved cleaned YAML:  {cleaned_yaml_path}")
    print(f"  Saved cleaned JSON:  {cleaned_json_path}")
    print(f"  Saved endpoints:     {endpoints_path}")
    
    # Step 3: Metrics (step 3 is saving, step 4 is metrics)
    print()
    metrics = calculate_metrics(full_spec, cleaned, endpoints)
    
    metrics_path = output_dir / "baseline_metrics.json"
    with open(metrics_path, 'w', encoding='utf-8') as f:
        json.dump(metrics, f, indent=2)
    
    print(f"\n  Metrics: {metrics_path}")
    print(f"\n  OUTPUT FILES:")
    print(f"  - {merged_path}  (full spec for Prism)")
    print(f"  - {cleaned_yaml_path}  (for LLM)")
    print(f"  - {cleaned_json_path}")
    print(f"  - {endpoints_path}")
    print(f"  - {metrics_path}")
    print(f"\n  NEXT STEPS:")
    print(f"  1. Mock server:  npx @stoplight/prism-cli mock {merged_path}")
    print(f"  2. LLM workflow: python generate_workflows.py")


if __name__ == "__main__":
    main()
