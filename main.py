import nextcord
from nextcord.ext import commands, tasks

import os
import random

from config import Config
from cogs.tts import check_tts_message


logger = Config.getLogger()

bot = commands.Bot()
musicBot = commands.Bot()


@bot.event
async def on_message(message):
    if message.author == bot.user:
        return
    await check_tts_message(message)
    return


@tasks.loop(seconds=5)
async def status_changer():
    await bot.change_presence(status=nextcord.Status.do_not_disturb, activity=nextcord.Game(f"{random.choice(Config.status_messages)}"))


@tasks.loop(seconds=5)
async def status_changer_music():
    await musicBot.change_presence(status=nextcord.Status.do_not_disturb, activity=nextcord.Game(f"{random.choice(Config.status_messages)}"))


@bot.event
async def on_ready():
    print(f'\n\nLogged in as {bot.user.name}({bot.user.id})')
    status_changer.start()
    await musicBot.start(os.getenv('TOKEN_'))
    

@musicBot.event
async def on_ready():
    print(f'\n\nLogged in as {musicBot.user.name}({musicBot.user.id})')
    status_changer_music.start()

for filename in os.listdir("./cogs"):
    if filename.endswith(".py"):
        if 'music' in filename:
            musicBot.load_extension(f'cogs.{filename[:-3]}')
        else:
            bot.load_extension(f"cogs.{filename[:-3]}")

bot.run(os.getenv('TOKEN'))
