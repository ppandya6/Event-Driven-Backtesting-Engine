"""Run from repository root: python -m tools.profile_engine --events 100000."""
import argparse
import cProfile
from datetime import datetime, timedelta, timezone
from time import perf_counter
from backtest import Engine, Quote
from backtest.strategies import MovingAverageCross


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--events', type=int, default=100000)
    parser.add_argument('--output', default='/tmp/backtest.prof')
    args = parser.parse_args()
    if args.events <= 0:
        parser.error('--events must be positive')
    start = datetime(2024, 1, 1, tzinfo=timezone.utc)
    events = (Quote(start + timedelta(seconds=i), 'DEMO', 100 + i % 20, 101 + i % 20, 100) for i in range(args.events))
    engine = Engine()
    profiler = cProfile.Profile()
    t0 = perf_counter()
    profiler.runcall(engine.run, events, MovingAverageCross())
    elapsed = perf_counter() - t0
    profiler.dump_stats(args.output)
    print(f'{len(engine.history)} events, {len(engine.fills)} fills, {elapsed:.3f}s, {args.events / elapsed:.0f} events/s')
    profiler.print_stats(sort='cumulative')


if __name__ == '__main__':
    main()
