---
name: amazon-fba-USA-fee-calculator
description: Calculates Amazon US FBA fulfillment fees for a product from its package dimensions, weight, and selling price, using the official 2026 rate card (Jan 15 2026 - Jan 14 2027). Outputs non-peak and peak fees, each before and after the 3.5% fuel surcharge. This skill should be used whenever the user asks for an FBA shipping/fulfillment fee, wants to compare FBA fees across packaging options, or needs a size-tier determination for a US-bound product.
agent_created: true
---

# Amazon US FBA Fulfillment Fee Calculator (2026)

Computes the per-unit FBA fulfillment fee for the US marketplace from package
dimensions + weight + selling price, following the official 2026 rate card.

## When to use

- User supplies package dimensions and weight and asks "FBA 运费/配送费多少"
- Comparing packaging options (e.g. "if I shrink the box by 1 inch, how much do I save")
- Determining which size tier a product falls into
- Any US FBA margin / profitability estimate that needs the fulfillment fee line

## Critical: price is a required input

The 2026 rate card is split into three **selling-price bands**: `<$10`,
`$10-$50`, `>$50`. The same physical product can differ by roughly $0.70-$1.30
per unit between bands. **Never guess or default the price.** If the user has
not supplied a selling price, ask for it before calculating. Likewise, ask
whether the item is apparel — apparel uses a separate rate card.

## Workflow

1. Collect the inputs:
   - Package dimensions (3 values, any order)
   - Unit weight
   - **Selling price in USD (required — ask if missing)**
   - Unit system: `in-lb` (default) or `cm-kg`
   - Apparel? (default no)
2. Run the calculator:

   ```bash
   python <skill-dir>/scripts/fba_fee.py --dim 17.28 13.46 7.4 --weight 9.26 --price 39.99
   python <skill-dir>/scripts/fba_fee.py --dim 43.89 34.19 18.80 --weight 4.20 --unit cm-kg --price 39.99
   python <skill-dir>/scripts/fba_fee.py --dim 8.5 4.8 1 --weight 0.38 --price 19.99 --apparel
   python <skill-dir>/scripts/fba_fee.py --dim 16.6 13.3 7.7 --weight 6.6 --price 25 --json
   ```

   The script is stdlib-only (no pip install). Add `--json` to pipe results into
   a larger report or spreadsheet.
3. Verify before reporting. Run `python scripts/fba_fee.py --selftest` after any
   change to the rate JSON or the calc logic — it checks 5 worked examples
   published on Seller Central.
4. Report the fees and the derivation **as Markdown directly in the chat**.
   Do NOT generate an HTML report or any artifact file — the plain-text /
   Markdown output of the script is the deliverable. Present the 2x2 fee table
   as a Markdown table and the derivation as a short bullet list. Always surface
   the **billable weight** and the **size tier**, because those are what the user
   will want to optimize.

## Outputs

Four numbers are produced per product — present them as a 2x2 table.
**All fee amounts are in 美金 (USD)** — label them explicitly as 美金 so they
are never confused with RMB.

**Reporting format: Markdown only.** Show the result inline in the chat as a
Markdown table + a short derivation bullet list. Do NOT write or open an HTML
file — the script's text output is the final deliverable. (Earlier versions of
this skill produced HTML reports; that is deprecated.)

| | Rate card value (美金) | With 3.5% fuel surcharge (美金) |
|---|---|---|
| Non-peak (2026-01-15 .. 2026-10-14) | 美金 $X.XX | 美金 $X.XX |
| Peak (2026-10-15 .. 2027-01-14) | 美金 $X.XX | 美金 $X.XX |

The 3.5% fuel and logistics surcharge has applied since 2026-04-17 and has no
announced end date, so the "+3.5%" column is what the seller actually pays.

## Rules encoded in the calculator

Do not re-derive these by hand — the script already implements them. They are
listed so the reasoning can be explained when the user asks why a number landed
where it did.

- **Dimensional weight** = (longest x median x shortest) / 139. For small bulky,
  large bulky and extra-large, a **2-inch minimum** is assumed on the median and
  shortest sides.
- **Shipping weight**: small standard and extra-large 150+ lb use **unit weight
  only**; every other tier uses the **greater of unit weight or dimensional
  weight**.
- **Girth** = 2 x (median side + shortest side). Length plus girth = longest + girth.
- **Billing granularity**: small standard rounds up to 1 oz, large standard to
  4 oz, bulky/extra-large to 1 lb.
- **Size tiers** (from 2026-01-15): small standard / large standard /
  **small bulky** (new in 2026, split out of large bulky) / large bulky /
  extra-large in four weight bands.
- **Non-apparel** large standard above 3 lb adds $0.08 per 4 oz; **apparel** adds
  $0.16 per half-lb. Do not mix these up.

Full thresholds and every rate row live in `references/rates_2026.json`. To
update for a new fee year, edit only that JSON (plus the window strings in
`meta`) and re-run the self-test.

## Scope limits

- **Dangerous goods** use a separate rate card and are NOT supported. If the
  user's product is hazmat, say so rather than returning a non-apparel figure.
- Storage fees, Overmax handling, low-inventory-level fees, SIPP discounts and
  inbound placement fees are out of scope — this skill covers the fulfillment
  fee line only.
- Amazon measures the item itself and bills off its own measurements, so treat
  output as an estimate.

## Reference links

- 2026 fee changes: `sellercentral.amazon.com/help/hub/reference/external/GABBX6GZPA8MSZGW`
- Product size tiers: `sellercentral.amazon.com/help/hub/reference/external/GG5KW835AHDJCH8W`
- Dimensional weight: `sellercentral.amazon.com/gp/help/external/G53Z9EKF8VVZVH29`
- Shipping weight: `sellercentral.amazon.com/gp/help/external/GEVWP48HPBLEFJEY`

Seller Central help pages are login-gated; use the `external/` reference path
(as above) to reach the public mirror.
