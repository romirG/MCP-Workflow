# Workflow Definitions — MCP Workflow Proxy

> **Mapping from Raw API Endpoints to Workflow-Level MCP Tools**

This document defines the complete mapping between the 133 raw DMTF Redfish API endpoints and the 21 semantic workflow-level MCP tools exposed by the proxy. Each workflow groups related endpoints into a single, operator-centric tool that an AI agent can invoke to accomplish a complex IT task with a single call.

---

## Summary

| Metric | Value |
|--------|-------|
| **Raw API Endpoints** | 133 |
| **Workflow Tools** | 21 |
| **Meta-Tools** | 3 (`list_workflows_meta`, `list_raw_endpoints`, `run_raw_endpoint`) |
| **Total MCP Tools** | 24 |
| **Tool Reduction** | 82.0% |
| **Token Reduction** | 74.7% (12,084 → 3,058 tokens) |
| **Categories** | monitoring (5), configuration (4), security (4), maintenance (3), diagnostics (3), lifecycle (2) |

---

## Workflow Tool Catalog

### 1. `discover_service_root`

| | |
|---|---|
| **Category** | monitoring |
| **Description** | Query the Redfish service root to discover the API version and the top-level service links (Systems, Chassis, Managers, etc.). Usually the first call when connecting to a new BMC. |
| **Parameters** | *(none)* |
| **Steps** | 1 |

**Mapped Endpoints:**

| # | Method | Endpoint |
|---|--------|----------|
| 1 | `GET` | `/redfish/v1` |

---

### 2. `server_health_check`

| | |
|---|---|
| **Category** | monitoring |
| **Description** | Run a top-to-bottom health assessment of a server: overall status, power state, and processor/memory health. If overall health is not OK, it automatically drills into chassis thermal data to look for a root cause. |
| **Parameters** | `SystemId` (optional), `ChassisId` (optional) |
| **Steps** | 8 (with conditional fast-path: healthy servers exit after 2 steps) |

**Mapped Endpoints:**

| # | Method | Endpoint |
|---|--------|----------|
| 1 | `GET` | `/redfish/v1/Systems` |
| 2 | `GET` | `/redfish/v1/Systems/{SystemId}` |
| 3 | `GET` | `/redfish/v1/Systems/{SystemId}/Processors` |
| 4 | `GET` | `/redfish/v1/Systems/{SystemId}/Processors/{ProcessorId}` |
| 5 | `GET` | `/redfish/v1/Systems/{SystemId}/Memory` |
| 6 | `GET` | `/redfish/v1/Systems/{SystemId}/Memory/{MemoryId}` |
| 7 | `GET` | `/redfish/v1/Chassis/{ChassisId}/Thermal` |

**Logic:** Conditional branching — if `health_status == 'OK'`, skips deep-dive steps (3–7) and jumps directly to summary. Loop with `break_if` on processors and memory to stop scanning once a fault is found.

---

### 3. `hardware_inventory_report`

| | |
|---|---|
| **Category** | monitoring |
| **Description** | Produce a full asset/inventory report for a server: CPUs, memory, PCIe devices and their functions, network interfaces, simple storage, and chassis-level FRU/assembly and network adapter data. |
| **Parameters** | `SystemId` (required), `ChassisId` (optional) |
| **Steps** | 11 |

**Mapped Endpoints:**

| # | Method | Endpoint |
|---|--------|----------|
| 1 | `GET` | `/redfish/v1/Systems/{SystemId}` |
| 2 | `GET` | `/redfish/v1/Systems/{SystemId}/PCIeDevices` |
| 3 | `GET` | `/redfish/v1/Systems/{SystemId}/PCIeDevices/{PCIeDeviceId}` |
| 4 | `GET` | `/redfish/v1/Systems/{SystemId}/PCIeDevices/{PCIeDeviceId}/PCIeFunctions` |
| 5 | `GET` | `/redfish/v1/Systems/{SystemId}/PCIeDevices/{PCIeDeviceId}/PCIeFunctions/{FunctionId}` |
| 6 | `GET` | `/redfish/v1/Systems/{SystemId}/NetworkInterfaces` |
| 7 | `GET` | `/redfish/v1/Systems/{SystemId}/SimpleStorage` |
| 8 | `GET` | `/redfish/v1/Systems/{SystemId}/SimpleStorage/{SimpleStorageId}` |
| 9 | `GET` | `/redfish/v1/Chassis/{ChassisId}/Assembly` |
| 10 | `GET` | `/redfish/v1/Chassis/{ChassisId}/NetworkAdapters` |
| 11 | `GET` | `/redfish/v1/Chassis/{ChassisId}/NetworkAdapters/{NetworkAdapterId}` |

