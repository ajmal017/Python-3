import logging
from datetime import datetime, timedelta

from strategies import dataloader
from strategies.ib_manager import IBManager
from strategies.strategy_01 import Strategy01
from strategies.trade_signal import *

logger = logging.getLogger(__name__)


def main():
    logger.info("Connecting to IB...")
    manager = IBManager("127.0.0.1", 7497, 0)
    logger.info("Server version: %s, connection time: %s",
                manager.serverVersion(),
                manager.twsConnectionTime())
    strategy = run_strategy(manager)
    manager.process_signals(strategy.signals)
    strategy.reset()

    logger.info('Trying to close IB connection')
    manager.disconnect()


def run_strategy(manager):
    strategy = Strategy01()
    strategy.data = load_transcripts()
    strategy.portfolio = load_portfolio(manager)
    logger.info('Run strategy and process signals')
    strategy.run()
    return strategy


def load_transcripts():
    # to_date = datetime(2016, 4, 10)
    # from_date = to_date - timedelta(days=10)
    to_date = datetime.now()
    from_date = to_date - timedelta(days=10)

    logger.info('Load transcripts from the last 10 days')
    ret = dataloader.load_transcripts_between(from_date, to_date)
    return ret


def load_portfolio(manager):
    logger.info('Load portfolio from IB')
    portfolio = {}
    for portfolio_item in manager.load_portfolio():
        contract = portfolio_item[0]
        order = portfolio_item[1]
        portfolio[contract.symbol] = {
            'signal': SignalFactory.get_signal(order, contract),
            'order_id': order.orderId
        }

    return portfolio


if __name__ == '__main__':
    main()