# Polymarket Complete-Set Checker (Lite)

Free, read-only. Answers one question: **does a YES+NO price gap on Polymarket survive the taker fee?**

- `fee`: Polymarket's taker fee, `shares × rate × p × (1 − p)`
- `calc`: YES+NO complete-set math on two prices you type in (buy-and-merge or split-and-sell)
- `check`: live top-of-book check of the most active binary markets, using each market's own fee schedule

Python 3.9+, standard library only. No wallet, no API key, never places orders.

## Quick start
```bash
python3 scripts/pm_lite.py calc --yes 0.48 --no 0.50 --size 100 --fee-rate 0.07
python3 scripts/pm_lite.py check --max-markets 100 --show-all --top 10
python3 -m unittest discover -s tests      # 8 offline tests
```

Worked example: YES 0.48 + NO 0.50 = 0.98, so it looks like 2¢ free per set. On 100 sets
the fees are $2.00 at a 4% rate (net +$0.0016) and $3.50 at 7% (net **−$1.50**).

## Honest expectations
Most checks find **nothing**. Real output from a live run (2026-10-27 00:22 UTC):

```
# 2026-10-27 00:22 UTC: 150 binary markets, fetching 300 books (top of book only)…
# 0 of 258 YES+NO checks show modelled profit after fees at the top of the book. Zero is the normal result. Research output only. Top-of-book prices m
strategy               title                                                    yes    no     sum    gap_before_fees  top_size  fee_rate  profit_after
---------------------  -------------------------------------------------------  -----  -----  -----  ---------------  --------  --------  ------------
buy YES+NO, merge      US x Yemen ceasefire continues through October 31?       0.987  0.014  1.001  -0.001           20        0         -0.02       
split $1, sell YES+NO  US x Yemen ceasefire continues through October 31?       0.986  0.013  0.999  -0.001           20        0         -0.02       
buy YES+NO, merge      Will Xavier Becerra win the California Governor Electi…  0.968  0.04   1.008  -0.008           5         0         -0.04     
split $1, sell YES+NO  Will Xavier Becerra win the California Governor Electi…  0.96   0.032  0.992  -0.008           5         0         -0.04     
buy YES+NO, merge      Israel x Iran ceasefire continues through October 27?    0.973  0.028  1.001  -0.001           50        0         -0.05       
split $1, sell YES+NO  Israel x Iran ceasefire continues through October 27?    0.972  0.027  0.999  -0.001           50        0         -0.05       
```

## Lite vs full
Lite covers binary markets at the top of the book only. The full Polymarket Edge Research Kit
adds an order-book depth walk, multi-outcome neg-risk baskets, market filters, EV and breakeven math,
an Excel calculator and a PDF playbook ($19): https://selar.com/v126c97911

License: MIT-0. Educational research tool, not financial advice. Not affiliated with Polymarket.
Prediction markets are restricted in some countries; check your local law.