---

### 4. `thermal_and_power_monitoring`

| | |
|---|---|
| **Category** | monitoring |
| **Description** | Monitor environmental health of a chassis: temperatures, fans, sensors, power supplies, batteries, and aggregate power/energy consumption. Flags any component whose status is not OK. |
| **Parameters** | `ChassisId` (optional), `Detail` (optional, default: `summary`) |
| **Steps** | 17 (with conditional fast-path for healthy chassis) |

**Mapped Endpoints:**

| # | Method | Endpoint |
|---|--------|----------|
| 1 | `GET` | `/redfish/v1/Chassis` |
| 2 | `GET` | `/redfish/v1/Chassis/{ChassisId}` |
| 3 | `PATCH` | `/redfish/v1/Chassis/{ChassisId}` |
| 4 | `GET` | `/redfish/v1/Chassis/{ChassisId}/Power` |
| 5 | `PATCH` | `/redfish/v1/Chassis/{ChassisId}/Power` |
| 6 | `GET` | `/redfish/v1/Chassis/{ChassisId}/EnvironmentMetrics` |
| 7 | `GET` | `/redfish/v1/Chassis/{ChassisId}/Thermal` |
| 8 | `PATCH` | `/redfish/v1/Chassis/{ChassisId}/Thermal` |
| 9 | `GET` | `/redfish/v1/Chassis/{ChassisId}/Sensors` |
| 10 | `GET` | `/redfish/v1/Chassis/{ChassisId}/Sensors/{SensorId}` |
| 11 | `GET` | `/redfish/v1/Chassis/{ChassisId}/ThermalSubsystem/Fans` |
| 12 | `GET` | `/redfish/v1/Chassis/{ChassisId}/ThermalSubsystem/Fans/{FanId}` |
| 13 | `GET` | `/redfish/v1/Chassis/{ChassisId}/PowerSubsystem/PowerSupplies` |
| 14 | `GET` | `/redfish/v1/Chassis/{ChassisId}/PowerSubsystem/PowerSupplies/{PowerSupplyId}` |
| 15 | `GET` | `/redfish/v1/Chassis/{ChassisId}/PowerSubsystem/Batteries` |
| 16 | `GET` | `/redfish/v1/Chassis/{ChassisId}/PowerSubsystem/Batteries/{BatteryId}` |

**Logic:** Healthy chassis skips per-sensor/fan/PSU loops (goto:summary) unless `Detail='full'`.

---

### 5. `storage_management`

| | |
|---|---|
| **Category** | configuration |
| **Description** | Inventory and manage storage: enumerate storage subsystems, drives and volumes, and create, modify, or delete volumes. |
| **Parameters** | `SystemId` (required), `StorageId` (optional), `VolumeId` (optional), `ChassisId` (optional) |
| **Steps** | 10 |

**Mapped Endpoints:**

