# cli-tools/shared/kaspa_wrapper.py
import subprocess
import json
from pathlib import Path
from typing import Dict, Any

CLI_BASE = str(Path.home() / "cli-tools/bin")  # adjust to your built binaries


def run_kaspa_cli(command: list[str], network: str = "testnet-12") -> Dict[str, Any]:
    full_cmd = ["kaspa-atomic-swap-cli"] + command + ["--network", network, "--json"]
    try:
        result = subprocess.run(full_cmd, capture_output=True, text=True, timeout=30)
        return json.loads(result.stdout)
    except Exception as e:
        return {"success": False, "error": str(e)}


def run_kaswallet_cli(
    command: list[str], network: str = "testnet-12"
) -> Dict[str, Any]:
    full_cmd = ["kaswallet-cli"] + command + ["--network", network]
    try:
        result = subprocess.run(full_cmd, capture_output=True, text=True, timeout=30)
        return (
            json.loads(result.stdout)
            if result.stdout.strip().startswith("{")
            else {"success": True, "data": result.stdout.strip()}
        )
    except Exception as e:
        return {"success": False, "error": str(e)}
