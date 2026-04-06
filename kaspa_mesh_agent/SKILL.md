# Available Skills for Kaspa-ETH Swarm (Testnet-12)

## Core Tools
- `quote(in_asset, out_asset, amount)` → Returns THORChain-style quote with liquidity fee breakdown
- `add-liquidity(lp_key, kas_amount, eth_amount)` → Add liquidity and receive pool units
- `pool-depth()` → Current pool depths and LP shares

## Kaspa Tools
- kaspa.initiate_htlc, kaspa.claim_htlc, kaspa.refund_htlc

## ETH Tools
- eth.lock, eth.claim, eth.refund

## Coordination
- generate_secret()
- monitor_swaps()

All tools return JSON. Fees are automatically handled using THORChain CLP formula.