| # | Method | Endpoint |
|---|--------|----------|
| 1 | `GET` | `/redfish/v1/Systems/{SystemId}/Storage` |
| 2 | `GET` | `/redfish/v1/Systems/{SystemId}/Storage/{StorageId}` |
| 3 | `GET` | `/redfish/v1/Systems/{SystemId}/Storage/{StorageId}/Drives/{DriveId}` |
| 4 | `GET` | `/redfish/v1/Systems/{SystemId}/Storage/{StorageId}/Volumes` |
| 5 | `POST` | `/redfish/v1/Systems/{SystemId}/Storage/{StorageId}/Volumes` |
| 6 | `GET` | `/redfish/v1/Systems/{SystemId}/Storage/{StorageId}/Volumes/{VolumeId}` |
| 7 | `PATCH` | `/redfish/v1/Systems/{SystemId}/Storage/{StorageId}/Volumes/{VolumeId}` |
| 8 | `DELETE` | `/redfish/v1/Systems/{SystemId}/Storage/{StorageId}/Volumes/{VolumeId}` |
| 9 | `GET` | `/redfish/v1/Chassis/{ChassisId}/Drives` |
| 10 | `GET` | `/redfish/v1/Chassis/{ChassisId}/Drives/{DriveId}` |

---

### 6. `server_power_operations`

| | |
|---|---|
| **Category** | lifecycle |
| **Description** | Perform power control on a server (On, GracefulShutdown, ForceOff, GracefulRestart, ForceRestart). Reads current power state first and skips the reset if already in the desired state. |
| **Parameters** | `SystemId` (required), `ResetType` (required, default: `GracefulRestart`) |
| **Steps** | 3 |

**Mapped Endpoints:**

| # | Method | Endpoint |
|---|--------|----------|
| 1 | `GET` | `/redfish/v1/Systems/{SystemId}` |
| 2 | `PATCH` | `/redfish/v1/Systems/{SystemId}` |
| 3 | `POST` | `/redfish/v1/Systems/{SystemId}/Actions/ComputerSystem.Reset` |

---

### 7. `bios_configuration`

| | |
|---|---|
| **Category** | configuration |
| **Description** | View and manage BIOS: read current attributes and boot options, modify attributes, change the BIOS password, or reset BIOS to factory defaults. |
| **Parameters** | `SystemId` (required), `BootOptionId` (optional) |
| **Steps** | 6 |

**Mapped Endpoints:**

| # | Method | Endpoint |
|---|--------|----------|
| 1 | `GET` | `/redfish/v1/Systems/{SystemId}/Bios` |
| 2 | `PATCH` | `/redfish/v1/Systems/{SystemId}/Bios` |
| 3 | `POST` | `/redfish/v1/Systems/{SystemId}/Bios/Actions/Bios.ResetBios` |
| 4 | `POST` | `/redfish/v1/Systems/{SystemId}/Bios/Actions/Bios.ChangePassword` |
| 5 | `GET` | `/redfish/v1/Systems/{SystemId}/BootOptions` |
| 6 | `GET` | `/redfish/v1/Systems/{SystemId}/BootOptions/{BootOptionId}` |

---

### 8. `secure_boot_management`

| | |
|---|---|
| **Category** | security |
| **Description** | Inspect and manage UEFI Secure Boot: read enablement and key state, enable/disable Secure Boot, and reset Secure Boot keys. |
| **Parameters** | `SystemId` (required) |
| **Steps** | 3 |

**Mapped Endpoints:**

| # | Method | Endpoint |
|---|--------|----------|
| 1 | `GET` | `/redfish/v1/Systems/{SystemId}/SecureBoot` |
| 2 | `PATCH` | `/redfish/v1/Systems/{SystemId}/SecureBoot` |
| 3 | `POST` | `/redfish/v1/Systems/{SystemId}/SecureBoot/Actions/SecureBoot.ResetKeys` |

---

### 9. `firmware_update`

| | |
|---|---|
| **Category** | maintenance |
| **Description** | End-to-end firmware lifecycle: check update service status, list firmware/software inventory, compare versions, trigger an update, and poll the resulting task for completion. |
| **Parameters** | `ImageURI` (required), `TargetVersion` (optional), `SoftwareId` (optional), `TaskId` (optional) |
| **Steps** | 9 |

**Mapped Endpoints:**

