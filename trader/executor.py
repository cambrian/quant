from abc import ABC, abstractmethod
from rx.concurrency.mainloopscheduler import AsyncIOScheduler


class Executor(ABC):
    @abstractmethod
    def __init__(self, *args):
        self.scheduler = AsyncIOScheduler()

    @abstractmethod
    def tick(self, fairs):
        pass

    @abstractmethod
    def consume(self, fairs_feed):
        fairs_feed.subscribe_on(self.scheduler).subscribe(self.tick)
        # Actually do stuff here.
        # Subscribe using `.subscribe_on(AsyncIOScheduler)`.
        pass
