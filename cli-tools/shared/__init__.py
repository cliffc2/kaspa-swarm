"""
THORChain-style Continuous Liquidity Pool (CLP) fee engine.
Exact slip-based liquidity fee formula: fee = (x² * Y) / (x + X)²
where x = input amount, X = input pool depth, Y = output pool depth.
"""

from decimal import Decimal, getcontext, ROUND_DOWN

getcontext().prec = 28


def calculate_slip_fee(
    input_amount: Decimal, input_depth: Decimal, output_depth: Decimal
) -> Decimal:
    """
    THORChain CLP liquidity fee.
    fee = (x² * Y) / (x + X)²
    """
    if input_depth <= 0 or output_depth <= 0:
        return Decimal("0")
    x = input_amount
    X = input_depth
    Y = output_depth
    fee = (x * x * Y) / ((x + X) * (x + X))
    return fee


def calculate_output_with_fee(
    input_amount: Decimal,
    input_depth: Decimal,
    output_depth: Decimal,
    min_slip_bps: int = 5,
    operator_cut_bps: int = 150,
    affiliate_cut_bps: int = 0,
) -> dict:
    """
    Calculate expected output after all fees.
    Returns full breakdown for transparency.
    """
    if input_depth <= 0 or output_depth <= 0:
        return {
            "expected_output": "0",
            "liquidity_fee": "0",
            "operator_cut": "0",
            "affiliate_cut": "0",
            "slip_bps": 0,
            "total_fee_bps": 0,
            "price_impact": "0",
        }

    x = input_amount
    X = input_depth
    Y = output_depth

    base_output = (x * Y) / (x + X)
    liquidity_fee = calculate_slip_fee(x, X, Y)
    final_output = base_output - liquidity_fee

    slip_percent = (x / (x + X)) * Decimal("10000")
    slip_bps = float(slip_percent.quantize(Decimal("0.01")))

    effective_slip_bps = max(slip_bps, min_slip_bps)
    effective_fee = (Decimal(str(effective_slip_bps)) / Decimal("10000")) * base_output

    operator_cut = effective_fee * Decimal(str(operator_cut_bps)) / Decimal("10000")
    affiliate_cut = effective_fee * Decimal(str(affiliate_cut_bps)) / Decimal("10000")
    lp_fee = effective_fee - operator_cut - affiliate_cut

    final_output = base_output - effective_fee

    price_impact = (x / X) * Decimal("100")

    return {
        "expected_output": str(
            final_output.quantize(Decimal("0.00000001"), rounding=ROUND_DOWN)
        ),
        "liquidity_fee": str(
            effective_fee.quantize(Decimal("0.00000001"), rounding=ROUND_DOWN)
        ),
        "operator_cut": str(
            operator_cut.quantize(Decimal("0.00000001"), rounding=ROUND_DOWN)
        ),
        "affiliate_cut": str(
            affiliate_cut.quantize(Decimal("0.00000001"), rounding=ROUND_DOWN)
        ),
        "lp_fee": str(lp_fee.quantize(Decimal("0.00000001"), rounding=ROUND_DOWN)),
        "slip_bps": effective_slip_bps,
        "total_fee_bps": effective_slip_bps + operator_cut_bps + affiliate_cut_bps,
        "price_impact": str(price_impact.quantize(Decimal("0.01"))),
        "base_output": str(
            base_output.quantize(Decimal("0.00000001"), rounding=ROUND_DOWN)
        ),
    }


def calculate_lp_units(
    kas_added: Decimal,
    eth_added: Decimal,
    current_kas: Decimal,
    current_eth: Decimal,
    current_units: Decimal,
) -> Decimal:
    """
    THORChain-style pool units calculation.
    For first liquidity: units = sqrt(kas * eth) * scaling
    For subsequent: proportional to added value
    """
    if current_units == 0:
        return (kas_added * eth_added).sqrt() * Decimal("1000000")

    kas_ratio = (
        kas_added / (current_kas + kas_added) if current_kas > 0 else Decimal("0")
    )
    eth_ratio = (
        eth_added / (current_eth + eth_added) if current_eth > 0 else Decimal("0")
    )
    avg_ratio = (kas_ratio + eth_ratio) / Decimal("2")

    return current_units * avg_ratio


def should_stream_swap(
    input_amount: Decimal, pool_depth: Decimal, max_swap_percent: int = 5
) -> tuple[bool, int]:
    """
    Check if swap should be split into multiple smaller HTLCs.
    Returns (should_stream, num_chunks).
    """
    if pool_depth <= 0:
        return False, 1

    percent = (input_amount / pool_depth) * Decimal("100")
    if percent > Decimal(str(max_swap_percent)):
        chunks = max(4, int(percent / Decimal(str(max_swap_percent))))
        return True, min(chunks, 8)

    return False, 1
