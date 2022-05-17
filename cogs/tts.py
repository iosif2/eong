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


from config import Config

logger = Config.getLogger()


def tts(txt, speaker):
    session = Session(aws_access_key_id=Config.aws_access_key_id, aws_secret_access_key=Config.aws_secret_access_key,
                      region_name=Config.region_name)
    polly = session.client("polly")
    try:
        response = polly.synthesize_speech(
            Text=txt, OutputFormat="mp3", VoiceId=speaker)
    except (BotoCoreError, ClientError) as error:
        return None
    if "AudioStream" in response:
        with closing(response["AudioStream"]) as stream:
            output = os.path.join(gettempdir(), "speech.mp3")
            try:
                with open(output, "wb") as file:
                    file.write(stream.read())
            except IOError as error:
                return None
    else:
        return None
    return output


def get_keyword_info(t):
    for key, value in Config.keywords.items():
        if key in t:
            if type(value) == list:
                return random.choice(value)
            return value
    return False


def get_voice(initial):
    global default_voice
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
            return await interaction.send('오류가 발생했습니다.')
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
            await utils.send_ephemeral_message(
                interaction=interaction, content='**Read**')
            while voice_client.is_playing():
                await asyncio.sleep(0.1)
            voice_client.play(nextcord.PCMVolumeTransformer(
                original=nextcord.FFmpegPCMAudio(source), volume=Config.volume_tts))

    @user_command(name='Follow', guild_ids=Config.guild_ids)
    async def _join_user_command(self, interaction: Interaction, member: Member):
        await interaction.channel.trigger_typing()
        voice_client = interaction.guild.voice_client
        if member.voice:
            if voice_client:
                if voice_client.channel.id == member.voice.channel.id:
                    return await utils.send_ephemeral_message(interaction=interaction, content='😕 Already connected')
                else:
                    await voice_client.move_to(member.voice.channel)
                    return await utils.send_ephemeral_message(interaction=interaction, content=f'🏃‍♀️ Moving to {member.voice.channel}')
            else:
                try:
                    await member.voice.channel.connect()

                except asyncio.TimeoutError:
                    return await utils.send_ephemeral_message(interaction=interaction, content='😕 Error')
                await utils.send_ephemeral_message(interaction=interaction, content=f'🙋‍♂️ Connected to {member.voice.channel}')
        else:
            await utils.send_ephemeral_message(interaction=interaction, content=f'😕 User is not connected to voice channel.')

    @slash_command("clm", guild_ids=Config.guild_ids, description='Clear messages')
    async def _clm(self, interaction: Interaction):
        try:
            deleted = await interaction.channel.purge(limit=100, check=lambda m: m.author == self.bot.user)
        except Exception as e:
            return await interaction.send(f'🤒```\n{e}\n```', delete_after=5)
        await interaction.send(f'{len(deleted)}', delete_after=5)

    @slash_command(name='volume', description='Get/Set volume', guild_ids=Config.guild_ids)
    async def _volume(self, interaction: Interaction, volume: int = SlashOption(description="Volume", required=False, min_value=0, max_value=100)):
        await interaction.channel.trigger_typing()
        if not volume:
            await interaction.send(f'Volume : **{Config.volume_tts*100} %**', delete_after=5)
        else:
            await interaction.send(f'Volume : {Config.volume_tts*100} % -> **{volume} %**', delete_after=5)
            Config.volume_tts = volume / 100
            voice_client = interaction.guild.voice_client
            if voice_client and voice_client.is_connected():
                voice_client.source.volume = Config.volume_tts

    @message_command(name='Filiz', guild_ids=Config.guild_ids)
    async def _read_filiz(self, interaction: Interaction, message: Message):
        await self.read_message(interaction, 'Filiz', message)

    @message_command(name='Takumi', guild_ids=Config.guild_ids)
    async def _read_takumi(self, interaction: Interaction, message: Message):
        await self.read_message(interaction, 'Takumi', message)

    @message_command(name='Seoyeon', guild_ids=Config.guild_ids)
    async def _read_seoyeon(self, interaction: Interaction, message: Message):
        await self.read_message(interaction, 'Seoyeon', message)

    @message_command(name='Enrique', guild_ids=Config.guild_ids)
    async def _read_enrique(self, interaction: Interaction, message: Message):
        await self.read_message(interaction, 'Enrique', message)


def setup(bot):
    bot.add_cog(TTSCog(bot))
