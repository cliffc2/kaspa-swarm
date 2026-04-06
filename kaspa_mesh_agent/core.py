# kaspa_mesh_agent/core.py
import asyncio
import argparse
import json
from config import load_config
from liquidity_pool_manager import LiquidityPoolManager
from tools import SwarmTools
from ws_transport import WebSocketTransport
from coordinator_prompt import SYSTEM_PROMPT

class KaspaMeshAgent:
    def __init__(self, node_type: str = "coordinator", ws_uri: str = "ws://localhost:8765"):
        self.config = load_config()
        self.pool_manager = LiquidityPoolManager(config=self.config)
        self.tools = SwarmTools(self.pool_manager)
        self.node_type = node_type
        self.ws = WebSocketTransport(uri=ws_uri, node_id=node_type)

    async def start(self, mission: str = None):
        await self.ws.connect()
        print(f"Kaspa Swarm started as {self.node_type} on Testnet-12")

        if mission:
            result = await self.coordinate(mission)
            print(json.dumps(result, indent=2))

        # Start background monitor + listener
        await asyncio.gather(
            self.run_monitor(),
            self.ws.start_listener(self.handle_message)
        )

    async def coordinate(self, mission: str):
        # In real version: call OpenRouter / LLM here with SYSTEM_PROMPT + mission
        # For now simulate tool flow
        print(f"[Coordinator] Mission: {mission}")
        # Example first action
        quote_result = await self.tools.quote("KAS", "ETH", 500)
        return {
            "role": "Coordinator",
            "next_action": "quote",
            "result": quote_result,
            "reasoning": "Calculated THORChain-style slip fee on Testnet-12"
        }

    async def handle_message(self, mid: str, payload: dict):
        print(f"[WS Received] {mid}: {payload}")

    async def run_monitor(self):
        while True:
            depth = await self.pool_manager.get_current_depth()
            print(f"[Monitor] Pool → KAS: {depth['KAS']}, ETH: {depth['ETH']}")
            await asyncio.sleep(30)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--mission", type=str, help="Natural language mission")
    parser.add_argument("--node-type", default="coordinator")
    args = parser.parse_args()

    agent = KaspaMeshAgent(node_type=args.node_type)
    asyncio.run(agent.start(args.mission))