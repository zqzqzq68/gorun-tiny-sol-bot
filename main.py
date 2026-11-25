"""Tiny trend-rotation bot for the make.fun bars-replay/v1 harness.

Strategy, in plain words:
  * Follow the trend on every symbol, never fight it: hold a symbol only
    while its fast EMA sits above its slow EMA and its recent momentum
    is positive; sit in USDC otherwise.
  * Bank gains and cut losers with two exits per position: a trailing
    stop below the best close since entry, and a take-profit that sells
    the whole position once it is up a fixed percent (the bot re-enters
    on the next bar if the trend is still up, so a steady climb keeps
    compounding instead of stalling on a single entry).
  * Size every new position the same way (a fixed share of current
    equity), cap how many positions can be open at once, and stop opening
    new ones after a deep equity drawdown, so one bad window cannot sink
    the account.

The bot speaks the harness protocol on stdin/stdout (newline-delimited
JSON: hello, batch..., done) and uses only the standard library. It is
fully deterministic: no clock, no randomness, no network, no files.
"""

import json
import sys

# --- Tunable strategy constants (all plain numbers, no magic elsewhere) ---
FAST_SPAN = 8          # bars in the fast EMA
SLOW_SPAN = 21         # bars in the slow EMA
MOMENTUM_BARS = 12     # bars over which momentum is measured
MOMENTUM_ENTER = 0.01  # enter only if the 12-bar return beats +1%
MOMENTUM_EXIT = -0.03  # exit if the 12-bar return falls below -3%
WARMUP_BARS = 24       # closes needed before the first entry
TARGET_WEIGHT = 0.15   # share of equity per new position
MAX_POSITIONS = 5      # cap on simultaneous open positions
TRAILING_STOP = 0.07   # exit if close drops 7% below the peak since entry
TAKE_PROFIT = 0.06     # exit if close rises 6% above the entry price
MAX_HOURLY_MOVE = 0.05  # skip symbols whose recent hourly moves average over 5%
EQUITY_GUARD = 0.85    # stop new entries once equity is under 85% of start
MAX_SLIPPAGE_BPS = 50  # slippage cap on every order


def ema_update(previous, price, span):
    """One exponential-moving-average step (seeded with the first price)."""
    if previous is None:
        return price
    alpha = 2.0 / (span + 1.0)
    return alpha * price + (1.0 - alpha) * previous


class SymbolState:
    """Per-symbol memory: closes, EMAs, and the peak since entry."""

    def __init__(self):
        self.closes = []
        self.fast = None
        self.slow = None
        self.peak = None

    def add_close(self, price):
        self.closes.append(price)
        self.fast = ema_update(self.fast, price, FAST_SPAN)
        self.slow = ema_update(self.slow, price, SLOW_SPAN)

    def momentum(self):
        """Simple return over the last MOMENTUM_BARS closes."""
        if len(self.closes) <= MOMENTUM_BARS:
            return None
        old = self.closes[-MOMENTUM_BARS - 1]
        return self.closes[-1] / old - 1.0

    def mean_hourly_move(self):
        """Mean absolute hourly move over the last 24 closes."""
        window = self.closes[-25:]
        if len(window) < 2:
            return 0.0
        moves = [abs(window[i] / window[i - 1] - 1.0)
                 for i in range(1, len(window))]
        return sum(moves) / len(moves)


class Bot:
    def __init__(self, hello):
        self.scales = {s["symbol"]: (s["price_scale"], s["qty_scale"])
                       for s in hello["symbols"]}
        self.capital = int(hello["capital"]["quote_units"])
        self.quote_scale = hello["capital"]["quote_scale"]
        self.max_weight_bps = hello["caps"]["max_weight_bps"]
        self.min_notional = int(hello["fees"]["min_notional_quote_units"])
        self.states = {symbol: SymbolState() for symbol in self.scales}
        self.warmup = hello.get("warmup_bars") or 0

    def price_of(self, symbol, raw_close):
        scale = self.scales[symbol][0]
        return int(raw_close) / (10 ** scale)

    def decide(self, batch):
        """Return the list of orders for one batch."""
        orders = []
        account = batch["account"]
        equity = int(account["equity_quote_units"])
        cash = int(account["cash_quote_units"])
        held = {p["symbol"]: p for p in account["positions"]}
        seq = batch["seq"]

        for bar in batch["bars"]:
            symbol = bar["symbol"]
            if symbol not in self.states:
                continue
            state = self.states[symbol]
            state.add_close(self.price_of(symbol, bar["c"]))

        # Trade only once every symbol has enough history to judge a trend.
        if any(len(s.closes) < WARMUP_BARS for s in self.states.values()):
            return orders
        if seq < self.warmup:
            return orders

        for symbol, state in self.states.items():
            close = state.closes[-1]
            momentum = state.momentum()
            if momentum is None:
                continue
            position = held.get(symbol)
            if position is not None:
                # Entry price in USDC per token: cost (micro-USDC) divided
                # by the token count (qty at qty_scale).
                qty_scale = self.scales[symbol][1]
                entry_price = (int(position["cost_quote_units"])
                               * (10 ** qty_scale)
                               / int(position["qty"])
                               / (10 ** self.quote_scale))
                if state.peak is None or close > state.peak:
                    state.peak = close
                fell_off_peak = close < state.peak * (1.0 - TRAILING_STOP)
                took_profit = close > entry_price * (1.0 + TAKE_PROFIT)
                trend_broke = state.fast < state.slow
                momentum_dead = momentum < MOMENTUM_EXIT
                if fell_off_peak or took_profit or trend_broke or momentum_dead:
                    orders.append({
                        "side": "sell",
                        "client_id": "sell-%s-%d" % (symbol, seq),
                        "symbol": symbol,
                        "qty": position["qty"],
                        "max_slippage_bps": MAX_SLIPPAGE_BPS,
                    })
                    state.peak = None
            else:
                if len(held) + len([o for o in orders
                                    if o["side"] == "buy"]) >= MAX_POSITIONS:
                    continue
                if equity < self.capital * EQUITY_GUARD:
                    continue
                trend_up = state.fast > state.slow
                strong = momentum > MOMENTUM_ENTER
                calm = state.mean_hourly_move() < MAX_HOURLY_MOVE
                if trend_up and strong and calm:
                    notional = int(equity * TARGET_WEIGHT)
                    cap = equity * self.max_weight_bps // 10000
                    notional = min(notional, cap, cash)
                    if notional >= self.min_notional:
                        orders.append({
                            "side": "buy",
                            "client_id": "buy-%s-%d" % (symbol, seq),
                            "symbol": symbol,
                            "notional_quote_units": str(notional),
                            "max_slippage_bps": MAX_SLIPPAGE_BPS,
                        })
        return orders


def main():
    bot = None
    out = sys.stdout
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        message = json.loads(line)
        kind = message.get("type")
        if kind == "hello":
            bot = Bot(message)
        elif kind == "batch":
            orders = bot.decide(message)
            out.write(json.dumps({"type": "reply", "seq": message["seq"],
                                  "orders": orders}) + "\n")
            out.flush()
        elif kind == "done":
            break


if __name__ == "__main__":
    main()
