from trader.executor.base import Executor


class Dummy(Executor):
    """A shitty executor for testing purposes."""

    def tick(self, fairs):
        # TODO
        pass
