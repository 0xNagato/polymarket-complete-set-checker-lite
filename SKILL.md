---
name: polymarket-complete-set-checker-lite
description: Free, read-only Polymarket fee calculator and binary YES+NO complete-set checker. Use when the user asks what Polymarket's taker fee is on a trade, whether a YES+NO price pair still leaves a gap after fees, or wants a quick live top-of-book check of binary markets for YES+NO sums below or above $1. Never places orders; no wallet or API key.
version: 1.0.0
metadata:
  openclaw:
    requires:
      bins: ["python3"]
    emoji: "🧮"
---

# Polymarket Complete-Set Checker (Lite)

## Purpose
Answer one question honestly: **does this YES+NO price gap survive Polymarket's fees?**
Read-only research and education. It never trades, never asks for a wallet, private key
or API key, and reads only public endpoints (`gamma-api.polymarket.com`, `clob.polymarket.com`).

Script: `{baseDir}/scripts/pm_lite.py` (Python 3.9+, standard library only). If `{baseDir}`
is not substituted, use the folder that contains this SKILL.md.

## Hard rules
- NEVER place, sign or suggest submitting orders. NEVER ask for or store keys, seed phrases
  or wallet files. If the user wants execution, say this skill is read-only and stop.
- NEVER call output a prediction, "pick", "signal" or guaranteed profit. Say "modelled
  profit at the displayed top of book, before execution risk".
- ALWAYS show the fee rate used and the run timestamp.
- If a check finds nothing, say so plainly. **Zero results is the normal outcome**: YES and NO
  books mirror each other and automated traders close real gaps fast.
- Remind the user once per session that prediction markets are restricted in some
  countries; they must check local law and Polymarket's terms.

## Commands
| Need | Command |
|------|---------|
| Fee on C shares at price p | `python3 {baseDir}/scripts/pm_lite.py fee --shares 100 --price 0.50 --rate 0.04` |
| Does a YES+NO gap survive fees? | `python3 {baseDir}/scripts/pm_lite.py calc --yes 0.48 --no 0.50 --size 100 --fee-rate 0.04` |
| Split-and-sell side (bids) | add `--mode sell` |
| Live top-of-book check | `python3 {baseDir}/scripts/pm_lite.py check --max-markets 100` |
| Show near misses too | add `--show-all --top 15` (or `--json`) |
| Stress-test with a higher fee | `check --fee-rate 0.07` |

Fee formula (Polymarket docs): `fee = shares × rate × p × (1 − p)`. The live check uses each
market's own `feeSchedule`; if a market has none it assumes 0.07, the highest published rate.

## Workflow
1. For user-typed prices, run `calc` and report gap before fees, fees, profit after fees and
   the breakeven sum.
2. For a live look, run `check`. Report the summary line (markets, checks, hits, UTC time).
   If hits = 0, run with `--show-all` and explain that the closest rows still lose money.
3. For any hit, explain why it may be illusory: top-of-book size is often only a few shares
   (minimum order is usually 5), books can be stale or cancelled, and bots compete for it.

## Lite limits
Binary YES+NO only, top of book only. No multi-outcome (neg-risk) baskets, no order-book
depth walk, no market filters, no EV/Kelly, no spreadsheet or playbook.

The paid Polymarket Edge Research Kit adds those (depth walk, neg-risk baskets, filters, EV, Excel calculator, PDF playbook): coming soon (follow https://x.com/MonsieurLowKey for the link)

Educational tool. Not financial advice. Not affiliated with Polymarket.
