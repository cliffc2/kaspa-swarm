# cli-tools/eth-swap-cli/eth_swap_cli.py
import click
import json
from decimal import Decimal
from pathlib import Path
import sys

# Add shared to path
sys.path.insert(0, str(Path(__file__).parent.parent / "shared"))
from fee_engine import calculate_quote

CONFIG_PATH = Path(__file__).parent.parent.parent / "config" / "testnet12.json"


def load_config():
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH) as f:
            return json.load(f)
    return {
        "network": "testnet-12",
        "eth": {
            "rpc_url": "https://sepolia.infura.io/v3/YOUR_INFURA_KEY",
            "htlc_contract": "0xYOUR_SEPOLIA_HTLC",
        },
        "pool": {"min_slip_bps": 10, "operator_cut_bps": 150},
    }


config = load_config()


@click.group()
def cli():
    """Kaspa-ETH Swarm CLI - ETH side (Testnet-12 ready)"""
    pass


@cli.command()
@click.option("--in-asset", type=click.Choice(["KAS", "ETH"]), required=True)
@click.option("--out-asset", type=click.Choice(["KAS", "ETH"]), required=True)
@click.option("--amount", type=float, required=True)
@click.option("--json", "as_json", is_flag=True, default=True)
def quote(in_asset: str, out_asset: str, amount: float, as_json: bool):
    """Get THORChain-style quote with slip-based fee"""
    # For MVP: read pool depth from lp-ledger (we'll improve with real balances later)
    ledger = {"pool_depth": {"KAS": "50000", "ETH": "10"}}  # placeholder
    input_depth = Decimal(ledger["pool_depth"].get(in_asset, "10000"))
    output_depth = Decimal(ledger["pool_depth"].get(out_asset, "5"))

    result = calculate_quote(
        Decimal(str(amount)),
        input_depth,
        output_depth,
        config["pool"]["min_slip_bps"],
        config["pool"]["operator_cut_bps"],
    )
    if as_json:
        click.echo(json.dumps(result, indent=2))
    else:
        click.echo(result["data"])


# TODO: Add lock, claim, refund, add-liquidity, remove-liquidity, pool-depth later

if __name__ == "__main__":
    cli()
