"""
atomic_swap.py - Wrapper for kaspa-atomic-swap-cli
Subprocess-based CLI wrapper with JSON output parsing.
"""

import subprocess
import json
from pathlib import Path
from typing import Dict, Any, Optional

CLI_PATH = Path("/usr/local/bin/kaspa-atomic-swap-cli")


class AtomicSwapError(Exception):
    pass


def run_swap_cli(
    command: list[str], network: str = "testnet-uxto", cli_path: Optional[Path] = None
) -> Dict[str, Any]:
    """Run kaspa-atomic-swap-cli command and parse JSON output."""
    path = cli_path or CLI_PATH
    full_cmd = [str(path), *command, "--network", network, "--json"]

    try:
        result = subprocess.run(full_cmd, capture_output=True, text=True, timeout=60)
        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError:
            return {
                "success": False,
                "message": "Failed to parse CLI output",
                "error": result.stderr,
            }
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "message": "CLI command timed out",
            "error": "timeout",
        }
    except FileNotFoundError:
        return {
            "success": False,
            "message": "kaspa-atomic-swap-cli not found",
            "error": "cli_not_found",
        }


def initiate_htlc(
    amount_sompi: int,
    claim_addr: str,
    secret_hash: str,
    timelock_blocks: int = 288,
    network: str = "testnet-uxto",
    from_addr: Optional[str] = None,
) -> Dict[str, Any]:
    """Initiate atomic swap with HTLC covenant."""
    cmd = [
        "initiate",
        "--amount",
        str(amount_sompi),
        "--to",
        claim_addr,
        "--secret-hash",
        secret_hash,
        "--timelock-blocks",
        str(timelock_blocks),
    ]
    if from_addr:
        cmd.extend(["--from", from_addr])
    return run_swap_cli(cmd, network)


def claim_htlc(
    utxo: str, preimage: str, network: str = "testnet-uxto"
) -> Dict[str, Any]:
    """Claim swap by revealing secret preimage."""
    cmd = ["claim", "--utxo", utxo, "--secret", preimage]
    return run_swap_cli(cmd, network)


def refund_htlc(utxo: str, network: str = "testnet-uxto") -> Dict[str, Any]:
    """Refund after timelock expires."""
    cmd = ["refund", "--utxo", utxo]
    return run_swap_cli(cmd, network)


def status_swap(txid: str, network: str = "testnet-uxto") -> Dict[str, Any]:
    """Query swap UTXO status on chain."""
    cmd = ["status", "--txid", txid]
    return run_swap_cli(cmd, network)


def monitor_swaps(
    wallet_addr: str, interval: int = 10, network: str = "testnet-uxto"
) -> Dict[str, Any]:
    """Monitor wallet for incoming swaps."""
    cmd = ["monitor", "--wallet", wallet_addr, "--interval", str(interval)]
    return run_swap_cli(cmd, network)


def show_script(
    secret_hash: str,
    timelock_blocks: int = 288,
    refund_addr: str = "",
    claim_addr: str = "",
) -> Dict[str, Any]:
    """Show covenant script for debugging."""
    cmd = [
        "show-script",
        "--secret-hash",
        secret_hash,
        "--timelock-blocks",
        str(timelock_blocks),
        "--refund-addr",
        refund_addr,
        "--claim-addr",
        claim_addr,
    ]
    return run_swap_cli(cmd)