| # | Method | Endpoint |
|---|--------|----------|
| 1 | `GET` | `/redfish/v1/UpdateService` |
| 2 | `PATCH` | `/redfish/v1/UpdateService` |
| 3 | `POST` | `/redfish/v1/UpdateService/Actions/UpdateService.SimpleUpdate` |
| 4 | `GET` | `/redfish/v1/UpdateService/FirmwareInventory` |
| 5 | `GET` | `/redfish/v1/UpdateService/FirmwareInventory/{SoftwareId}` |
| 6 | `GET` | `/redfish/v1/UpdateService/SoftwareInventory` |
| 7 | `GET` | `/redfish/v1/UpdateService/SoftwareInventory/{SoftwareId}` |
| 8 | `GET` | `/redfish/v1/TaskService/Tasks/{TaskId}` |

---

### 10. `network_configuration`

| | |
|---|---|
| **Category** | configuration |
| **Description** | View and configure network interfaces on both the host system and the management controller (BMC/iDRAC), plus network protocol settings (HTTPS, SSH, IPMI). |
| **Parameters** | `SystemId` (optional), `ManagerId` (optional), `InterfaceId` (optional) |
| **Steps** | 8 |

**Mapped Endpoints:**

| # | Method | Endpoint |
|---|--------|----------|
| 1 | `GET` | `/redfish/v1/Systems/{SystemId}/EthernetInterfaces` |
| 2 | `GET` | `/redfish/v1/Systems/{SystemId}/EthernetInterfaces/{InterfaceId}` |
| 3 | `PATCH` | `/redfish/v1/Systems/{SystemId}/EthernetInterfaces/{InterfaceId}` |
| 4 | `GET` | `/redfish/v1/Managers/{ManagerId}/EthernetInterfaces` |
| 5 | `GET` | `/redfish/v1/Managers/{ManagerId}/EthernetInterfaces/{InterfaceId}` |
| 6 | `PATCH` | `/redfish/v1/Managers/{ManagerId}/EthernetInterfaces/{InterfaceId}` |
| 7 | `GET` | `/redfish/v1/Managers/{ManagerId}/NetworkProtocol` |
| 8 | `PATCH` | `/redfish/v1/Managers/{ManagerId}/NetworkProtocol` |

---

### 11. `bmc_manager_operations`

| | |
|---|---|
| **Category** | maintenance |
| **Description** | Manage BMC/iDRAC controllers: list managers, read configuration, update settings, reset the BMC, or reset to factory defaults. |
| **Parameters** | `ManagerId` (optional), `ResetType` (optional) |
| **Steps** | 5 |

**Mapped Endpoints:**

| # | Method | Endpoint |
|---|--------|----------|
| 1 | `GET` | `/redfish/v1/Managers` |
| 2 | `GET` | `/redfish/v1/Managers/{ManagerId}` |
| 3 | `PATCH` | `/redfish/v1/Managers/{ManagerId}` |
| 4 | `POST` | `/redfish/v1/Managers/{ManagerId}/Actions/Manager.Reset` |
| 5 | `POST` | `/redfish/v1/Managers/{ManagerId}/Actions/Manager.ResetToDefaults` |

---

### 12. `user_account_management`

| | |
|---|---|
| **Category** | security |
| **Description** | Full CRUD on user accounts: list, create, modify, and delete BMC user accounts. Also reads role definitions and account service settings. |
| **Parameters** | `AccountId` (optional), `RoleId` (optional) |
| **Steps** | 9 |

**Mapped Endpoints:**

| # | Method | Endpoint |
|---|--------|----------|
| 1 | `GET` | `/redfish/v1/AccountService` |
| 2 | `PATCH` | `/redfish/v1/AccountService` |
| 3 | `GET` | `/redfish/v1/AccountService/Accounts` |
| 4 | `POST` | `/redfish/v1/AccountService/Accounts` |
| 5 | `GET` | `/redfish/v1/AccountService/Accounts/{AccountId}` |
| 6 | `PATCH` | `/redfish/v1/AccountService/Accounts/{AccountId}` |
| 7 | `DELETE` | `/redfish/v1/AccountService/Accounts/{AccountId}` |
| 8 | `GET` | `/redfish/v1/AccountService/Roles` |
| 9 | `GET` | `/redfish/v1/AccountService/Roles/{RoleId}` |

