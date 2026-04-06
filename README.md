# Kaspa Swarm — Autonomous KAS ↔ ETH Liquidity Engine (THORChain Style)

Autonomous AI-powered atomic swap swarm with slip-based liquidity fees, LP sharing, and mesh/WebSocket transport.

**Status**: Testnet-12 + Sepolia ready (Covenants++ testing)

## Quick Start (Testnet-12)

```bash
# 1. Clone & setup
git clone https://github.com/cliffc2/kaspa-swarm.git
cd kaspa-swarm

# 2. Build CLIs
cd cli-tools/kaspa-atomic-swap-cli && cargo build --release && cp target/release/kaspa-atomic-swap-cli ../bin/
# Build kaswallet similarly

# 3. Install Python deps
pip install -r requirements.txt   # websockets, click, web3, etc.

# 4. Update config/testnet12.json with your addresses & RPC keys

# 5. Launch
docker compose up -d
# or
python -m kaspa_mesh_agent.core --mission "Swap 500 KAS to ETH on testnet-12"