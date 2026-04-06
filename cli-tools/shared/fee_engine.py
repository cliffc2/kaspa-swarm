# cli-tools/shared/fee_engine.py
from decimal import Decimal, getcontext
from typing import Dict

getcontext().prec = 36


def calculate_slip_fee(
    input_amount: Decimal, input_pool_depth: Decimal, output_pool_depth: Decimal
) -> Decimal:
    """THORChain-style liquidity fee: fee = (x² * Y) / (x + X)²"""
    if input_pool_depth <= 0 or output_pool_depth <= 0:
        return Decimal("0")
    x = input_amount
    X = input_pool_depth
    Y = output_pool_depth
    fee = (x * x * Y) / ((x + X) ** 2)
    return fee.quantize(Decimal("0.00000001"))


def calculate_quote(
    input_amount: Decimal,
    input_depth: Decimal,
    output_depth: Decimal,
    min_slip_bps: int = 10,
    operator_cut_bps: int = 150,
) -> Dict:
    if input_depth <= 0 or output_depth <= 0:
        base_output = Decimal("0")
    else:
        base_output = (input_amount * output_depth) / (input_amount + input_depth)

    liquidity_fee = calculate_slip_fee(input_amount, input_depth, output_depth)
    final_output = base_output - liquidity_fee

    # Apply operator cut on the liquidity fee
    operator_cut = liquidity_fee * Decimal(operator_cut_bps) / Decimal(10000)
    net_fee_to_pool = liquidity_fee - operator_cut

    slip_bps = (
        float((input_amount / (input_amount + input_depth)) * 10000)
        if (input_amount + input_depth) > 0
        else 0.0
    )

    total_fee_bps = max(slip_bps, float(min_slip_bps))

    return {
        "success": True,
        "data": {
            "input_amount": float(input_amount),
            "expected_output": float(final_output.quantize(Decimal("0.00000001"))),
            "liquidity_fee": float(liquidity_fee.quantize(Decimal("0.00000001"))),
            "operator_cut": float(operator_cut.quantize(Decimal("0.00000001"))),
            "net_fee_to_pool": float(net_fee_to_pool.quantize(Decimal("0.00000001"))),
            "slip_bps": round(slip_bps, 2),
            "total_fee_bps": round(total_fee_bps, 2),
            "input_pool_depth": float(input_depth),
            "output_pool_depth": float(output_depth),
        },
    }
