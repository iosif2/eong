import nextcord
from nextcord.ext import commands, tasks

import os
import random
import asyncio

import tts
from config import Config

logger = Config.getLogger()

bot = commands.Bot()


def is_me(m):
    return m.author.id == bot.user.id


def is_registered(t):
    for key in Config.keywords.keys():
        if key in t:
            return key
    else:
        return False


def get_voice(initial):
    global default_voice
    if initial in Config.voices.keys():
        return Config.voices[initial]
    else:
        return False


@bot.event
async def on_message(message):
    if is_me(message):
        return

    content = str(message.content)
    author = message.author
    key = is_registered(content)
    if key or content.startswith(Config.prefix):
        voice_client = message.guild.voice_client
        source = None
        if key:
            source = Config.SERVER_URL + \
                Config.ENDPOINTS['FILES'] + Config.keywords[key]
            logger.info(f'author : {author}, voice : {key}, text : {content}')
        else:
            voice = get_voice(content[1:2])
            if voice:
                source = tts.tts(content[2:], voice)
                logger.info(
                    f'[TTS] author : {author}, voice : {voice}, text : {content[2:]}')
        if voice_client is None:
            if author.voice:
                voice_client = await author.voice.channel.connect(reconnect=True)
        else:
            if author.voice:
                await voice_client.move_to(author.voice.channel)
        while voice_client.is_playing():
            await asyncio.sleep(0.1)
        if source is not None:
            voice_client.play(nextcord.PCMVolumeTransformer(
                original=nextcord.FFmpegPCMAudio(source), volume=1))
    return


@bot.slash_command("clm", guild_ids=Config.guild_ids, description='Clear messages')
async def _clm(interaction: nextcord.Interaction):
    try:
        deleted = await interaction.channel.purge(limit=100, check=is_me)
    except Exception as e:
        return await interaction.send(f'🤒```\n{e}\n```', delete_after=5)
    await interaction.send(f'{len(deleted)}', delete_after=5)


@tasks.loop(seconds=5)
async def status_changer():
    await bot.change_presence(status=nextcord.Status.do_not_disturb, activity=nextcord.Game(f"{random.choice(Config.status_messages)}"))


@bot.event
async def on_ready():
    print(f'\n\nLogged in as{bot.user.name}({bot.user.id})')
    status_changer.start()


for filename in os.listdir("./cogs"):
    if filename.endswith(".py"):
        bot.load_extension(f"cogs.{filename[:-3]}")

bot.run(os.getenv('TOKEN'))
