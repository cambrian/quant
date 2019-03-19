import asyncio


def call_async(fn):
    return asyncio.get_event_loop().run_in_executor(None, fn)
