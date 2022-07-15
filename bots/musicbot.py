import random

import nextcord
from nextcord.ext import commands, tasks

from config import Config


class MusicBot(commands.Bot):
    def __init__(self):
        super().__init__(self)
        self.command_prefix = "`"
        self.load_extension("cogs.music")

    async def on_ready(self):
        print(f"\n\nLogged in as {self.user.name}({self.user.id})")
        self.status_changer.start()

    @tasks.loop(seconds=5)
    async def status_changer(self):
        await self.change_presence(
            status=nextcord.Status.do_not_disturb,
            activity=nextcord.Game(f"{random.choice(Config.status_messages)}"),
        )
