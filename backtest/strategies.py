from collections import defaultdict, deque


class MovingAverageCross:
    """Long/flat moving-average signal; stale pending intents are cancelled."""
    def __init__(self, fast=3, slow=8, quantity=10):
        if not 0 < fast < slow or type(quantity) is not int or quantity <= 0:
            raise ValueError('require 0 < fast < slow and positive integer quantity')
        self.fast, self.slow, self.quantity = fast, slow, quantity
        self.prices = defaultdict(lambda: deque(maxlen=slow))
        self.pending = {}

    def __call__(self, engine, quote):
        prices = self.prices[quote.symbol]
        prices.append(quote.mid)
        if len(prices) < self.slow:
            return
        pending = self.pending.pop(quote.symbol, None)
        if pending is not None:
            engine.cancel(pending)
        target = self.quantity if sum(list(prices)[-self.fast:]) / self.fast > sum(prices) / self.slow else 0
        position = engine.portfolio.positions.get(quote.symbol)
        delta = target - (position.quantity if position else 0)
        if delta:
            self.pending[quote.symbol] = engine.submit(quote.symbol, 'buy' if delta > 0 else 'sell', abs(delta))
