# kaspa_mesh_agent/tools.py
from decimal import Decimal
from liquidity_pool_manager import LiquidityPoolManager
from shared.fee_engine import calculate_quote
from shared.kaspa_wrapper import run_kaspa_cli, run_kaswallet_cli   # assume you have this

class SwarmTools:
    def __init__(self, pool_manager: LiquidityPoolManager):
        self.pool_manager = pool_manager

    async def quote(self, in_asset: str, out_asset: str, amount: float):
        depth = await self.pool_manager.get_current_depth()
        return calculate_quote(Decimal(str(amount)), depth[in_asset], depth[out_asset])

    async def add_liquidity(self, lp_key: str, kas: float, eth: float):
        return self.pool_manager.add_liquidity(lp_key, Decimal(str(kas)), Decimal(str(eth)))

    # Extend with real CLI calls as needed