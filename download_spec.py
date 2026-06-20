"""
download_spec.py - Person 1: Download Redfish OpenAPI Specs from DMTF GitHub
=============================================================================
Downloads OpenAPI YAML files by directly constructing URLs for known resource
types and their latest versions. Avoids GitHub API rate limits by using raw
content URLs directly.

Usage:
    python download_spec.py
    python download_spec.py --output-dir ./specs/raw
"""

import os
import json
import argparse
import requests
import time
from pathlib import Path


RAW_BASE_URL = "https://raw.githubusercontent.com/DMTF/Redfish-Publications/main/openapi"

# Mapping of resource type -> (filename, latest known version)
# These are the core Redfish resource types for server/infrastructure management
# Versions verified from DMTF/Redfish-Publications repo (2024.3 release)
RESOURCE_SPECS = {
    # ---- Core System Resources ----
    "ServiceRoot":          ("ServiceRoot.v1_17_0.yaml", "v1.17.0"),
    "ComputerSystem":       ("ComputerSystem.v1_22_2.yaml", "v1.22.2"),
    "ComputerSystemCollection": ("ComputerSystemCollection.yaml", "collection"),
    "Processor":            ("Processor.v1_20_1.yaml", "v1.20.1"),
    "ProcessorCollection":  ("ProcessorCollection.yaml", "collection"),
    "Memory":               ("Memory.v1_19_1.yaml", "v1.19.1"),
    "MemoryCollection":     ("MemoryCollection.yaml", "collection"),
    
    # ---- Chassis & Physical ----
    "Chassis":              ("Chassis.v1_25_1.yaml", "v1.25.1"),
    "ChassisCollection":    ("ChassisCollection.yaml", "collection"),
    "Power":                ("Power.v1_7_2.yaml", "v1.7.2"),
    "Thermal":              ("Thermal.v1_7_2.yaml", "v1.7.2"),
    "Sensor":               ("Sensor.v1_9_1.yaml", "v1.9.1"),
    "SensorCollection":     ("SensorCollection.yaml", "collection"),
    
    # ---- Management / BMC ----
    "Manager":              ("Manager.v1_19_1.yaml", "v1.19.1"),
    "ManagerCollection":    ("ManagerCollection.yaml", "collection"),
    "ManagerAccount":       ("ManagerAccount.v1_12_1.yaml", "v1.12.1"),
    "ManagerAccountCollection": ("ManagerAccountCollection.yaml", "collection"),
    "AccountService":       ("AccountService.v1_16_0.yaml", "v1.16.0"),
    
    # ---- Networking ----
    "EthernetInterface":    ("EthernetInterface.v1_12_2.yaml", "v1.12.2"),
    "EthernetInterfaceCollection": ("EthernetInterfaceCollection.yaml", "collection"),
    "NetworkAdapter":       ("NetworkAdapter.v1_10_0.yaml", "v1.10.0"),
    "NetworkAdapterCollection": ("NetworkAdapterCollection.yaml", "collection"),
    
    # ---- Storage ----
    "Storage":              ("Storage.v1_17_0.yaml", "v1.17.0"),
    "StorageCollection":    ("StorageCollection.yaml", "collection"),
    "Drive":                ("Drive.v1_18_0.yaml", "v1.18.0"),
    "DriveCollection":      ("DriveCollection.yaml", "collection"),
    "Volume":               ("Volume.v1_10_1.yaml", "v1.10.1"),
    "VolumeCollection":     ("VolumeCollection.yaml", "collection"),
    
    # ---- Firmware / Update ----
    "UpdateService":        ("UpdateService.v1_14_0.yaml", "v1.14.0"),
    "SoftwareInventory":    ("SoftwareInventory.v1_10_2.yaml", "v1.10.2"),
    "SoftwareInventoryCollection": ("SoftwareInventoryCollection.yaml", "collection"),
    
    # ---- Events & Logs ----
    "EventService":         ("EventService.v1_10_2.yaml", "v1.10.2"),
    "EventDestination":     ("EventDestination.v1_14_1.yaml", "v1.14.1"),
    "EventDestinationCollection": ("EventDestinationCollection.yaml", "collection"),
    "LogService":           ("LogService.v1_7_0.yaml", "v1.7.0"),
    "LogServiceCollection": ("LogServiceCollection.yaml", "collection"),
    "LogEntry":             ("LogEntry.v1_16_2.yaml", "v1.16.2"),
    "LogEntryCollection":   ("LogEntryCollection.yaml", "collection"),
    
    # ---- Sessions & Security ----
    "SessionService":       ("SessionService.v1_1_9.yaml", "v1.1.9"),
    "Session":              ("Session.v1_7_1.yaml", "v1.7.1"),
    "SessionCollection":    ("SessionCollection.yaml", "collection"),
    "Certificate":          ("Certificate.v1_8_1.yaml", "v1.8.1"),
    "CertificateCollection": ("CertificateCollection.yaml", "collection"),
    "CertificateService":   ("CertificateService.v1_0_5.yaml", "v1.0.5"),
    "SecureBoot":           ("SecureBoot.v1_1_1.yaml", "v1.1.1"),
    
    # ---- Tasks ----
    "TaskService":          ("TaskService.v1_2_1.yaml", "v1.2.1"),
    "Task":                 ("Task.v1_7_4.yaml", "v1.7.4"),
    "TaskCollection":       ("TaskCollection.yaml", "collection"),
    
    # ---- BIOS & Boot ----
    "Bios":                 ("Bios.v1_2_1.yaml", "v1.2.1"),
    "BootOption":           ("BootOption.v1_0_6.yaml", "v1.0.6"),
    "BootOptionCollection": ("BootOptionCollection.yaml", "collection"),
    
    # ---- Power & Cooling (new model) ----
    "PowerSupply":          ("PowerSupply.v1_6_0.yaml", "v1.6.0"),
    "PowerSupplyCollection": ("PowerSupplyCollection.yaml", "collection"),
    "Battery":              ("Battery.v1_3_0.yaml", "v1.3.0"),
    "BatteryCollection":    ("BatteryCollection.yaml", "collection"),
    "Fan":                  ("Fan.v1_5_1.yaml", "v1.5.1"),
    "FanCollection":        ("FanCollection.yaml", "collection"),
    "EnvironmentMetrics":   ("EnvironmentMetrics.v1_3_1.yaml", "v1.3.1"),
    
    # ---- Telemetry ----
    "TelemetryService":     ("TelemetryService.v1_3_3.yaml", "v1.3.3"),
    "MetricReport":         ("MetricReport.v1_6_0.yaml", "v1.6.0"),
    "MetricReportCollection": ("MetricReportCollection.yaml", "collection"),
    "MetricDefinition":     ("MetricDefinition.v1_3_4.yaml", "v1.3.4"),
    "MetricDefinitionCollection": ("MetricDefinitionCollection.yaml", "collection"),
    
    # ---- Virtual Media ----
    "VirtualMedia":         ("VirtualMedia.v1_6_1.yaml", "v1.6.1"),
    "VirtualMediaCollection": ("VirtualMediaCollection.yaml", "collection"),
    
    # ---- Roles ----
    "Role":                 ("Role.v1_3_2.yaml", "v1.3.2"),
    "RoleCollection":       ("RoleCollection.yaml", "collection"),
    
    # ---- Assembly ----
    "Assembly":             ("Assembly.v1_5_0.yaml", "v1.5.0"),
    
    # ---- PCIe ----
    "PCIeDevice":           ("PCIeDevice.v1_14_0.yaml", "v1.14.0"),
    "PCIeDeviceCollection": ("PCIeDeviceCollection.yaml", "collection"),
    "PCIeFunction":         ("PCIeFunction.v1_6_0.yaml", "v1.6.0"),
    "PCIeFunctionCollection": ("PCIeFunctionCollection.yaml", "collection"),
    
    # ---- Misc ----
    "ActionInfo":           ("ActionInfo.v1_4_1.yaml", "v1.4.1"),
    "SimpleStorage":        ("SimpleStorage.v1_3_1.yaml", "v1.3.1"),
    "SimpleStorageCollection": ("SimpleStorageCollection.yaml", "collection"),
}


