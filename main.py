#!venv/bin/python
from covid import Covid, CovidCog
import tts
import nextcord
from nextcord.ext import tasks
import asyncio
import os

import logging
from eyc import EYCCog, EyesYChick
from activity import ActivityCog
from config import Config

logger = Config.getLogger()


client = nextcord.Client()

def is_me(m):
    return m.author == client.user

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

@client.event
async def on_message(message):
    if is_me(message):
        return
    
    content = str(message.content)
    author = message.author
    
    key = is_registered(content)
    
    if key or content.startswith(Config.prefix):
        voice_client = nextcord.utils.get(client.voice_clients, guild=message.guild)
        source = None
        if key:
            source = Config.SERVER_URL + Config.ENDPOINTS['FILES'] + Config.keywords[key]
            logger.info(f'author : {author}, voice : {key}, text : {content}')
        else:
            voice = get_voice(content[1:2])
            if voice:
                source = tts.tts(content[2:], voice)
                logger.info(f'[TTS] author : {author}, voice : {voice}, text : {content[2:]}')
        if voice_client is None:
            if author.voice:
                voice_client = await author.voice.channel.connect(reconnect=True)
        else:
            if author.voice:
                await voice_client.move_to(author.voice.channel)
        while voice_client.is_playing():
            await asyncio.sleep(0.1)
        if source is not None:
            voice_client.play(nextcord.PCMVolumeTransformer(original=nextcord.FFmpegPCMAudio(source), volume=Config.vol))

    if content.startswith('dc'):
        voice_client = nextcord.utils.get(client.voice_clients, guild=message.guild)
        if voice_client:
            logger.info(f'[Command] Disconnecting from {voice_client.channel}, Command issuer : {author}')
            await voice_client.disconnect()
    return

@client.slash_command("clear", guild_ids=Config.guild_ids, description='Clear messages')
async def _clear(interaction: nextcord.Interaction):
    deleted = await interaction.channel.purge(limit=100, check=is_me)
    await interaction.send(f'{len(deleted)}', delete_after=5)

@tasks.loop(seconds=3)
async def counter():
    await client.change_presence(status=nextcord.Status.do_not_disturb, activity=nextcord.Game(f"👀 {client.eyc.count_eyes}  🐥 {client.eyc.count_chick}"))

@client.event
async def on_ready():
    print('\n\n\n\nLogged in as')
    print(f'{client.user.name}({client.user.id})')
    print('------------------------------------------------------------')
    counter.start()
    
client.add_cog(EYCCog(client=client))
client.add_cog(ActivityCog(client=client))
client.add_cog(CovidCog(client=client))
client.eyc = EyesYChick()
client.covid = Covid(serviceKey=Config.serviceKey)
client.run(os.getenv('TOKEN'))