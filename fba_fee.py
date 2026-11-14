#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Amazon US FBA fulfillment fee calculator - 2026 rate card.

Zero dependencies (stdlib only). Rate data lives in ../references/rates_2026.json
so that annual fee changes only require editing the JSON.

Usage:
    python fba_fee.py --dim 17.28 13.46 7.4 --weight 9.26 --price 39.99
    python fba_fee.py --dim 43.89 34.19 18.80 --weight 4.20 --unit cm-kg --price 39.99
    python fba_fee.py --dim 8.5 4.8 1 --weight 0.38 --price 19.99 --apparel
    python fba_fee.py --dim 16.6 13.3 7.7 --weight 6.6 --price 25 --json
    python fba_fee.py --selftest

Units:
    in-lb (default): dimensions in inches, weight in pounds
    cm-kg          : dimensions in centimeters, weight in kilograms

Price is REQUIRED: the 2026 rate card is split into three selling-price bands
(<$10 / $10-50 / >$50). Without a price the correct fee cannot be selected.
"""

import argparse
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
RATES_PATH = os.path.normpath(os.path.join(HERE, "..", "references", "rates_2026.json"))

OZ_PER_LB = 16.0
LB_PER_KG = 2.20462262185
IN_PER_CM = 1.0 / 2.54
BULKY_OR_LARGER = (
    "small_bulky", "large_bulky",
    "extra_large_0_50", "extra_large_50_70",
    "extra_large_70_150", "extra_large_150_plus",
)


def load_rates():
    with open(RATES_PATH, encoding="utf-8") as fh:
        return json.load(fh)


def ceil_to(value, step):
    """Round up to the nearest multiple of `step` (float-safe)."""
    return math.ceil(round(value / step, 9)) * step


def price_band(price):
    if price < 10.0:
        return "lt10"
    if price <= 50.0:
        return "b1050"
    return "gt50"


def classify(a, b, c, len_plus_girth, ship_lb, unit_lb, tiers):
    """Return size-tier key. a>=b>=c are the sorted side lengths in inches."""
    t = tiers["small_standard"]
    if (unit_lb * OZ_PER_LB <= t["max_unit_oz"] and a <= t["max_longest_in"]
            and b <= t["max_median_in"] and c <= t["max_shortest_in"]):
        return "small_standard"

    t = tiers["large_standard"]
    if (ship_lb <= t["max_ship_lb"] and a <= t["max_longest_in"]
            and b <= t["max_median_in"] and c <= t["max_shortest_in"]):
        return "large_standard"

    t = tiers["small_bulky"]
    if (ship_lb <= t["max_ship_lb"] and a <= t["max_longest_in"]
            and b <= t["max_median_in"] and c <= t["max_shortest_in"]
            and len_plus_girth <= t["max_len_plus_girth_in"]):
        return "small_bulky"

    t = tiers["large_bulky"]
    if (ship_lb <= t["max_ship_lb"] and a <= t["max_longest_in"]
            and b <= t["max_median_in"] and c <= t["max_shortest_in"]
            and len_plus_girth <= t["max_len_plus_girth_in"]):
        return "large_bulky"

    # Extra-Large 150+ lb is keyed on UNIT weight, not shipping weight:
    # Amazon treats "unit weight more than 150 lb" as the 150+ trigger, and that
    # tier is the one that then bills on unit weight only.
    if unit_lb > tiers["extra_large_150_plus"]["min_unit_lb"]:
        return "extra_large_150_plus"
    if ship_lb <= tiers["extra_large_0_50"]["max_ship_lb"]:
        return "extra_large_0_50"
    if ship_lb <= tiers["extra_large_50_70"]["max_ship_lb"]:
        return "extra_large_50_70"
    return "extra_large_70_150"


def fee_for(tier_rate, bill_oz, band):
    """Return (fee, human-readable formula) for one rate-card entry."""
    if tier_rate["type"] == "bands":
        for row in tier_rate["rows"]:
            if bill_oz <= row["upto_oz"]:
                return row[band], "hit band <= %g oz" % row["upto_oz"]
        tail = tier_rate["tail"]
        intervals = int(math.ceil(round((bill_oz - tail["from_oz"]) / tail["interval_oz"], 9)))
        val = tail["base"][band] + intervals * tail["increment"]
        formula = "%s + %d x %s" % (tail["base"][band], intervals, tail["increment"])
        return val, formula

    # formula tier (bulky / extra-large): billable weight is whole pounds
    w_lb = bill_oz / OZ_PER_LB
    units = int(round(w_lb - tier_rate["above_lb"]))
    units = max(units, 0)
    val = tier_rate["base"][band] + units * tier_rate["increment"]
    formula = "%s + %d x %s (bill wt %g lb)" % (
        tier_rate["base"][band], units, tier_rate["increment"], w_lb)
    return val, formula


def calculate(dims_in, weight, price, unit="in-lb", apparel=False):
    """Core calculation. dims_in = [l, w, h]; weight and price in the given unit system."""
    rates = load_rates()
    meta = rates["meta"]
    tiers = rates["size_tiers"]

    d = sorted(dims_in, reverse=True)
    a, b, c = d[0], d[1], d[2]

    if unit == "cm-kg":
        a, b, c = a * IN_PER_CM, b * IN_PER_CM, c * IN_PER_CM
        unit_lb = weight * LB_PER_KG
    else:
        unit_lb = weight

    girth = 2.0 * (b + c)
    len_plus_girth = a + girth
    volume_plain = a * b * c

    # Dimensional weight: bulky/extra-large tiers assume a 2-inch minimum on the
    # two shorter sides. Standard-size tiers use the raw volume.
    def dim_weight(apply_min):
        if apply_min:
            m = meta["min_side_inches"]
            return (a * max(b, m) * max(c, m)) / meta["dim_divisor"]
        return volume_plain / meta["dim_divisor"]

    # Tier and shipping weight depend on each other (bulky/extra-large get a
    # 2-inch minimum on the two shorter sides, which raises dimensional weight
    # and can push the item into a heavier tier). Iterate to a fixed point.
    ship_lb = max(unit_lb, dim_weight(False))
    tier = classify(a, b, c, len_plus_girth, ship_lb, unit_lb, tiers)
    for _ in range(5):
        apply_min = tier in BULKY_OR_LARGER
        new_ship = max(unit_lb, dim_weight(apply_min))
        new_tier = classify(a, b, c, len_plus_girth, new_ship, unit_lb, tiers)
        converged = (new_tier == tier and abs(new_ship - ship_lb) < 1e-9)
        tier, ship_lb = new_tier, new_ship
        if converged:
            break

    # Dimensional weight that actually applies to this tier.
    apply_min = tier in BULKY_OR_LARGER
    dim_w = dim_weight(apply_min)

    # Fee weight: small standard and extra-large 150+ bill on unit weight only.
    basis = tiers[tier]["weight_basis"]
    fee_ship_lb = unit_lb if basis == "unit_weight" else ship_lb

    # Rounding to the billing granularity of the tier.
    if tier == "small_standard":
        step_oz = 1.0
    elif tier == "large_standard":
        step_oz = 4.0
    else:
        step_oz = OZ_PER_LB
    bill_oz = ceil_to(fee_ship_lb * OZ_PER_LB, step_oz)

    band = price_band(price)
    product = "apparel" if apparel else "non_apparel"
    surcharge = 1.0 + meta["fuel_surcharge_pct"] / 100.0

    out = {}
    for season in ("non_peak", "peak"):
        rate = rates["rates"][product][season][tier]
        base, formula = fee_for(rate, bill_oz, band)
        out[season] = {
            "card": round(base, 2),
            "with_surcharge": round(base * surcharge, 2),
            "formula": formula,
        }

    return {
        "input": {
            "dims_in": [round(x, 4) for x in (a, b, c)],
            "weight_input": weight,
            "unit": unit,
            "price": price,
            "apparel": apparel,
        },
        "derived": {
            "longest_in": round(a, 4),
            "median_in": round(b, 4),
            "shortest_in": round(c, 4),
            "girth_in": round(girth, 4),
            "len_plus_girth_in": round(len_plus_girth, 4),
            "volume_cu_in": round(volume_plain, 4),
            "volume_cu_ft": round(volume_plain / 1728.0, 6),
            "unit_weight_lb": round(unit_lb, 4),
            "dim_weight_lb": round(dim_w, 4),
            "dim_weight_two_inch_min": apply_min,
            "ship_weight_lb": round(ship_lb, 4),
            "fee_weight_lb": round(fee_ship_lb, 4),
            "billable_weight_oz": round(bill_oz, 4),
            "billable_weight_lb": round(bill_oz / OZ_PER_LB, 4),
            "size_tier": tier,
            "size_tier_zh": tiers[tier].get("label_zh", tier),
            "weight_basis": basis,
            "price_band": band,
        },
        "fees": out,
        "meta": {
            "non_peak_window": meta["non_peak_window"],
            "peak_window": meta["peak_window"],
            "fuel_surcharge_pct": meta["fuel_surcharge_pct"],
            "currency": meta["currency"],
        },
    }


def render(res):
    d = res["derived"]
    f = res["fees"]
    m = res["meta"]
    i = res["input"]
    lines = []
    lines.append("=" * 62)
    lines.append("Amazon US FBA Fulfillment Fee  |  2026 rate card")
    lines.append("=" * 62)
    lines.append("金额单位：美金 (USD)")
    lines.append("Input      : %.4g x %.4g x %.4g in   weight %.4g %s   price 美金 $%.2f%s"
                 % (i["dims_in"][0], i["dims_in"][1], i["dims_in"][2],
                    i["weight_input"], "kg" if i["unit"] == "cm-kg" else "lb",
                    i["price"], "  [APPAREL]" if i["apparel"] else ""))
    lines.append("")
    lines.append("-- Derivation " + "-" * 48)
    lines.append("Sorted sides     : longest %.4g in | median %.4g in | shortest %.4g in"
                 % (d["longest_in"], d["median_in"], d["shortest_in"]))
    lines.append("Girth            : 2 x (%.4g + %.4g) = %.4g in" % (d["median_in"], d["shortest_in"], d["girth_in"]))
    lines.append("Length + girth   : %.4g in" % d["len_plus_girth_in"])
    lines.append("Volume           : %.4g cu in (%.6g cu ft)" % (d["volume_cu_in"], d["volume_cu_ft"]))
    lines.append("Unit weight      : %.4g lb" % d["unit_weight_lb"])
    lines.append("Dim weight       : %.4g lb  (/139%s)" % (d["dim_weight_lb"], ", 2-inch min applied" if d["dim_weight_two_inch_min"] else ""))
    lines.append("Ship weight      : %.4g lb   (tier determination)" % d["ship_weight_lb"])
    lines.append("Fee weight       : %.4g lb   [basis: %s]" % (d["fee_weight_lb"], d["weight_basis"]))
    lines.append("Billable weight  : %.4g lb (%.4g oz)" % (d["billable_weight_lb"], d["billable_weight_oz"]))
    lines.append("Size tier        : %s (%s)" % (d["size_tier"], d["size_tier_zh"]))
    lines.append("Price band       : %s" % d["price_band"])
    lines.append("")
    lines.append("-- Fulfillment fee per unit " + "-" * 33)
    lines.append("%-30s %14s %16s" % ("", "card (美金)", "+3.5%% fuel (美金)"))
    lines.append("%-30s %14s %16s" % ("Non-peak (%s)" % m["non_peak_window"],
                                      "美金 $%.2f" % f["non_peak"]["card"],
                                      "美金 $%.2f" % f["non_peak"]["with_surcharge"]))
    lines.append("%-30s %14s %16s" % ("Peak     (%s)" % m["peak_window"],
                                      "美金 $%.2f" % f["peak"]["card"],
                                      "美金 $%.2f" % f["peak"]["with_surcharge"]))
    lines.append("")
    lines.append("Formula non-peak : %s" % f["non_peak"]["formula"])
    lines.append("Formula peak     : %s" % f["peak"]["formula"])
    lines.append("=" * 62)
    return "\n".join(lines)


def selftest():
    """Validate against worked examples published on Amazon Seller Central."""
    cases = [
        # (name, dims in, weight lb, price, apparel, expect tier, expect bill oz, expect non-peak fee)
        ("Mobile device case (Seller Central)", [13.8, 9, 0.7], 0.18, 9.99, False, "small_standard", 3.0, 2.49),
        ("Disposable plates (shipping weight)", [6.3, 6.2, 4.8], 3.0, 25.0, False, "large_standard", 48.0, 6.67),
        ("Glass jars (dim weight wins)", [16.6, 13.3, 7.7], 6.6, 25.0, False, "large_standard", 196.0, 9.93),
        ("Packaging reduction example", [12.2, 12.0, 4.3], 3.6, 25.0, False, "large_standard", 76.0, 7.53),
        ("White dry erase board (2-in min)", [40, 1, 25], 4.5, 25.0, False, "large_bulky", 240.0, 14.67),
    ]
    ok = True
    print("Running %d self-tests against Seller Central published examples\n" % len(cases))
    for name, dims, wt, price, app, exp_tier, exp_oz, exp_fee in cases:
        r = calculate(dims, wt, price, "in-lb", app)
        d = r["derived"]
        got_fee = r["fees"]["non_peak"]["card"]
        t_ok = d["size_tier"] == exp_tier
        w_ok = abs(d["billable_weight_oz"] - exp_oz) < 1e-6
        f_ok = abs(got_fee - exp_fee) < 0.005
        status = "PASS" if (t_ok and w_ok and f_ok) else "FAIL"
        if status == "FAIL":
            ok = False
        print("[%s] %s" % (status, name))
        print("        tier=%s (want %s) | bill=%g oz (want %g) | fee=$%.2f (want $%.2f)"
              % (d["size_tier"], exp_tier, d["billable_weight_oz"], exp_oz, got_fee, exp_fee))
    print()
    if ok:
        print("All self-tests passed.")
    else:
        print("SOME SELF-TESTS FAILED - do not trust results until fixed.")
    return 0 if ok else 1


def main():
    p = argparse.ArgumentParser(
        description="Amazon US FBA fulfillment fee calculator (2026 rate card).")
    p.add_argument("--dim", nargs=3, type=float, metavar=("L", "W", "H"),
                   help="Package dimensions (3 values, any order)")
    p.add_argument("--weight", type=float, help="Unit weight")
    p.add_argument("--price", type=float,
                   help="Selling price in USD (REQUIRED - 2026 fees are price-banded)")
    p.add_argument("--unit", choices=["in-lb", "cm-kg"], default="in-lb",
                   help="in-lb (default) or cm-kg")
    p.add_argument("--apparel", action="store_true",
                   help="Use the apparel rate card instead of non-apparel")
    p.add_argument("--json", action="store_true", help="Emit JSON instead of text")
    p.add_argument("--selftest", action="store_true",
                   help="Validate against Seller Central published examples")
    args = p.parse_args()

    if args.selftest:
        return selftest()

    if args.dim is None or args.weight is None:
        p.error("--dim and --weight are required (or use --selftest)")
    if args.price is None:
        p.error("--price is REQUIRED: 2026 fees are split into <$10 / $10-50 / >$50 bands.")
    if any(x <= 0 for x in args.dim) or args.weight <= 0:
        p.error("Dimensions and weight must be positive.")
    if args.price < 0:
        p.error("Price must be non-negative.")

    res = calculate(args.dim, args.weight, args.price, args.unit, args.apparel)
    if args.json:
        print(json.dumps(res, ensure_ascii=False, indent=2))
    else:
        print(render(res))
    return 0


if __name__ == "__main__":
    sys.exit(main())