---

### 13. `session_management`

| | |
|---|---|
| **Category** | security |
| **Description** | Manage Redfish sessions: view service configuration, list active sessions, create new sessions (authenticate), and terminate sessions. |
| **Parameters** | `SessionId` (optional) |
| **Steps** | 6 |

**Mapped Endpoints:**

| # | Method | Endpoint |
|---|--------|----------|
| 1 | `GET` | `/redfish/v1/SessionService` |
| 2 | `PATCH` | `/redfish/v1/SessionService` |
| 3 | `GET` | `/redfish/v1/SessionService/Sessions` |
| 4 | `POST` | `/redfish/v1/SessionService/Sessions` |
| 5 | `GET` | `/redfish/v1/SessionService/Sessions/{SessionId}` |
| 6 | `DELETE` | `/redfish/v1/SessionService/Sessions/{SessionId}` |

---

### 14. `event_subscription_management`

| | |
|---|---|
| **Category** | configuration |
| **Description** | Manage event-driven alerting: configure the event service, create/modify/delete webhook subscriptions, and send test events for validation. |
| **Parameters** | `SubscriptionId` (optional) |
| **Steps** | 8 |

**Mapped Endpoints:**

| # | Method | Endpoint |
|---|--------|----------|
| 1 | `GET` | `/redfish/v1/EventService` |
| 2 | `PATCH` | `/redfish/v1/EventService` |
| 3 | `POST` | `/redfish/v1/EventService/Actions/EventService.SubmitTestEvent` |
| 4 | `GET` | `/redfish/v1/EventService/Subscriptions` |
| 5 | `POST` | `/redfish/v1/EventService/Subscriptions` |
| 6 | `GET` | `/redfish/v1/EventService/Subscriptions/{SubscriptionId}` |
| 7 | `PATCH` | `/redfish/v1/EventService/Subscriptions/{SubscriptionId}` |
| 8 | `DELETE` | `/redfish/v1/EventService/Subscriptions/{SubscriptionId}` |

---

### 15. `log_collection`

| | |
|---|---|
| **Category** | diagnostics |
| **Description** | Comprehensive log gathering across system, manager, and chassis scopes: list log services, read individual entries, and clear logs when needed. |
| **Parameters** | `SystemId` (optional), `ManagerId` (optional), `ChassisId` (optional), `LogServiceId` (optional), `EntryId` (optional) |
| **Steps** | 10 |

**Mapped Endpoints:**

| # | Method | Endpoint |
|---|--------|----------|
| 1 | `GET` | `/redfish/v1/Systems/{SystemId}/LogServices` |
| 2 | `GET` | `/redfish/v1/Systems/{SystemId}/LogServices/{LogServiceId}` |
| 3 | `GET` | `/redfish/v1/Systems/{SystemId}/LogServices/{LogServiceId}/Entries` |
| 4 | `GET` | `/redfish/v1/Systems/{SystemId}/LogServices/{LogServiceId}/Entries/{EntryId}` |
| 5 | `POST` | `/redfish/v1/Systems/{SystemId}/LogServices/{LogServiceId}/Actions/LogService.ClearLog` |
| 6 | `GET` | `/redfish/v1/Managers/{ManagerId}/LogServices` |
| 7 | `GET` | `/redfish/v1/Managers/{ManagerId}/LogServices/{LogServiceId}` |
| 8 | `GET` | `/redfish/v1/Managers/{ManagerId}/LogServices/{LogServiceId}/Entries` |
| 9 | `GET` | `/redfish/v1/Managers/{ManagerId}/LogServices/{LogServiceId}/Entries/{EntryId}` |
| 10 | `GET` | `/redfish/v1/Chassis/{ChassisId}/LogServices` |

---

### 16. `certificate_management`

| | |
|---|---|
| **Category** | security |
| **Description** | Manage TLS/SSL certificates: view the certificate service, generate Certificate Signing Requests (CSR), replace certificates, and manage per-manager certificate stores. |
| **Parameters** | `ManagerId` (optional), `CertificateId` (optional) |
| **Steps** | 6 |

