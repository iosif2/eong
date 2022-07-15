import os
import random

import nextcord
from cogs.tts import check_tts_message
from nextcord.ext import commands, tasks

from config import Config

from .musicbot import MusicBot as Music


class MainBot(commands.Bot):
    def __init__(self):
        super().__init__(self)
        self.command_prefix = "`"
        for filename in os.listdir("./cogs"):
            if filename.endswith(".py"):
                if "music" in filename:
                    continue
                else:
                    self.load_extension(f"cogs.{filename[:-3]}")

    async def on_ready(self):
        print(f"\n\nLogged in as {self.user.name}({self.user.id})")
        self.status_changer.start()
        music = Music()
        await music.start(os.getenv("TOKEN_"))

    async def on_message(self, message):
        if message.author == self.user:
            return
        await check_tts_message(message)
        return

    @tasks.loop(seconds=5)
    async def status_changer(self):
        await self.change_presence(
            status=nextcord.Status.do_not_disturb,
            activity=nextcord.Game(f"{random.choice(Config.status_messages)}"),
        )
