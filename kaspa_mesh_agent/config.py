# kaspa_mesh_agent/config.py
import json
from pathlib import Path
from typing import Dict

CONFIG_PATH = Path("config/testnet12.json")

def load_config() -> Dict:
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH) as f:
            return json.load(f)
    # Fallback
    return {
        "network": "testnet-12",
        "kaspa": {"liquidity_address": "kaspa:YOUR_TESTNET_ADDRESS"},
        "eth": {"htlc_contract": "0xYOUR_SEPOLIA_HTLC"},
        "pool": {"min_slip_bps": 10, "operator_cut_bps": 150},
        "ledger_path": "./lp-ledger-testnet12.json"
    }