"""
eth-swap-cli - Ethereum HTLC Atomic Swap CLI with THORChain-style fees.
Mirrors kaspa-atomic-swap-cli interface for swarm compatibility.
All commands output JSON for agent consumption.
"""

import sys
import os
import json
import hashlib
import click
from decimal import Decimal
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent.parent / "shared"))
from fee_engine import calculate_output_with_fee, calculate_lp_units, should_stream_swap

LEDGER_PATH = Path(__file__).parent.parent.parent / "lp-ledger.json"
CONFIG_PATH = Path(__file__).parent / "config.json"


def load_config() -> dict:
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH) as f:
            return json.load(f)
    return {
        "rpc_url": os.getenv("ETH_RPC_URL", "https://sepolia.infura.io/v3/YOUR_KEY"),
        "contract_address": os.getenv(
            "HTLC_CONTRACT", "0x0000000000000000000000000000000000000000"
        ),
        "private_key": os.getenv("ETH_PRIVATE_KEY", ""),
        "fee_wallet": os.getenv("FEE_WALLET", ""),
        "min_slip_bps": 5,
        "operator_cut_bps": 150,
        "affiliate_cut_bps": 0,
        "max_swap_percent": 5,
        "network": "sepolia",
    }


def load_ledger() -> dict:
    if LEDGER_PATH.exists():
        with open(LEDGER_PATH) as f:
            return json.load(f)
    return {
        "total_units": "0",
        "lp_positions": {},
        "pool_depth": {"KAS": "0", "ETH": "0"},
        "config": {
            "min_slip_bps": 5,
            "operator_cut_bps": 150,
            "affiliate_cut_bps": 0,
            "max_swap_percent": 5,
        },
    }


def save_ledger(ledger: dict):
    LEDGER_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(LEDGER_PATH, "w") as f:
        json.dump(ledger, f, indent=2)


def response(success: bool, message: str, data: dict = None, error: str = None) -> dict:
    resp = {"success": success, "message": message}
    if data is not None:
        resp["data"] = data
    if error is not None:
        resp["error"] = error
    return resp


def print_response(resp: dict):
    print(json.dumps(resp, indent=2))


@click.group()
def cli():
    """ETH Atomic Swap CLI with THORChain-style fees"""
    pass


@cli.command()
@click.option("--in-asset", required=True, type=click.Choice(["KAS", "ETH"]))
@click.option("--out-asset", required=True, type=click.Choice(["KAS", "ETH"]))
@click.option("--amount", required=True, type=str)
@click.option("--affiliate", default=None, type=str)
def quote(in_asset: str, out_asset: str, amount: str, affiliate: Optional[str]):
    """Get THORChain-style quote with slip-based fees"""
    config = load_config()
    ledger = load_ledger()

    input_depth = Decimal(ledger["pool_depth"].get(in_asset, "0"))
    output_depth = Decimal(ledger["pool_depth"].get(out_asset, "0"))
    amount_dec = Decimal(amount)

    if input_depth == 0 or output_depth == 0:
        print_response(
            response(False, "Pool has no liquidity", error="insufficient_liquidity")
        )
        return

    affiliate_bps = config["affiliate_cut_bps"] if affiliate else 0

    calc = calculate_output_with_fee(
        amount_dec,
        input_depth,
        output_depth,
        min_slip_bps=config["min_slip_bps"],
        operator_cut_bps=config["operator_cut_bps"],
        affiliate_cut_bps=affiliate_bps,
    )

    stream, chunks = should_stream_swap(
        amount_dec, input_depth, config["max_swap_percent"]
    )

    data = {
        "input_asset": in_asset,
        "output_asset": out_asset,
        "input_amount": str(amount_dec),
        "expected_output": calc["expected_output"],
        "liquidity_fee": calc["liquidity_fee"],
        "operator_cut": calc["operator_cut"],
        "affiliate_cut": calc["affiliate_cut"],
        "lp_fee": calc["lp_fee"],
        "slip_bps": calc["slip_bps"],
        "total_fee_bps": calc["total_fee_bps"],
        "price_impact": calc["price_impact"],
        "pool_depth_input": str(input_depth),
        "pool_depth_output": str(output_depth),
        "should_stream": stream,
        "stream_chunks": chunks if stream else 1,
        "affiliate_address": affiliate,
    }

    print_response(response(True, "Quote calculated", data))