**Mapped Endpoints:**

| # | Method | Endpoint |
|---|--------|----------|
| 1 | `GET` | `/redfish/v1/CertificateService` |
| 2 | `POST` | `/redfish/v1/CertificateService/Actions/CertificateService.GenerateCSR` |
| 3 | `POST` | `/redfish/v1/CertificateService/Actions/CertificateService.ReplaceCertificate` |
| 4 | `GET` | `/redfish/v1/Managers/{ManagerId}/Certificates` |
| 5 | `GET` | `/redfish/v1/Managers/{ManagerId}/Certificates/{CertificateId}` |
| 6 | `DELETE` | `/redfish/v1/Managers/{ManagerId}/Certificates/{CertificateId}` |

---

### 17. `virtual_media_operations`

| | |
|---|---|
| **Category** | lifecycle |
| **Description** | Mount and unmount virtual media (ISO images) on both system and manager scopes for remote OS installation, diagnostics boot, or firmware flashing. |
| **Parameters** | `SystemId` (optional), `ManagerId` (optional), `VirtualMediaId` (optional), `ImageURI` (optional) |
| **Steps** | 10 |

**Mapped Endpoints:**

| # | Method | Endpoint |
|---|--------|----------|
| 1 | `GET` | `/redfish/v1/Systems/{SystemId}/VirtualMedia` |
| 2 | `GET` | `/redfish/v1/Systems/{SystemId}/VirtualMedia/{VirtualMediaId}` |
| 3 | `PATCH` | `/redfish/v1/Systems/{SystemId}/VirtualMedia/{VirtualMediaId}` |
| 4 | `POST` | `/redfish/v1/Systems/{SystemId}/VirtualMedia/{VirtualMediaId}/Actions/VirtualMedia.InsertMedia` |
| 5 | `POST` | `/redfish/v1/Systems/{SystemId}/VirtualMedia/{VirtualMediaId}/Actions/VirtualMedia.EjectMedia` |
| 6 | `GET` | `/redfish/v1/Managers/{ManagerId}/VirtualMedia` |
| 7 | `GET` | `/redfish/v1/Managers/{ManagerId}/VirtualMedia/{VirtualMediaId}` |
| 8 | `PATCH` | `/redfish/v1/Managers/{ManagerId}/VirtualMedia/{VirtualMediaId}` |
| 9 | `POST` | `/redfish/v1/Managers/{ManagerId}/VirtualMedia/{VirtualMediaId}/Actions/VirtualMedia.InsertMedia` |
| 10 | `POST` | `/redfish/v1/Managers/{ManagerId}/VirtualMedia/{VirtualMediaId}/Actions/VirtualMedia.EjectMedia` |

---

### 18. `telemetry_metrics_collection`

| | |
|---|---|
| **Category** | monitoring |
| **Description** | Access the telemetry service: read metric definitions and retrieve metric reports for performance monitoring and capacity planning. |
| **Parameters** | `MetricDefinitionId` (optional), `MetricReportId` (optional) |
| **Steps** | 6 |

**Mapped Endpoints:**

| # | Method | Endpoint |
|---|--------|----------|
| 1 | `GET` | `/redfish/v1/TelemetryService` |
| 2 | `PATCH` | `/redfish/v1/TelemetryService` |
| 3 | `GET` | `/redfish/v1/TelemetryService/MetricDefinitions` |
| 4 | `GET` | `/redfish/v1/TelemetryService/MetricDefinitions/{MetricDefinitionId}` |
| 5 | `GET` | `/redfish/v1/TelemetryService/MetricReports` |
| 6 | `GET` | `/redfish/v1/TelemetryService/MetricReports/{MetricReportId}` |

---

### 19. `task_management`

| | |
|---|---|
| **Category** | diagnostics |
| **Description** | Monitor and manage long-running operations: list tasks, check progress/status of firmware updates or volume creation, and clean up completed tasks. |
| **Parameters** | `TaskId` (optional) |
| **Steps** | 4 |

