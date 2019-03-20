from aiostream import stream

import asyncio
import traceback


class ConsumingException(Exception):
    pass


class MVar(object):
    def __init__(self):
        self.consumed = False
        self.got_value = asyncio.Condition()
        self.value = None

    async def _put(self, value):
        await self.got_value.acquire()
        self.value = value
        self.got_value.notify()
        self.got_value.release()

    # Asynchronously keeps track of the latest element in a stream
    async def consume(self, feed):
        self.consumed = True
        await stream.action(feed, self._put)

    async def put(self, value):
        if self.consumed:
            raise ConsumingException('MVar already consuming a stream')

    async def take(self):
        await self.got_value.acquire()
        await self.got_value.wait()
        taken_value = self.value
        self.value = None
        self.got_value.release()
        return taken_value


def call_async(fn):
    return asyncio.get_event_loop().run_in_executor(None, fn)


async def trace_exceptions(coroutine):
    try:
        await coroutine
    except Exception as e:
        traceback.print_exc()
