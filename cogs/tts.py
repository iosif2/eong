import asyncio
import os
import random
from tempfile import gettempdir
from contextlib import closing
import utils

import nextcord
from nextcord import Interaction, slash_command, message_command, user_command, Message, Member, SlashOption
from nextcord.ext import commands
from boto3 import Session
from botocore.exceptions import BotoCoreError, ClientError

import config
from config import Config

logger = config.getLogger()


def tts(txt, speaker):
    session = Session(aws_access_key_id=Config.aws_access_key_id, aws_secret_access_key=Config.aws_secret_access_key,
                      region_name=Config.region_name)
    polly = session.client("polly")
    try:
        response = polly.synthesize_speech(
            Text=txt, OutputFormat="mp3", VoiceId=speaker)
    except (BotoCoreError, ClientError):
        return None
    if "AudioStream" in response:
        with closing(response["AudioStream"]) as stream:
            output = os.path.join(gettempdir(), "speech.mp3")
            try:
                with open(output, "wb") as file:
                    file.write(stream.read())
            except IOError:
                return None
    else:
        return None
    return output


def get_keyword_info(t):
    for key, value in Config.keywords.items():
        if key in t:
            if isinstance(value, list):
                return random.choice(value)
            return value
    return False


def get_voice(initial):
    if initial in Config.voices.keys():
        return Config.voices[initial]
    else:
        return False


async def check_tts_message(message):
    if message.content.startswith('dc'):
        voice_client = message.guild.voice_client
        if voice_client is not None:
            await voice_client.disconnect()

    keyword = get_keyword_info(message.content)

    if keyword or message.content.startswith(Config.prefix):
        voice_client = message.guild.voice_client
        source = None
        if keyword:
            source = Config.SERVER_URL + \
                Config.ENDPOINTS['FILES'] + keyword
            logger.info(
                f'author : {message.author}, voice : {keyword}, text : {message.content}')
        else:
            voice = get_voice(message.content[1:2])
            if voice:
                source = tts(message.content[2:], voice)
                logger.info(
                    f'[TTS] author : {message.author}, voice : {voice}, text : {message.content[2:]}')
        if voice_client is None:
            if message.author.voice:
                voice_client = await message.author.voice.channel.connect(reconnect=True)
        else:
            if message.author.voice:
                await voice_client.move_to(message.author.voice.channel)
        if source is not None:
            while voice_client.is_playing():
                await asyncio.sleep(0.1)
            voice_client.play(nextcord.PCMVolumeTransformer(
                original=nextcord.FFmpegPCMAudio(source), volume=Config.volume_tts))


class TTSCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def read_message(self, interaction: Interaction, voice: str, message: Message):
        source = tts(message.content, voice)

        if source is None:
            return await interaction.send('오류가 발생했습니다.', ephemeral=True)
        logger.info(
            f'[TTS] author : {interaction.user}, voice : {voice}, text : {message.content}')
        voice_client = interaction.guild.voice_client
        if voice_client is None:
            if interaction.user.voice:
                voice_client = await interaction.user.voice.channel.connect(reconnect=True)
        else:
            if interaction.user.voice:
                await voice_client.move_to(interaction.user.voice.channel)
        if source is not None:
            while voice_client.is_playing():
                await asyncio.sleep(0.1)
            voice_client.play(nextcord.PCMVolumeTransformer(
                original=nextcord.FFmpegPCMAudio(source), volume=Config.volume_tts))
            await interaction.send(content='**Read**', ephemeral=True)

    @message_command(name='Filiz')
    async def _read_filiz(self, interaction: Interaction, message: Message):
        await self.read_message(interaction, 'Filiz', message)

    @message_command(name='Takumi')
    async def _read_takumi(self, interaction: Interaction, message: Message):
        await self.read_message(interaction, 'Takumi', message)

    @message_command(name='Seoyeon')
    async def _read_seoyeon(self, interaction: Interaction, message: Message):
        await self.read_message(interaction, 'Seoyeon', message)

    @message_command(name='Enrique')
    async def _read_enrique(self, interaction: Interaction, message: Message):
        await self.read_message(interaction, 'Enrique', message)


def setup(bot):
    bot.add_cog(TTSCog(bot))
