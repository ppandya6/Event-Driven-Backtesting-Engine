import argparse
import json
from .data import read_quotes
from .engine import Engine, ExecutionModel
from .strategies import MovingAverageCross


def main():
    parser = argparse.ArgumentParser(description='Replay quote CSV with a moving-average strategy')
    parser.add_argument('csv')
    parser.add_argument('--cash', default='100000')
    parser.add_argument('--fee-per-share', default='0.005')
    parser.add_argument('--slippage-bps', default='1')
    parser.add_argument('--fast', type=int, default=3)
    parser.add_argument('--slow', type=int, default=8)
    parser.add_argument('--quantity', type=int, default=10)
    args = parser.parse_args()
    engine = Engine(args.cash, ExecutionModel(args.fee_per_share, args.slippage_bps))
    engine.run(read_quotes(args.csv), MovingAverageCross(args.fast, args.slow, args.quantity))
    print(json.dumps(engine.summary(), indent=2))
