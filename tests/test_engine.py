import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal as D
from backtest import Engine, ExecutionModel, RiskLimits, Quote, Status, Portfolio, Fill, Side
from backtest.data import read_quotes
from backtest.strategies import MovingAverageCross

T = datetime(2024, 1, 1, tzinfo=timezone.utc)
def q(i, bid=99, ask=101, size=100, symbol='X'):
    return Quote(T + timedelta(seconds=i), symbol, bid, ask, size)

class EngineTests(unittest.TestCase):
    def test_costs_and_next_quote_execution(self):
        e = Engine(10000, ExecutionModel('0.1', 10))
        e.run([q(0), q(1)], lambda e, ev: e.submit('X','buy',10) if ev.timestamp == T else None)
        self.assertEqual(len(e.fills),1)
        self.assertEqual(e.fills[0].timestamp,T+timedelta(seconds=1))
        self.assertEqual(e.fills[0].price,D('101.101'))
        self.assertEqual(e.portfolio.cash,D('8987.990'))
        self.assertEqual(e.portfolio.equity(e.quotes),D('9987.990'))

    def test_fifo_partial_and_cancel(self):
        e = Engine(execution=ExecutionModel(0,0))
        def strategy(e, ev):
            if ev.timestamp == T:
                e.submit('X','buy',5)
                e.submit('X','buy',5)
            elif ev.timestamp == T+timedelta(seconds=1):
                self.assertTrue(e.cancel(2))
                self.assertFalse(e.cancel(2))
        e.run([q(0),q(1,size=7),q(2)],strategy)
        self.assertEqual([f.quantity for f in e.fills],[5,2])
        self.assertEqual(e.orders[2].remaining,3)
        self.assertEqual(e.orders[2].status,Status.CANCELLED)

    def test_limit_checks_adjusted_price(self):
        e = Engine(execution=ExecutionModel(0,10))
        e.run([q(0),q(1),q(2,98,99)],lambda e, ev: e.submit('X','buy',1,100) if ev.timestamp==T else None)
        self.assertEqual(e.fills[0].timestamp,T+timedelta(seconds=2))
        self.assertLessEqual(e.fills[0].price,100)

    def test_risk_rejections(self):
        cases = [(10000,RiskLimits(),'sell',1,'short selling disabled'),
                 (10000,RiskLimits(max_position=1),'buy',2,'position limit'),
                 (10,RiskLimits(),'buy',1,'insufficient cash'),
                 (1000,RiskLimits(max_gross_leverage='0.1'),'buy',2,'gross leverage limit')]
        for cash,risk,side,qty,reason in cases:
            with self.subTest(reason=reason):
                e=Engine(cash,risk=risk)
                e.run([q(0),q(1)],lambda e,ev: e.submit('X',side,qty) if ev.timestamp==T else None)
                self.assertEqual(e.orders[1].reason,reason)
                self.assertEqual(e.fills,[])

    def test_multiple_orders_cannot_overspend(self):
        e=Engine(150,ExecutionModel(0,0))
        def strategy(e,ev):
            if ev.timestamp==T:
                e.submit('X','buy',1)
                e.submit('X','buy',1)
        e.run([q(0),q(1)],strategy)
        self.assertEqual(len(e.fills),1)
        self.assertEqual(e.orders[2].status,Status.REJECTED)

    def test_symbol_and_liquidity(self):
        e=Engine()
        e.run([q(0),q(1,symbol='Y'),q(2,size=0),q(3)],lambda e,ev: e.submit('X','buy',1) if ev.timestamp==T else None)
        self.assertEqual(e.fills[0].timestamp,T+timedelta(seconds=3))

    def test_invalid_inputs(self):
        for bid,ask in [(2,1),('NaN',2),(0,2)]:
            with self.assertRaises(ValueError): q(0,bid,ask)
        with self.assertRaises(ValueError): Quote(datetime(2024,1,1),'X',1,2)
        e=Engine()
        with self.assertRaises(ValueError): e.run([q(1),q(0)],lambda *_:None)
        with self.assertRaises(RuntimeError): e.run([],lambda *_:None)

    def test_drawdown(self):
        e=Engine(1000,ExecutionModel(0,0))
        e.run([q(0,100,100),q(1,100,100),q(2,80,80)],lambda e,ev: e.submit('X','buy',1) if ev.timestamp==T else None)
        self.assertEqual(e.summary()['max_drawdown'],'0.02')
        self.assertEqual(e.summary()['return'],'-0.02')

    def test_example_repeatability(self):
        results=[]
        for _ in range(2):
            e=Engine().run(read_quotes('examples/quotes.csv'),MovingAverageCross())
            self.assertEqual(len(e.history),52)
            self.assertGreater(len(e.fills),0)
            results.append(e.summary())
        self.assertEqual(*results)

    def test_short_round_trip(self):
        e=Engine(10000,ExecutionModel(0,0),RiskLimits(allow_short=True))
        def strategy(e,ev):
            if ev.timestamp==T: e.submit('X','sell',10)
            if ev.timestamp==T+timedelta(seconds=1): e.submit('X','buy',10)
        e.run([q(0,100,100),q(1,100,100),q(2,90,90)],strategy)
        self.assertEqual(e.portfolio.cash,10100)
        self.assertEqual(e.portfolio.realized_pnl,100)

class AccountingTests(unittest.TestCase):
    def test_average_cost_reversal_and_fees(self):
        p=Portfolio(10000)
        for side,qty,price in [(Side.BUY,10,100),(Side.BUY,10,120),(Side.SELL,25,130)]:
            p.apply(Fill(1,T,'X',side,qty,D(price),D(1)))
        self.assertEqual(p.realized_pnl,400)
        self.assertEqual(p.positions['X'].quantity,-5)
        self.assertEqual(p.positions['X'].average_price,130)
        p.apply(Fill(1,T,'X',Side.BUY,5,D(125),D(1)))
        self.assertEqual(p.realized_pnl,425)
        self.assertEqual(p.cash,10421)
        self.assertEqual(p.positions['X'].average_price,0)
        self.assertEqual(p.fees,4)

if __name__=='__main__': unittest.main()
