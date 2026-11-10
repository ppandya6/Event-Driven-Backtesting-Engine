"""Public simulation records. Monetary inputs use Decimal, never binary floats."""
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum


def dec(value):
    return Decimal(str(value))


def positive(value, name, zero=False):
    value = dec(value)
    if not value.is_finite() or (value < 0 if zero else value <= 0):
        raise ValueError(f"{name} must be finite and {'nonnegative' if zero else 'positive'}")
    return value


class Side(str, Enum):
    BUY = 'buy'
    SELL = 'sell'


class Status(str, Enum):
    OPEN = 'open'
    FILLED = 'filled'
    CANCELLED = 'cancelled'
    REJECTED = 'rejected'


@dataclass(frozen=True)
class Quote:
    timestamp: datetime
    symbol: str
    bid: Decimal
    ask: Decimal
    size: int = 1000000  # shared executable quantity for this quote event

    def __post_init__(self):
        object.__setattr__(self, 'bid', positive(self.bid, 'bid'))
        object.__setattr__(self, 'ask', positive(self.ask, 'ask'))
        if not self.symbol or self.ask < self.bid or type(self.size) is not int or self.size < 0:
            raise ValueError('invalid symbol, crossed quote, or size')
        if self.timestamp.tzinfo is None or self.timestamp.utcoffset() is None:
            raise ValueError('timestamps must be timezone-aware')

    @property
    def mid(self):
        return (self.bid + self.ask) / 2


@dataclass
class Order:
    id: int
    symbol: str
    side: Side
    quantity: int
    limit: Decimal | None
    submitted_at: datetime
    remaining: int
    status: Status = Status.OPEN
    reason: str = ''


@dataclass(frozen=True)
class Fill:
    order_id: int
    timestamp: datetime
    symbol: str
    side: Side
    quantity: int
    price: Decimal
    fee: Decimal


@dataclass(frozen=True)
class Snapshot:
    timestamp: datetime
    cash: Decimal
    equity: Decimal
    gross_exposure: Decimal
