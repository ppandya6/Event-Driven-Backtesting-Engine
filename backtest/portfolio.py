"""Cash, average-cost positions and realized P&L accounting."""
from dataclasses import dataclass
from decimal import Decimal
from .models import Side, positive


@dataclass
class Position:
    quantity: int = 0
    average_price: Decimal = Decimal(0)


class Portfolio:
    def __init__(self, cash):
        self.initial_cash = self.cash = positive(cash, 'cash')
        self.positions = {}
        self.realized_pnl = Decimal(0)  # before fees
        self.fees = Decimal(0)

    def apply(self, fill):
        p = self.positions.setdefault(fill.symbol, Position())
        delta = fill.quantity * (1 if fill.side == Side.BUY else -1)
        old = p.quantity
        if old * delta < 0:
            closed = min(abs(old), abs(delta))
            self.realized_pnl += closed * (fill.price - p.average_price) * (1 if old > 0 else -1)
        new = old + delta
        if old == 0 or old * delta > 0:
            p.average_price = (abs(old) * p.average_price + abs(delta) * fill.price) / abs(new)
        elif new == 0:
            p.average_price = Decimal(0)
        elif old * new < 0:
            p.average_price = fill.price
        p.quantity = new
        self.cash -= delta * fill.price + fill.fee
        self.fees += fill.fee

    def equity(self, quotes):
        return self.cash + sum(p.quantity * quotes[s].mid for s, p in self.positions.items() if p.quantity)

    def gross(self, quotes):
        return sum((abs(p.quantity) * quotes[s].mid for s, p in self.positions.items() if p.quantity), Decimal(0))
