# kaspa_mesh_agent/monitor.py
import asyncio
# ... import pool_manager

async def start_monitor(pool_manager):
    while True:
        depth = await pool_manager.get_current_depth()
        print(f"[Monitor] Current pool depth: KAS={depth['KAS']}, ETH={depth['ETH']}")
        await asyncio.sleep(30)