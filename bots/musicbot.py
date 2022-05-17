import random

import nextcord
from nextcord.ext import commands, tasks

from config import Config


class MusicBot(commands.Bot):

    async def on_ready(self):
        self.load_extension("cogs.music")
        print(f'\n\nLogged in as {self.user.name}({self.user.id})')
        self.status_changer.start()

    @tasks.loop(seconds=5)
    async def status_changer(self):
        await self.change_presence(status=nextcord.Status.do_not_disturb,
                                   activity=nextcord.Game(f"{random.choice(Config.status_messages)}"))