@cli.command()
@click.option("--from-asset", required=True, type=click.Choice(["KAS", "ETH"]))
@click.option("--to-asset", required=True, type=click.Choice(["KAS", "ETH"]))
@click.option("--amount", required=True, type=str)
@click.option("--secret-hash", required=True, type=str)
@click.option("--counterparty", required=True, type=str)
@click.option("--timelock", default=14400, type=int)
@click.option("--affiliate", default=None, type=str)
def swap(
    from_asset: str,
    to_asset: str,
    amount: str,
    secret_hash: str,
    counterparty: str,
    timelock: int,
    affiliate: Optional[str],
):
    """Execute atomic swap with fee deduction"""
    config = load_config()
    ledger = load_ledger()

    input_depth = Decimal(ledger["pool_depth"].get(from_asset, "0"))
    output_depth = Decimal(ledger["pool_depth"].get(to_asset, "0"))
    amount_dec = Decimal(amount)

    if input_depth == 0 or output_depth == 0:
        print_response(response(False, "No liquidity", error="insufficient_liquidity"))
        return

    affiliate_bps = config["affiliate_cut_bps"] if affiliate else 0
    calc = calculate_output_with_fee(
        amount_dec,
        input_depth,
        output_depth,
        min_slip_bps=config["min_slip_bps"],
        operator_cut_bps=config["operator_cut_bps"],
        affiliate_cut_bps=affiliate_bps,
    )

    data = {
        "from_asset": from_asset,
        "to_asset": to_asset,
        "input_amount": str(amount_dec),
        "output_amount": calc["expected_output"],
        "secret_hash": secret_hash,
        "counterparty": counterparty,
        "timelock": timelock,
        "liquidity_fee": calc["liquidity_fee"],
        "total_fee_bps": calc["total_fee_bps"],
        "action": "lock_htlc",
        "status": "ready_to_lock",
    }

    print_response(response(True, "Swap prepared - lock HTLC on chain", data))


@cli.command()
@click.option("--kas-amount", required=True, type=str)
@click.option("--eth-amount", required=True, type=str)
@click.option("--lp-address", required=True, type=str)
@click.option("--asym", is_flag=True, default=False)
def add_liquidity(kas_amount: str, eth_amount: str, lp_address: str, asym: bool):
    """Add liquidity to pool and receive LP units"""
    ledger = load_ledger()

    kas_dec = Decimal(kas_amount)
    eth_dec = Decimal(eth_amount)

    current_kas = Decimal(ledger["pool_depth"]["KAS"])
    current_eth = Decimal(ledger["pool_depth"]["ETH"])
    current_units = Decimal(ledger["total_units"])

    new_units = calculate_lp_units(
        kas_dec, eth_dec, current_kas, current_eth, current_units
    )

    if lp_address not in ledger["lp_positions"]:
        ledger["lp_positions"][lp_address] = {
            "units": "0",
            "kas_deposit": "0",
            "eth_deposit": "0",
        }

    pos = ledger["lp_positions"][lp_address]
    pos["units"] = str(Decimal(pos["units"]) + new_units)
    pos["kas_deposit"] = str(Decimal(pos["kas_deposit"]) + kas_dec)
    pos["eth_deposit"] = str(Decimal(pos["eth_deposit"]) + eth_dec)

    ledger["total_units"] = str(current_units + new_units)
    ledger["pool_depth"]["KAS"] = str(current_kas + kas_dec)
    ledger["pool_depth"]["ETH"] = str(current_eth + eth_dec)

    save_ledger(ledger)

    total_units = current_units + new_units
    share_pct = (new_units / total_units * 100) if total_units > 0 else 0

    data = {
        "lp_address": lp_address,
        "units_added": str(new_units),
        "total_units": str(total_units),
        "share_percent": str(share_pct.quantize(Decimal("0.01"))),
        "kas_added": str(kas_dec),
        "eth_added": str(eth_dec),
        "new_pool_depth": {
            "KAS": str(current_kas + kas_dec),
            "ETH": str(current_eth + eth_dec),
        },
    }

    print_response(response(True, "Liquidity added", data))


@cli.command()
@click.option("--lp-address", required=True, type=str)
@click.option("--percentage", default=100, type=int)
def remove_liquidity(lp_address: str, percentage: int):
    """Remove liquidity and receive proportional assets + fees"""
    ledger = load_ledger()

    if lp_address not in ledger["lp_positions"]:
        print_response(response(False, "LP not found", error="lp_not_found"))
        return

    pos = ledger["lp_positions"][lp_address]
    units = Decimal(pos["units"])
    total_units = Decimal(ledger["total_units"])

    if total_units == 0:
        print_response(response(False, "Empty pool", error="empty_pool"))
        return

    share = units / total_units
    pct = Decimal(str(percentage)) / Decimal("100")
    withdraw_share = share * pct

    kas_pool = Decimal(ledger["pool_depth"]["KAS"])
    eth_pool = Decimal(ledger["pool_depth"]["ETH"])

    kas_return = kas_pool * withdraw_share
    eth_return = eth_pool * withdraw_share

    units_to_remove = units * pct
    pos["units"] = str(units - units_to_remove)
    pos["kas_deposit"] = str(Decimal(pos["kas_deposit"]) - kas_return)
    pos["eth_deposit"] = str(Decimal(pos["eth_deposit"]) - eth_return)

    ledger["total_units"] = str(total_units - units_to_remove)
    ledger["pool_depth"]["KAS"] = str(kas_pool - kas_return)
    ledger["pool_depth"]["ETH"] = str(eth_pool - eth_return)

    save_ledger(ledger)

    data = {
        "lp_address": lp_address,
        "percentage_withdrawn": percentage,
        "kas_returned": str(kas_return.quantize(Decimal("0.00000001"))),
        "eth_returned": str(eth_return.quantize(Decimal("0.00000001"))),
        "units_removed": str(units_to_remove),
        "remaining_units": pos["units"],
        "new_pool_depth": {
            "KAS": ledger["pool_depth"]["KAS"],
            "ETH": ledger["pool_depth"]["ETH"],
        },
    }

    print_response(response(True, "Liquidity removed", data))


