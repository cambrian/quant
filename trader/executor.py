from abc import ABC, abstractmethod
from aiostream import stream

import asyncio


class Executor(ABC):
    async def consume(self, fairs_feed, exchange):
        self.exchange = exchange
        await stream.action(fairs_feed, self._tick)

    @abstractmethod
    async def _tick(self, fairs):
        pass
