# Amazon US FBA Fee Calculator

An [Agent Skill](https://agentskills.io) that calculates Amazon US FBA fulfillment fees from package dimensions, weight, and selling price, using the official 2026 rate card (15 Jan 2026 – 14 Jan 2027).

Works with any agent that can load a `SKILL.md` skill folder, including Workbuddy, Grok Bot, Codex, Claude Code, Cursor, and similar tools.

输入产品的包装尺寸、重量和售价，即可测算美国站 FBA 配送费（含非旺季 / 旺季，以及 3.5% 燃油附加费后的实付金额）。

## What it does

- Determines the 2026 size tier (small standard, large standard, small bulky, large bulky, extra-large)
- Computes billable weight (unit weight vs dimensional weight, with the correct rounding rules)
- Returns four fee figures: non-peak and peak, each before and after the 3.5% fuel and logistics surcharge
- Supports inch-pound or cm-kilogram inputs, and a separate apparel rate card
- Ships a stdlib-only Python calculator (`scripts/fba_fee.py`) plus the full rate table (`references/rates_2026.json`)
- Includes `--selftest` checks against Seller Central published examples

Selling price is required, because the 2026 rate card is split into `<$10`, `$10–$50`, and `>$50` bands. Dangerous goods, storage fees, and inbound placement fees are out of scope.

Treat the result as an estimate: Amazon bills from its own measurements.

## Install

Copy or clone this repository into your agent's skills directory, keeping the folder name and the `SKILL.md` / `scripts/` / `references/` layout intact.

```bash
git clone https://github.com/BOMEWILL/amazon-fba-usa-fee-calculator.git
```

Then move the folder here, depending on the agent:

| Agent | Skills directory |
| --- | --- |
| Workbuddy | `~/.workbuddy/skills/` (Windows: `%USERPROFILE%\.workbuddy\skills\`) |
| Claude Code | `~/.claude/skills/` or a project's `.claude/skills/` |
| Codex | `~/.codex/skills/` |
| Cursor | `~/.cursor/skills/` or a project's `.cursor/skills/` |
| Grok Bot and other agents | The agent's configured skills / workflows folder |

You can also point the agent at this repository and ask it to install the skill from the repo URL.

After installation, ask the agent to calculate a US FBA fulfillment fee and give it dimensions, weight, and selling price.

## Usage

The calculator needs only Python 3 (no `pip` packages).

```bash
python scripts/fba_fee.py --dim 17.28 13.46 7.4 --weight 9.26 --price 39.99
python scripts/fba_fee.py --dim 43.89 34.19 18.80 --weight 4.20 --unit cm-kg --price 39.99
python scripts/fba_fee.py --dim 8.5 4.8 1 --weight 0.38 --price 19.99 --apparel
python scripts/fba_fee.py --dim 16.6 13.3 7.7 --weight 6.6 --price 25 --json
python scripts/fba_fee.py --selftest
```

See `SKILL.md` for the reporting format, size-tier rules, and scope limits.

## License

MIT. See [LICENSE](LICENSE).

Fee amounts come from Amazon's published 2026 rate card and are not affiliated with or endorsed by Amazon.
