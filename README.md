# Event-Driven Backtesting Engine

A dependency-free Python 3.10+ trading simulator for historical bid/ask quotes.
It includes market and limit orders, cancellation, FIFO partial fills, transaction
costs, average-cost portfolio accounting, execution-time risk controls, CSV replay,
a moving-average example strategy, automated tests, and CPU profiling.

## Run

From the repository root:

```sh
python -m backtest examples/quotes.csv
python -m unittest discover -s tests -v
python -m tools.profile_engine --events 100000
```

Optional installation exposes the `backtest` command:

```sh
python -m venv .venv
.venv/bin/python -m pip install -e .
.venv/bin/backtest examples/quotes.csv --cash 100000 --fee-per-share 0.005 --slippage-bps 1
```

No API keys, databases, or downloaded market data are required. The sample CSV is
synthetic and demonstrates mechanics, not investment performance.

## Strategy API

```python
from backtest import Engine
from backtest.data import read_quotes

def strategy(engine, quote):
    if not engine.orders:
        order_id = engine.submit(quote.symbol, 'buy', 10, limit='110')
        # engine.cancel(order_id) cancels any still-open remainder.

engine = Engine(cash='100000').run(read_quotes('examples/quotes.csv'), strategy)
print(engine.summary())
print(engine.fills)
```

A strategy receives the engine and the current immutable quote. It can inspect
observed quotes, portfolio positions, order states, fills and equity history.
Instantiate a fresh engine and strategy for each replay. Monetary records use
`Decimal`; prefer strings for monetary inputs. Quantities are positive integers.

## Event and execution contract

1. Read an event and require timezone-aware, globally nondecreasing timestamps.
   Equal timestamps preserve input order; each CSV row is a separate event.
2. Update that symbol's quote. Match previously submitted orders in submission
   order against the event's shared executable `size`.
3. Execute buys at ask plus configured basis-point slippage, sells at bid minus
   slippage. Charge a per-share fee on each actual fill. Limit prices constrain
   the execution price including slippage, excluding fees.
4. Check projected cash, absolute per-symbol position and gross/equity leverage
   before each fill, using all previously executed fills. A failed check rejects
   the remaining order; the engine does not resize it to fit risk limits.
5. Update cash, average cost, realized P&L and fees. Call the strategy, then append
   the cash/equity/gross-exposure snapshot.

Orders created in a callback cannot execute until the next event for their
symbol, even if another symbol receives an intervening quote. An open order can
fill partially across events. Zero-size quotes do not fill. Cancellation affects
only the unfilled remainder. Orders are good until cancelled and remain open at
end of input; there is no automatic liquidation. Quotes mark positions at their
midpoint. The last observed quote is retained for symbols without a new event.

Risk defaults: no shorts, no negative cash, 10,000 shares per symbol, gross
leverage at most 1. Configure `RiskLimits` and `ExecutionModel` on the engine.
Risk checks run at fills, not submission: pending orders do not reserve funds,
and later orders can be rejected as earlier orders consume cash. Price moves can
breach limits without an automatic liquidation. Short sale proceeds enter cash;
borrow availability, financing, borrow fees and margin calls are not modeled.

## Historical data

CSV fields:

```csv
timestamp,symbol,bid,ask,size
2024-01-02T14:30:00+00:00,DEMO,100,100.10,100
```

`size` defaults to 1,000,000 if the column is absent. It represents shared
executable shares for that event, not cumulative exchange volume. Prices must be
finite and positive, ask >= bid, and size a nonnegative integer. Feed multiple
symbols in one globally sorted stream. Invalid input raises an error; a replay
that raises is incomplete and its partial results should be discarded.

## Architecture and accounting

- `models.py`: quotes, orders, fills and snapshots.
- `engine.py`: replay, matching, execution costs and risk limits.
- `portfolio.py`: signed positions, cash and average-cost realized P&L.
- `data.py`: streaming CSV adapter.
- `strategies.py`: long/flat moving-average strategy with cancellation of stale intents.
- `cli.py`: runnable simulation and JSON summary.

Equity = cash + signed shares × midpoint. Gross exposure uses absolute shares.
Realized P&L is reported before fees; cash and equity include fees. Average cost
is unchanged by partial closes and resets on position reversal. Total return is
final equity / initial cash − 1. Maximum drawdown includes starting capital as
its initial peak. Summary returns are fractions, not percentages. Open positions
remain marked, so realized P&L alone is not total strategy profit.

## Validation and profiling

Tests cover execution timing, exact costs, limits, partial fills, cancellation,
risk rejection, cash conservation, shorts, reversal accounting, drawdown,
multisymbol isolation, input validation and repeatability. GitHub Actions runs
these checks on Python 3.10, 3.12 and 3.13.

```sh
python -m tools.profile_engine --events 100000 --output /tmp/backtest.prof
python -m pstats /tmp/backtest.prof
```

The profiler exercises actual strategy orders and fills and prints throughput
and cumulative CPU statistics. The CSV adapter streams; the engine deliberately
retains orders, fills and snapshots in memory for inspection. Matching scans
active orders only; memory grows with recorded history. Benchmark results vary
by machine and workload.

This is a deterministic quote-level model, not an exchange order book: it omits
queue position, latency, impact calibrated to volume, corporate actions, trading
calendars and multi-currency accounting. Adjust historical data for corporate
actions before replay; do not interpret synthetic liquidity as fill certainty.