**Mapped Endpoints:**

| # | Method | Endpoint |
|---|--------|----------|
| 1 | `GET` | `/redfish/v1/TaskService` |
| 2 | `GET` | `/redfish/v1/TaskService/Tasks` |
| 3 | `GET` | `/redfish/v1/TaskService/Tasks/{TaskId}` |
| 4 | `DELETE` | `/redfish/v1/TaskService/Tasks/{TaskId}` |

---

### 20. `health_guarded_firmware_update` *(Dynamically Generated)*

| | |
|---|---|
| **Category** | maintenance |
| **Description** | Check server health first and only proceed with a firmware update when the system is healthy. Generated by the Natural Language Workflow Builder. |
| **Parameters** | `SystemId` (required), `ImageURI` (required) |
| **Steps** | 3 |

**Mapped Endpoints:**

| # | Method | Endpoint |
|---|--------|----------|
| 1 | `GET` | `/redfish/v1/Systems/{SystemId}` |
| 2 | `POST` | `/redfish/v1/UpdateService/Actions/UpdateService.SimpleUpdate` |
| 3 | `GET` | `/redfish/v1/UpdateService` |

**Note:** This workflow was generated dynamically by the NL Workflow Builder (stretch goal) from the prompt: *"Create a workflow that checks server health and then updates firmware if health is good."*

---

### 21. `clear_system_logs` *(Dynamically Generated)*

| | |
|---|---|
| **Category** | diagnostics |
| **Description** | Inspect the log services and clear the selected system event log. Generated by the Natural Language Workflow Builder. |
| **Parameters** | `SystemId` (required), `LogServiceId` (optional, default: `SystemEventLog`) |
| **Steps** | 2 |

**Mapped Endpoints:**

| # | Method | Endpoint |
|---|--------|----------|
| 1 | `GET` | `/redfish/v1/Systems/{SystemId}/LogServices` |
| 2 | `POST` | `/redfish/v1/Systems/{SystemId}/LogServices/{LogServiceId}/Actions/LogService.ClearLog` |

**Note:** This workflow was generated dynamically by the NL Workflow Builder.

---

## Meta-Tools (Hierarchical Exposure)

In addition to the 21 workflow tools, the MCP server exposes **3 meta-tools** that enable hierarchical drill-down:

### `list_workflows_meta`
Returns a catalogue of all available workflow tools with name, description, category, parameters, step count, and endpoint count. The agent calls this first to understand what workflows are available.

### `list_raw_endpoints`
**Tier Toggle** — takes a workflow name and returns the list of raw Redfish API endpoints that the workflow orchestrates internally. This lets the agent "look inside" a workflow.

### `run_raw_endpoint`
**Escape Hatch** — executes a single, direct HTTP request against the Redfish server. Used when a workflow doesn't cover a specific edge case and the agent needs surgical API access.

**Usage flow:**
```
1. Agent tries:  server_health_check(params)     → works ✓
2. Edge case:    list_raw_endpoints("bios_configuration")  → sees individual endpoints
3. Surgical fix: run_raw_endpoint("PATCH", "/redfish/v1/Systems/Server1/Bios/Settings", body)
```

---

## Cross-Workflow Chaining

Several workflows include `next_workflows` suggestions that the agent can follow for multi-step IT operations:

| Source Workflow | Condition | Suggested Next | Reason |
|----------------|-----------|----------------|--------|
| `server_health_check` | `health_status != 'OK'` | `log_collection` | Pull logs to root-cause a degraded server |
| `server_health_check` | `health_status != 'OK'` | `thermal_and_power_monitoring` | Inspect full sensor/fan/PSU detail |
| `server_health_check` | `health_status == 'Warning'` | `firmware_update` | A faulty component may need firmware remediation |
| `thermal_and_power_monitoring` | `chassis_health != 'OK'` | `log_collection` | Collect chassis/manager logs when environmental fault detected |
| `storage_management` | `new_volume_uri != null` | `task_management` | Volume creation is async; track the resulting build task |
