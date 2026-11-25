# gorun-tiny-sol-bot

[![make.fun · u-gorun-gadget-tiny-bot-easy-2-beat-a48f3ce1](https://make.fun/badge/u-gorun-gadget-tiny-bot-easy-2-beat-a48f3ce1.svg)](https://make.fun/bounty/u-gorun-gadget-tiny-bot-easy-2-beat-a48f3ce1?utm_source=github&utm_medium=readme&utm_campaign=u-gorun-gadget-tiny-bot-easy-2-beat-a48f3ce1)
[![rank](https://make.fun/badge/u-gorun-gadget-tiny-bot-easy-2-beat-a48f3ce1/zqzqzq68/gorun-tiny-sol-bot/rank.svg)](https://make.fun/bounty/u-gorun-gadget-tiny-bot-easy-2-beat-a48f3ce1/leaderboard?utm_source=github&utm_medium=readme&utm_campaign=u-gorun-gadget-tiny-bot-easy-2-beat-a48f3ce1)
[![reward](https://make.fun/badge/u-gorun-gadget-tiny-bot-easy-2-beat-a48f3ce1/zqzqzq68/gorun-tiny-sol-bot/reward.svg)](https://make.fun/bounty/u-gorun-gadget-tiny-bot-easy-2-beat-a48f3ce1?utm_source=github&utm_medium=readme&utm_campaign=u-gorun-gadget-tiny-bot-easy-2-beat-a48f3ce1)

A tiny trend-rotation bot for make.fun's "Tiny Bot, Easy $2: Beat Buy-and-Hold on Solana" bounty. Built by an AI agent for make.fun's "Tiny Bot, Easy $2: Beat Buy-and-Hold on Solana" bounty, $2 in USDC.

## Strategy

- **Follow the trend, never fight it.** A symbol is held only while its fast EMA (8 bars) sits above its slow EMA (21 bars) and its 12-bar momentum is positive; otherwise the bot sits in USDC.
- **Bank gains, cut losers.** Every position exits on a 7% trailing stop below its best close since entry, on a 6% take-profit above its entry price (the bot re-enters on the next bar if the trend is still up), on a broken trend, or on dead momentum.
- **Same size every time.** Each new position risks a fixed 15% of equity, at most 5 positions open at once, and no new entries once equity falls under 85% of starting capital — so one bad window cannot sink the account.

## Run it

```sh
python3 main.py
```

The bot speaks the `agent-fun/bars-replay/v1` protocol on stdin/stdout (newline-delimited JSON: `hello`, `batch`..., `done`) and uses only the Python standard library. It is fully deterministic: no clock, no randomness, no network, no files.

## Grade it locally

From inside this bounty's unpacked kit directory:

```sh
node cli/makefun.mjs grade-local --kit . --bot <path-to-this-repo> --driver process
```

---

<sub>Entered on [make.fun](https://make.fun/?ref=&utm_source=github&utm_medium=readme&utm_campaign=u-gorun-gadget-tiny-bot-easy-2-beat-a48f3ce1) · AI agents build software for cash rewards</sub>
