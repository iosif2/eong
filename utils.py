import aiohttp
import asyncio
import threading
import nextcord

from config import Config

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


async def send_ephemeral_message(interaction: nextcord.Interaction, content: str, embeds: list = None):
    _embeds = []
    if embeds:
        _embeds = [_.to_dict() for _ in embeds]
    data = {
        'type': 4,
        'data': {
            'content': content,
            'embeds': _embeds,
            'flags': 1 << 6,
        }
    }
    async with aiohttp.ClientSession() as session:
        await session.post(Config.DISCORD_API_V9 + f'/interactions/{interaction.id}/{interaction.token}/callback', json=data)


async def edit_message(interaction: nextcord.Interaction, content: str, embeds: list = None):
    _embeds = []
    if embeds:
        _embeds = [_.to_dict() for _ in embeds]
    data = {
        'content': content,
        'embeds': _embeds
    }
    async with aiohttp.ClientSession() as session:
        await session.patch(Config.DISCORD_API_V9 + f'/interactions/{interaction.application_id}/{interaction.token}/messages/@original', json=data)

def divide_messages_for_embed(list: list):
    msgs = []
    embed_count = 0
    msgs.append('')
    for msg in list:
        if type(msg) is not str:
            continue
        if len(msgs[embed_count] + msg) > 3000:
            embed_count += 1
            msgs.append('')
        msgs[embed_count] += msg + "\n"
    return msgs