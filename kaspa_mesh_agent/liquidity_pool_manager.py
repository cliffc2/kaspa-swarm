# kaspa_mesh_agent/liquidity_pool_manager.py
"""
THORChain-style LP manager for KaspaMeshAgent
Tracks pool depth, LP positions, fee distribution, and Mimir-style config.
Optimized for Testnet-12 + Sepolia.
"""

import json
import asyncio
from pathlib import Path
from decimal import Decimal, getcontext
from typing import Dict, Any, Optional

getcontext().prec = 28

class LiquidityPoolManager:
    def __init__(self, ledger_path: Optional[Path] = None, config: Optional[Dict] = None):
        self.config = config or {}
        default_ledger = Path("lp-ledger-testnet12.json")
        self.ledger_path = ledger_path or Path(self.config.get("ledger_path", default_ledger))
        self.ledger = self._load_ledger()

    def _load_ledger(self) -> Dict:
        if self.ledger_path.exists():
            with open(self.ledger_path) as f:
                return json.load(f)
        return {
            "total_units": "0",
            "lp_positions": {},
            "pool_depth": {"KAS": "0", "ETH": "0"},
            "config": {
                "min_slip_bps": 10,           # Floor like THORChain
                "operator_cut_bps": 150,      # 0.15% to operator
                "affiliate_cut_bps": 0,
                "max_swap_percent": 5,
            },
        }

    def _save_ledger(self):
        with open(self.ledger_path, "w") as f:
            json.dump(self.ledger, f, indent=2)

    def update_pool_depth(self, kas_balance: Decimal, eth_balance: Decimal):
        self.ledger["pool_depth"]["KAS"] = str(kas_balance.quantize(Decimal("0.00000001")))
        self.ledger["pool_depth"]["ETH"] = str(eth_balance.quantize(Decimal("0.00000001")))
        self._save_ledger()

    def get_pool_depth(self) -> Dict[str, Decimal]:
        return {
            "KAS": Decimal(self.ledger["pool_depth"]["KAS"]),
            "ETH": Decimal(self.ledger["pool_depth"]["ETH"]),
        }

    def calculate_lp_units(self, kas_added: Decimal, eth_added: Decimal) -> Decimal:
        current_kas = Decimal(self.ledger["pool_depth"]["KAS"])
        current_eth = Decimal(self.ledger["pool_depth"]["ETH"])
        current_units = Decimal(self.ledger["total_units"])

        if current_units == 0:
            # Initial liquidity uses geometric mean (THORChain style)
            new_units = (kas_added * eth_added).sqrt() * Decimal("1_000_000")
        else:
            kas_ratio = kas_added / (current_kas + kas_added) if current_kas > 0 else Decimal("0")
            eth_ratio = eth_added / (current_eth + eth_added) if current_eth > 0 else Decimal("0")
            new_units = current_units * (kas_ratio + eth_ratio) / Decimal("2")

        return new_units

    def add_liquidity(self, lp_key: str, kas_added: Decimal, eth_added: Decimal) -> Dict:
        current_kas = Decimal(self.ledger["pool_depth"]["KAS"])
        current_eth = Decimal(self.ledger["pool_depth"]["ETH"])
        current_units = Decimal(self.ledger["total_units"])

        new_units = self.calculate_lp_units(kas_added, eth_added)

        if lp_key not in self.ledger["lp_positions"]:
            self.ledger["lp_positions"][lp_key] = {
                "units": "0", "kas_deposit": "0", "eth_deposit": "0"
            }

        pos = self.ledger["lp_positions"][lp_key]
        pos["units"] = str(Decimal(pos["units"]) + new_units)
        pos["kas_deposit"] = str(Decimal(pos["kas_deposit"]) + kas_added)
        pos["eth_deposit"] = str(Decimal(pos["eth_deposit"]) + eth_added)

        # Update pool
        new_kas = current_kas + kas_added
        new_eth = current_eth + eth_added
        self.ledger["pool_depth"]["KAS"] = str(new_kas)
        self.ledger["pool_depth"]["ETH"] = str(new_eth)
        self.ledger["total_units"] = str(current_units + new_units)

        self._save_ledger()

        share_pct = (new_units / (current_units + new_units) * 100) if (current_units + new_units) > 0 else Decimal("0")

        return {
            "success": True,
            "lp_key": lp_key,
            "units_added": str(new_units.quantize(Decimal("0.000001"))),
            "total_units": str((current_units + new_units).quantize(Decimal("0.000001"))),
            "share_percent": float(share_pct.quantize(Decimal("0.01"))),
            "new_pool_depth": {"KAS": str(new_kas), "ETH": str(new_eth)},
        }

    def remove_liquidity(self, lp_key: str, percentage: int = 100) -> Dict:
        if lp_key not in self.ledger["lp_positions"]:
            return {"success": False, "error": "lp_not_found"}

        pos = self.ledger["lp_positions"][lp_key]
        units = Decimal(pos["units"])
        total_units = Decimal(self.ledger["total_units"])

        if total_units == 0:
            return {"success": False, "error": "empty_pool"}

        pct = Decimal(percentage) / Decimal("100")
        withdraw_share = (units / total_units) * pct

        kas_pool = Decimal(self.ledger["pool_depth"]["KAS"])
        eth_pool = Decimal(self.ledger["pool_depth"]["ETH"])

        kas_return = (kas_pool * withdraw_share).quantize(Decimal("0.00000001"))
        eth_return = (eth_pool * withdraw_share).quantize(Decimal("0.00000001"))

        units_to_remove = (units * pct).quantize(Decimal("0.000001"))

        # Update position
        pos["units"] = str(units - units_to_remove)
        pos["kas_deposit"] = str(Decimal(pos["kas_deposit"]) - kas_return)
        pos["eth_deposit"] = str(Decimal(pos["eth_deposit"]) - eth_return)

        self.ledger["total_units"] = str(total_units - units_to_remove)
        self.ledger["pool_depth"]["KAS"] = str(kas_pool - kas_return)
        self.ledger["pool_depth"]["ETH"] = str(eth_pool - eth_return)

        self._save_ledger()

        return {
            "success": True,
            "lp_key": lp_key,
            "percentage_withdrawn": percentage,
            "kas_returned": str(kas_return),
            "eth_returned": str(eth_return),
            "units_removed": str(units_to_remove),
            "remaining_share_percent": float((Decimal(pos["units"]) / Decimal(self.ledger["total_units"]) * 100).quantize(Decimal("0.01"))) if Decimal(self.ledger["total_units"]) > 0 else 0.0
        }

    def distribute_liquidity_fee(self, fee_amount: Decimal, asset: str) -> float:
        """Fees stay in the pool → benefits all LPs proportionally"""
        current = Decimal(self.ledger["pool_depth"][asset])
        new_depth = current + fee_amount
        self.ledger["pool_depth"][asset] = str(new_depth.quantize(Decimal("0.00000001")))
        self._save_ledger()
        return float(fee_amount)

    def update_config(self, key: str, value: int) -> Dict:
        valid = ["min_slip_bps", "operator_cut_bps", "affiliate_cut_bps", "max_swap_percent"]
        if key not in valid:
            return {"success": False, "error": "invalid_key"}
        self.ledger["config"][key] = value
        self._save_ledger()
        return {"success": True, "updated": {key: value}}

    def get_config(self) -> Dict:
        return self.ledger["config"]

    async def get_current_depth(self) -> Dict[str, Decimal]:
        return self.get_pool_depth()