"""Single-threaded deterministic replay with FIFO quote liquidity."""
from dataclasses import dataclass
from decimal import Decimal
from .models import Fill, Order, Side, Snapshot, Status, positive
from .portfolio import Portfolio


@dataclass(frozen=True)
class ExecutionModel:
    fee_per_share: Decimal = Decimal('0.005')
    slippage_bps: Decimal = Decimal('1')

    def __post_init__(self):
        for name in ('fee_per_share', 'slippage_bps'):
            object.__setattr__(self, name, positive(getattr(self, name), name, zero=True))
        if self.slippage_bps >= 10000:
            raise ValueError('slippage must be less than 10000 bps')

    def price(self, quote, side):
        sign = 1 if side == Side.BUY else -1
        return (quote.ask if sign == 1 else quote.bid) * (1 + sign * self.slippage_bps / 10000)


@dataclass(frozen=True)
class RiskLimits:
    max_position: int = 10000
    max_gross_leverage: Decimal = Decimal('1')
    allow_short: bool = False

    def __post_init__(self):
        if type(self.max_position) is not int or self.max_position <= 0:
            raise ValueError('max_position must be a positive integer')
        object.__setattr__(self, 'max_gross_leverage', positive(self.max_gross_leverage, 'leverage'))


class Engine:
    """Strategy signature: callback(engine, quote).

    Resting orders match before the callback. Orders submitted by the callback
    first become eligible at the next quote event for their symbol.
    """
    def __init__(self, cash=100000, execution=None, risk=None):
        self.portfolio = Portfolio(cash)
        self.execution = execution or ExecutionModel()
        self.risk = risk or RiskLimits()
        self.quotes = {}
        self.orders = {}
        self._active = {}
        self.fills = []
        self.history = []
        self.now = None
        self._ran = False

    def submit(self, symbol, side, quantity, limit=None):
        if self.now is None or symbol not in self.quotes:
            raise ValueError('a quote for the symbol must be observed before submitting')
        side = Side(side)
        if type(quantity) is not int or quantity <= 0:
            raise ValueError('quantity must be a positive integer')
        limit = None if limit is None else positive(limit, 'limit')
        order = Order(len(self.orders) + 1, symbol, side, quantity, limit, self.now, quantity)
        self.orders[order.id] = order
        self._active[order.id] = order
        return order.id

    def cancel(self, order_id):
        order = self.orders.get(order_id)
        if order is None or order.status != Status.OPEN:
            return False
        order.status = Status.CANCELLED
        self._active.pop(order_id)
        return True

    def _risk_reason(self, order, quantity, price):
        p = self.portfolio
        delta = quantity * (1 if order.side == Side.BUY else -1)
        current = p.positions.get(order.symbol)
        old = current.quantity if current else 0
        new = old + delta
        if not self.risk.allow_short and new < 0:
            return 'short selling disabled'
        if abs(new) > self.risk.max_position:
            return 'position limit'
        cash = p.cash - delta * price - quantity * self.execution.fee_per_share
        if cash < 0:
            return 'insufficient cash'
        mid = self.quotes[order.symbol].mid
        equity = p.equity(self.quotes) - delta * (price - mid) - quantity * self.execution.fee_per_share
        gross = p.gross(self.quotes) - abs(old) * mid + abs(new) * mid
        if equity <= 0 or gross > equity * self.risk.max_gross_leverage:
            return 'gross leverage limit'
        return ''

    def _match(self, quote):
        available = quote.size
        for order in list(self._active.values()):
            if not available:
                break
            if order.status != Status.OPEN or order.symbol != quote.symbol:
                continue
            price = self.execution.price(quote, order.side)
            if order.limit is not None and ((order.side == Side.BUY and price > order.limit) or
                                             (order.side == Side.SELL and price < order.limit)):
                continue
            quantity = min(order.remaining, available)
            reason = self._risk_reason(order, quantity, price)
            if reason:
                order.status, order.reason = Status.REJECTED, reason
                self._active.pop(order.id)
                continue
            fill = Fill(order.id, quote.timestamp, order.symbol, order.side, quantity, price,
                        quantity * self.execution.fee_per_share)
            self.portfolio.apply(fill)
            self.fills.append(fill)
            order.remaining -= quantity
            available -= quantity
            if order.remaining == 0:
                order.status = Status.FILLED
                self._active.pop(order.id)

    def run(self, events, strategy):
        if self._ran:
            raise RuntimeError('create a fresh engine for each replay')
        self._ran = True
        for quote in events:
            if self.now is not None and quote.timestamp < self.now:
                raise ValueError('events must be globally chronological')
            self.now = quote.timestamp
            self.quotes[quote.symbol] = quote
            self._match(quote)
            strategy(self, quote)
            p = self.portfolio
            self.history.append(Snapshot(self.now, p.cash, p.equity(self.quotes), p.gross(self.quotes)))
        return self

    def summary(self):
        equity = self.history[-1].equity if self.history else self.portfolio.initial_cash
        peak = self.portfolio.initial_cash
        drawdown = Decimal(0)
        for snapshot in self.history:
            peak = max(peak, snapshot.equity)
            drawdown = max(drawdown, (peak - snapshot.equity) / peak)
        return {'events': len(self.history), 'fills': len(self.fills), 'equity': str(equity),
                'return': str(equity / self.portfolio.initial_cash - 1),
                'max_drawdown': str(drawdown), 'fees': str(self.portfolio.fees),
                'realized_pnl_before_fees': str(self.portfolio.realized_pnl)}
