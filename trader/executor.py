from util import MVar

from abc import ABC, abstractmethod
from aiostream import stream

import asyncio


class Executor(ABC):
    def __init__(self):
        self.latest_input_var = MVar()

    async def consume(self, input_feed):
        await self.latest_input_var.consume(input_feed)

    async def run(self):
        while True:
            latest_input = await self.latest_input_var.take()
            await self._tick(latest_input)

    @abstractmethod
    async def _tick(self, input):
        pass
