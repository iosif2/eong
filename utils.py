import asyncio
import threading


class ThreadSafeCacheable:
    def __init__(self, co):
        self.co = co
        self.done = False
        self.result = None
        self.lock = threading.Lock()

    def __await__(self):
        while True:
            if self.done:
                return self.result
            if self.lock.acquire(blocking=False):
                self.result = yield from self.co.__await__()
                self.done = True
                return self.result
            else:
                yield from asyncio.sleep(0.005)


def cacheable(f):
    def wrapped(*args, **kwargs):
        r = f(*args, **kwargs)
        return ThreadSafeCacheable(r)
    return wrapped


def divide_messages_for_embed(messages: list):
    msgs = []
    embed_count = 0
    msgs.append('')
    for msg in messages:
        if not isinstance(msg, str):
            continue
        if len(msgs[embed_count] + msg) > 3500:
            embed_count += 1
            msgs.append('')
        msgs[embed_count] += msg + "\n"
    return msgs


def duration_to_string(duration: int):
    seconds = duration % (24 * 3600)
    hour = seconds // 3600
    seconds %= 3600
    minutes = seconds // 60
    seconds %= 60
    if hour > 0:
        return "%dh %02dm %02ds" % (hour, minutes, seconds)
    else:
        return "%02dm %02ds" % (minutes, seconds)


def head(async_iterator): return async_iterator.__anext__()
