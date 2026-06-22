#!/usr/bin/env python3
"""
Generates a ready-to-paste Claude Desktop config snippet
with the correct absolute paths for this machine.
Run this after setup.bat (Windows) or setup.sh (Mac/Linux) has created the venv.
"""
import json
import sys
from pathlib import Path

project_dir = Path(__file__).parent.resolve()

if sys.platform == "win32":
    python_exe = project_dir / "venv" / "Scripts" / "python.exe"
else:
    python_exe = project_dir / "venv" / "bin" / "python"

if not python_exe.exists():
    print("ERROR: venv not found. Run setup.bat (Windows) or setup.sh (Mac/Linux) first.")
    sys.exit(1)

config = {
    "mcpServers": {
        "redfish-workflow-proxy": {
            "command": str(python_exe),
            "args": [str(project_dir / "mcp_server.py")],
            "env": {}
        }
    }
}

output_path = project_dir / "claude_desktop_config_snippet.json"
with open(output_path, "w") as f:
    json.dump(config, f, indent=2)

snippet = json.dumps(config, indent=2)

print("=" * 60)
print("  Config snippet generated!")
print("=" * 60)
print()
print("1. Open your Claude Desktop config file:")
print("   Windows (standard) : %APPDATA%\\Claude\\claude_desktop_config.json")
print("   Windows (MSIX/Store): %LOCALAPPDATA%\\Packages\\Claude_pzs8sxrjxfjjc")
print("                         \\LocalCache\\Roaming\\Claude\\claude_desktop_config.json")
print("   Mac/Linux           : ~/Library/Application Support/Claude/claude_desktop_config.json")
print()
print('2. Paste the "mcpServers" block into that file, then save.')
print()
print("3. Fully restart Claude Desktop.")
print()
print("-" * 60)
print(snippet)
print("-" * 60)
print()
print(f"(Also saved to: {output_path})")
