from trader.strategy.base import Strategy


class Dummy(Strategy):
    """A shitty strategy for testing purposes."""

    def tick(self, prices):
        # TODO
        return {}