@cli.command()
def pool_depth():
    """Show current pool depth and stats"""
    ledger = load_ledger()
    config = load_config()

    data = {
        "pool_depth": ledger["pool_depth"],
        "total_lp_units": ledger["total_units"],
        "num_lps": len(ledger["lp_positions"]),
        "config": {
            "min_slip_bps": config["min_slip_bps"],
            "operator_cut_bps": config["operator_cut_bps"],
            "affiliate_cut_bps": config["affiliate_cut_bps"],
            "max_swap_percent": config["max_swap_percent"],
        },
    }

    print_response(response(True, "Pool depth retrieved", data))


@cli.command()
@click.option("--lp-address", required=True, type=str)
def my_share(lp_address: str):
    """Show LP share and accrued fees"""
    ledger = load_ledger()

    if lp_address not in ledger["lp_positions"]:
        print_response(response(False, "LP not found", error="lp_not_found"))
        return

    pos = ledger["lp_positions"][lp_address]
    units = Decimal(pos["units"])
    total_units = Decimal(ledger["total_units"])
    share = (units / total_units * 100) if total_units > 0 else 0

    kas_pool = Decimal(ledger["pool_depth"]["KAS"])
    eth_pool = Decimal(ledger["pool_depth"]["ETH"])

    data = {
        "lp_address": lp_address,
        "units": pos["units"],
        "share_percent": str(share.quantize(Decimal("0.01"))),
        "proportional_kas": str(
            (kas_pool * units / total_units).quantize(Decimal("0.00000001"))
        )
        if total_units > 0
        else "0",
        "proportional_eth": str(
            (eth_pool * units / total_units).quantize(Decimal("0.00000001"))
        )
        if total_units > 0
        else "0",
        "total_deposited": {"KAS": pos["kas_deposit"], "ETH": pos["eth_deposit"]},
    }

    print_response(response(True, "LP share retrieved", data))


@cli.command()
@click.option("--secret-hash", required=True, type=str)
@click.option("--secret", required=True, type=str)
def claim(secret_hash: str, secret: str):
    """Claim HTLC by revealing preimage"""
    expected_hash = hashlib.sha256(bytes.fromhex(secret)).hexdigest()

    if expected_hash != secret_hash:
        print_response(response(False, "Invalid preimage", error="invalid_secret"))
        return

    data = {
        "secret_hash": secret_hash,
        "action": "claim_htlc",
        "status": "ready_to_claim",
    }

    print_response(response(True, "Preimage valid - claim HTLC", data))


@cli.command()
@click.option("--secret-hash", required=True, type=str)
def refund(secret_hash: str):
    """Request HTLC refund after timelock"""
    data = {
        "secret_hash": secret_hash,
        "action": "refund_htlc",
        "status": "ready_to_refund",
    }

    print_response(response(True, "Refund prepared", data))


@cli.command()
@click.option("--key", required=True, type=str)
@click.option("--value", required=True, type=int)
def update_mimir(key: str, value: int):
    """Update Mimir-style config parameters"""
    valid_keys = [
        "min_slip_bps",
        "operator_cut_bps",
        "affiliate_cut_bps",
        "max_swap_percent",
    ]
    if key not in valid_keys:
        print_response(
            response(False, f"Invalid key. Valid: {valid_keys}", error="invalid_key")
        )
        return

    config = load_config()
    config[key] = value

    with open(CONFIG_PATH, "w") as f:
        json.dump(config, f, indent=2)

    ledger = load_ledger()
    ledger["config"][key] = value
    save_ledger(ledger)

    print_response(response(True, f"Config updated: {key} = {value}", {key: value}))


@cli.command()
def list_tools():
    """List all available CLI commands for agent discovery"""
    tools = [
        {"name": "quote", "desc": "Get THORChain-style quote with slip fees"},
        {"name": "swap", "desc": "Execute atomic swap with fee deduction"},
        {"name": "add-liquidity", "desc": "Add liquidity and receive LP units"},
        {"name": "remove-liquidity", "desc": "Remove liquidity and withdraw assets"},
        {"name": "pool-depth", "desc": "Show current pool depth and stats"},
        {"name": "my-share", "desc": "Show LP share and proportional assets"},
        {"name": "claim", "desc": "Claim HTLC by revealing preimage"},
        {"name": "refund", "desc": "Request HTLC refund after timelock"},
        {"name": "update-mimir", "desc": "Update config parameters"},
        {"name": "list-tools", "desc": "List all available commands"},
    ]
    print_response(response(True, "Available tools", {"tools": tools}))


if __name__ == "__main__":
    cli()
