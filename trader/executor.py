from abc import ABC, abstractmethod
from aioreactive.core import AsyncAnonymousObserver
import aioreactive.core as rx


class Executor(ABC):
    async def consume(self, fairs_feed):
        await rx.subscribe(fairs_feed, AsyncAnonymousObserver(self._tick))

    @abstractmethod
    async def _tick(self, fairs):
        pass