def download_with_fallback(resource: str, filename: str, output_dir: Path) -> bool:
    """
    Download a file from GitHub. If the exact version doesn't exist,
    try common earlier versions as fallback.
    """
    filepath = output_dir / filename
    
    if filepath.exists():
        return True
    
    url = f"{RAW_BASE_URL}/{filename}"
    response = requests.get(url, timeout=30)
    
    if response.status_code == 200:
        filepath.write_text(response.text, encoding="utf-8")
        return True
    
    # If not found, try fallback versions for versioned files
    if ".v" in filename:
        base_name = filename.split(".v")[0]
        # Try a range of recent versions
        for major in [1]:
            for minor in range(20, -1, -1):
                for patch in range(5, -1, -1):
                    fallback = f"{base_name}.v{major}_{minor}_{patch}.yaml"
                    fallback_url = f"{RAW_BASE_URL}/{fallback}"
                    resp = requests.get(fallback_url, timeout=10)
                    if resp.status_code == 200:
                        fallback_path = output_dir / fallback
                        fallback_path.write_text(resp.text, encoding="utf-8")
                        print(f"    (used fallback: {fallback})")
                        return True
                    time.sleep(0.1)
        
        return False
    
    return False


def main():
    parser = argparse.ArgumentParser(
        description="Download DMTF Redfish OpenAPI specs (direct URL approach)"
    )
    parser.add_argument(
        "--output-dir", "-o",
        type=str,
        default="./specs/raw",
        help="Directory to save downloaded YAML files (default: ./specs/raw)"
    )
    args = parser.parse_args()
    
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print("=" * 60)
    print("  REDFISH OPENAPI SPEC DOWNLOADER")
    print("  Person 1 - Data & Mocking Engineer")
    print("=" * 60)
    print(f"\n  Target: {len(RESOURCE_SPECS)} resource types")
    print(f"  Output: {output_dir}\n")
    
    success = 0
    failed = []
    
    for i, (resource, (filename, version)) in enumerate(RESOURCE_SPECS.items(), 1):
        print(f"  [{i}/{len(RESOURCE_SPECS)}] {resource} ({version})...", end=" ")
        
        if download_with_fallback(resource, filename, output_dir):
            print("OK")
            success += 1
        else:
            print("FAILED")
            failed.append(resource)
        
        time.sleep(0.15)  # Be nice to GitHub
    
    # Generate manifest
    manifest = {
        "source": "DMTF/Redfish-Publications",
        "download_timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "total_resource_types": len(RESOURCE_SPECS),
        "downloaded": success,
        "failed": len(failed),
        "failed_resources": failed,
        "resources": {},
    }
    
    total_size = 0
    for resource, (filename, version) in RESOURCE_SPECS.items():
        filepath = output_dir / filename
        if filepath.exists():
            size = filepath.stat().st_size
            total_size += size
            manifest["resources"][resource] = {
                "filename": filename,
                "version": version,
                "size_bytes": size,
            }
    
    manifest["total_size_bytes"] = total_size
    manifest["total_size_mb"] = round(total_size / (1024 * 1024), 2)
    
    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    
    print(f"\n{'='*60}")
    print(f"  DOWNLOAD COMPLETE")
    print(f"{'='*60}")
    print(f"  Downloaded:   {success}/{len(RESOURCE_SPECS)} resource specs")
    print(f"  Total size:   {manifest['total_size_mb']} MB")
    print(f"  Manifest:     {manifest_path}")
    if failed:
        print(f"  Failed ({len(failed)}): {', '.join(failed)}")
    print(f"{'='*60}")
    print(f"\n  Next step: Run 'python parse_spec.py' to merge and clean!")


if __name__ == "__main__":
    main()
