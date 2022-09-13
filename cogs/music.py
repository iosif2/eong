import asyncio
import itertools
import random
from functools import partial
from multiprocessing.sharedctypes import Value

import nextcord
import youtube_dl
from async_lru import alru_cache
from async_timeout import timeout
from nextcord import (
    Interaction,
    Member,
    Message,
    SlashOption,
    message_command,
    slash_command,
    user_command,
)
from nextcord.ext import commands
from youtube_dl import YoutubeDL

import config
import utils
from config import Config

youtube_dl.utils.bug_reports_message = lambda: ""
logger = config.getLogger()


ydl_opts = {
    "format": "bestaudio/best",
    "outtmpl": "downloads/%(extractor)s-%(id)s-%(title)s.%(ext)s",
    "restrictfilenames": True,
    "noplaylist": True,
    "nocheckcertificate": True,
    "ignoreerrors": False,
    "logtostderr": False,
    "quiet": True,
    "no_warnings": True,
    "default_search": "auto",
    "source_address": "0.0.0.0",
}

ffmpegopts = {"before_options": "-nostdin", "options": "-vn"}

ytdl = YoutubeDL(ydl_opts)


class YTDLSource(nextcord.PCMVolumeTransformer):
    def __init__(self, source, *, data, requester):
        super().__init__(source)
        self.requester = requester

        self.title = data.get("title")
        self.web_url = data.get("webpage_url")
        self.duration = data.get("duration")

    def __getitem__(self, item: str):
        return self.__getattribute__(item)

    @classmethod
    @alru_cache(maxsize=32)
    async def create_source(cls, member: nextcord.Member, search: str, *, bot: commands.Bot, download=False):
        loop = bot.loop or asyncio.get_event_loop()

        to_run = partial(ytdl.extract_info, url=search, download=download)

        data = await loop.run_in_executor(None, to_run)

        if "entries" in data:
            data = data["entries"][0]

        if download:
            source = ytdl.prepare_filename(data)
        else:
            return {
                "webpage_url": data["webpage_url"],
                "requester": member,
                "title": data["title"],
            }
        logger.info(f"create_source() : Created Source {source}")
        return cls(nextcord.FFmpegPCMAudio(source), data=data, requester=member)

    @classmethod
    async def regather_stream(cls, data, *, loop):
        loop = loop or asyncio.get_event_loop()
        requester = data["requester"]

        to_run = partial(ytdl.extract_info, url=data["webpage_url"], download=False)
        data = await loop.run_in_executor(None, to_run)

        return cls(nextcord.FFmpegPCMAudio(data["url"]), data=data, requester=requester)


class MusicPlayer:

    __slots__ = (
        "client",
        "_guild",
        "_channel",
        "queue",
        "next",
        "current",
        "players",
        "volume",
        "_msg",
        "embed_player",
        "embed_status",
        "embed_queue",
        "embeds_msgs",
        "updater_task",
    )

    def __init__(self, interaction: Interaction, players: list, channel=None):
        self.client = interaction.client
        self._guild = interaction.guild
        self._channel = channel if channel is not None else interaction.channel
        self._msg = None
        self.queue = asyncio.Queue()
        self.next = asyncio.Event()
        self.players = players
        self.embed_player = None
        self.embed_status = None
        self.embed_queue = None
        self.embeds_msgs = []
        self.updater_task = asyncio.tasks.create_task(self.message_updater())
        asyncio.tasks.create_task(self.player_loop())

    @classmethod
    async def create(cls, interaction: Interaction, players: list):
        if interaction.channel.type == nextcord.ChannelType.text:
            await interaction.channel.purge(limit=100, check=lambda m: m.author == interaction.client.user)
            new_channel = await interaction.channel.create_thread(name="🐈🎧", type=nextcord.ChannelType.public_thread)
        return cls(interaction, players, channel=new_channel)

    async def message_updater(self):
        try:
            while True:
                await asyncio.sleep(60)
                logger.info(f"message_updater(): Updating player message for {self._guild.name}")
                await self.update_player_msg()
        except asyncio.CancelledError:
            logger.info(f"message_updater(): Cancelled message updater for {self._guild.name}")
            if self._channel.type == nextcord.ChannelType.public_thread:
                await self._channel.delete()
            else:
                await self._msg.delete()
            return

    async def player_loop(self):
        await self.client.wait_until_ready()
        while not self.client.is_closed():
            self.next.clear()
            try:
                async with timeout(300):
                    embed = nextcord.Embed(
                        title="🎧 Player",
                        description="**Idling**",
                        color=nextcord.Color.green(),
                    )
                    await self.set_embed_player(embed)
                    source = await self.queue.get()
            except asyncio.TimeoutError:
                continue
                # return self.client.loop.create_task(MusicPlayer.destroy(self.players, self._guild))
            if not isinstance(source, YTDLSource):
                try:
                    source = await YTDLSource.regather_stream(source, loop=self.client.loop)
                except Exception:
                    await self._channel.send("🤕 Error while processing", delete_after=5)
                    continue
            source.volume = Config.volume_music
            self.current = source
            await asyncio.sleep(0.5)
            self._guild.voice_client.play(
                source,
                after=lambda _: self.client.loop.call_soon_threadsafe(self.next.set),
            )
            logger.info(f"player_loop(): Playing {source.title} requester : {source.requester.name}")
            await asyncio.sleep(0.5)
            if self._guild.voice_client.is_playing():
                embed = nextcord.Embed(
                    title="🎧 Playing",
                    description=f"{source.title} {source.web_url} [{source.requester.mention}]",
                    color=nextcord.Color.green(),
                )
            else:
                embed = nextcord.Embed(
                    title="🤕 Error / Skipping to next",
                    description=f"{source.title} {source.web_url} [{source.requester.mention}]",
                    color=nextcord.Color.green(),
                )
            await self.set_embed_player(embed)
            await self.next.wait()
            self.current = None

    @classmethod
    async def destroy(self, players, guild):
        try:
            voice_client = guild.voice_client
            if voice_client and voice_client.is_connected():
                await voice_client.disconnect()
            players[guild.id].updater_task.cancel()
            await players[guild.id]._msg.delete()
            del players[guild.id]
        except KeyError:
            pass
        logger.info(f"destroy(): Destroyed music player for {guild.name}")

    async def update_player_msg(self):
        embeds = []
        if self.embed_player:
            embeds.append(self.embed_player)
        if self.embed_status:
            embeds.append(self.embed_status)
        if self.embed_queue:
            embeds.append(self.embed_queue)
        embeds += self.embeds_msgs
        if self._msg is None:
            self._msg = await self._channel.send(embeds=embeds)
        else:
            self._msg = await self._msg.edit(embeds=embeds)
        logger.info(f"update_player_msg(): Updated player message for {self._guild.name}")

    async def set_embed_player(self, embed):
        self.embed_player = embed
        await self.update_player_msg()

    async def set_embed_status(self, embed, clear_after: int = None):
        self.embed_status = embed
        await self.update_player_msg()
        if clear_after:

            async def inner_call(delay: float = clear_after):
                await asyncio.sleep(delay)
                await self.clear_embed_status()

            asyncio.create_task(inner_call())

    async def clear_embed_status(self):
        self.embed_status = None
        await self.update_player_msg()

    async def add_embed_queues(self, embeds):
        for embed in embeds:
            await self.add_embed_queue(embed, clear_after=3)
            while self.embed_queue is not None:
                await asyncio.sleep(0.05)

    async def add_embed_queue(self, embed, clear_after=None):
        self.embed_queue = embed
        await self.update_player_msg()
        if clear_after:

            async def inner_call(delay: float = clear_after):
                await asyncio.sleep(delay)
                self.embed_queue = None
                await self.update_player_msg()

        asyncio.create_task(inner_call())

    async def add_embed_msgs(self, embed, clear_after=None):
        self.embeds_msgs.append(embed)
        await self.update_player_msg()
        if clear_after:

            async def inner_call(delay: float = clear_after):
                await asyncio.sleep(delay)
                self.embeds_msgs.remove(embed)
                await self.update_player_msg()

        asyncio.create_task(inner_call())


class MusicCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.players = {}
        self.saved_queue = {}
        self.history = []

    async def get_player(self, interaction: Interaction, create=True):
        try:
            player = self.players[interaction.guild.id]
        except KeyError:
            if create:
                player = await MusicPlayer.create(interaction, self.players)
                self.players[interaction.guild.id] = player
            else:
                return None
        return player

    @slash_command("clm", description="Clear messages")
    async def _clm(self, interaction: Interaction):
        try:
            player = await self.get_player(interaction=interaction)
            deleted = await interaction.channel.purge(
                limit=100,
                check=lambda m: m.author == self.bot.user and player._msg != m,
            )
        except Exception as e:
            return await interaction.send(f"🤒```\n{e}\n```", delete_after=5)
        await interaction.send(f"{len(deleted)}", delete_after=5)

    async def join(
        self,
        interaction,
        member: nextcord.Member = None,
        channel: nextcord.VoiceChannel = None,
        ephemeral=False,
    ):
        await interaction.channel.trigger_typing()
        if not channel:
            if member:
                if member.voice:
                    channel = member.voice.channel
                else:
                    return await interaction.send(content="☹️ User is not connected", ephemeral=ephemeral)
            else:
                channel = interaction.guild.voice_channels[0]
        voice_client = interaction.guild.voice_client
        if voice_client:
            if voice_client.channel.id == channel.id:
                await interaction.send("😕 Already connected", delete_after=5, ephemeral=ephemeral)
                return
            else:
                await interaction.send(f"🏃‍♀️ Moving to {channel}", delete_after=3, ephemeral=ephemeral)
                await voice_client.move_to(channel)
        else:
            try:
                await channel.connect()
            except asyncio.TimeoutError:
                return
        await interaction.send(f"🙋‍♂️ Connected to {channel}", delete_after=5, ephemeral=ephemeral)

    @slash_command(name="join", description="Connects to voice channel")
    async def _join(
        self,
        interaction: Interaction,
        channel: nextcord.abc.GuildChannel = SlashOption(
            name="channel",
            description="Select the channel to join",
            channel_types=[nextcord.ChannelType.voice],
            required=False,
        ),
    ):
        await interaction.channel.trigger_typing()
        await self.join(interaction=interaction, channel=channel)

    @user_command(name="Follow")
    async def _join_user_command(self, interaction: Interaction, member: Member):
        await interaction.channel.trigger_typing()
        await self.join(interaction=interaction, member=member, ephemeral=True)

    @slash_command(name="dc", description="Diconnect the voice client and Destroy the music player")
    async def _dc(self, interaction: Interaction):
        await interaction.channel.trigger_typing()
        voice_client = interaction.guild.voice_client
        if not voice_client or not voice_client.is_connected():
            return await interaction.send(content="☹️ Bot is **not connected**", delete_after=3)
        player = await self.get_player(interaction, create=False)
        if player is not None:
            player.queue._queue.clear()
            voice_client.stop()
            await player.destroy(self.players, interaction.guild)
        else:
            await voice_client.disconnect()
        await interaction.send(f"😼 **Disconnected** [{interaction.user.mention}]", delete_after=5)

    async def play(self, interaction: nextcord.Interaction, search: str, ephemeral=False):
        await interaction.channel.trigger_typing()
        voice_client = interaction.guild.voice_client
        player = await self.get_player(interaction=interaction)
        await player._channel.add_user(interaction.user)
        if not voice_client or not voice_client.is_connected():
            if interaction.user.voice:
                if voice_client:
                    if voice_client.channel.id != interaction.user.voice.channel.id:
                        await voice_client.move_to(interaction.user.voice.channel)
                else:
                    try:
                        await interaction.user.voice.channel.connect()
                    except asyncio.TimeoutError:
                        return await interaction.send(content="😕 Error", delete_after=5, ephemeral=ephemeral)
            else:
                return await interaction.send(
                    content="You are not connected to voice channel.",
                    delete_after=5,
                    ephemeral=ephemeral,
                )

        await interaction.send(
            content=f"🔍 Searching... [{interaction.user.mention}] ",
            delete_after=5,
            ephemeral=ephemeral,
        )

        msg = ""
        for keyword in search.split(","):
            if keyword.isspace():
                continue
            try:
                source = await YTDLSource.create_source(
                    member=interaction.user,
                    search=keyword,
                    bot=interaction.client,
                    download=False,
                )
            except youtube_dl.utils.DownloadError as e:
                msg += f"! Video Unavailable ```ansi\n{e}\n```"
                break
            await player.queue.put(source)
            msg += f'+ Added [{source["title"]}]\n'
        msgs = utils.divide_messages_for_embed(msg.strip().split("\n"))
        for msg in msgs:
            if msgs.index(msg):
                embed = nextcord.Embed(
                    title=f"😎 Added to queue [Page({msgs.index(msg) + 1}/{len(msgs)})]",
                    description=msg,
                    color=nextcord.Color.green(),
                )
            else:
                embed = nextcord.Embed(
                    title=f"[Page({msgs.index(msg) + 1}/{len(msgs)})]",
                    description=msg,
                    color=nextcord.Color.yellow(),
                )
            await interaction.send(embeds=[embed], delete_after=10)

    @message_command(name="Find and Play")
    async def _findNplay(self, interaction: Interaction, message: Message):
        await self.play(interaction=interaction, search=message.content, ephemeral=True)

    @slash_command(name="play", description="play music.")
    async def _play(
        self,
        interaction: Interaction,
        search: str = SlashOption(
            description="keyword or [multiple, keywords, seperated, with, comma]",
            required=True,
        ),
    ):
        await self.play(interaction=interaction, search=search)

    @slash_command(name="stop", description="stop player")
    async def _stop(self, interaction: Interaction):
        await interaction.channel.trigger_typing()
        voice_client = interaction.guild.voice_client
        if not voice_client or not voice_client.is_connected():
            return await interaction.send(content="☹️ Bot is **not connected**", delete_after=3)

        if voice_client.is_paused():
            pass
        elif not voice_client.is_playing:
            return
        player = await self.get_player(interaction=interaction)
        await player._channel.add_user(interaction.user)
        player.queue._queue.clear()
        voice_client.stop()
        embed = nextcord.Embed(
            title="🛑 **Stopped**",
            description=f"[{interaction.user.mention}]",
            color=nextcord.Color.yellow(),
        )
        await player.set_embed_status(embed=embed, clear_after=10)
        await interaction.send("🛑 **Stopped**", delete_after=2)

    @slash_command(name="skip", description="Skips current music")
    async def _skip(self, interaction: Interaction):
        await interaction.channel.trigger_typing()
        voice_client = interaction.guild.voice_client
        if not voice_client or not voice_client.is_connected():
            return await interaction.send(content="☹️ Bot is **not connected**", delete_after=3)
        player = await self.get_player(interaction=interaction)
        await player._channel.add_user(interaction.user)
        if voice_client.is_paused():
            pass
        elif not voice_client.is_playing:
            return
        voice_client.stop()
        embed = nextcord.Embed(
            title="⏩ **Skip**",
            description=f"[{interaction.user.mention}]",
            color=nextcord.Color.yellow(),
        )
        await player.add_embed_msgs(embed, clear_after=10)
        await interaction.send("⏩ **Skip**", delete_after=2)

    @slash_command(name="volume", description="Get/Set volume")
    async def _volume(
        self,
        interaction: Interaction,
        volume: int = SlashOption(description="Volume", required=False, min_value=0, max_value=100),
    ):
        await interaction.channel.trigger_typing()
        if not volume:
            await interaction.send(
                f"Volume : **{Config.volume_music*100} %** [{interaction.user.mention}]",
                delete_after=5,
            )
        else:
            await interaction.send(
                f"Volume : {Config.volume_music*100} % -> **{volume} %** [{interaction.user.mention}]",
                delete_after=5,
            )
            Config.volume_music = volume / 100
            voice_client = interaction.guild.voice_client
            if voice_client and voice_client.is_connected():
                voice_client.source.volume = Config.volume_music

    @slash_command(name="player", description="player main command")
    async def _player(self, interaction: Interaction):
        pass

    @_player.subcommand(name="pause", description="Pauses the player")
    async def _pause(self, interaction: Interaction):
        await interaction.channel.trigger_typing()
        voice_client = interaction.guild.voice_client
        if not voice_client or not voice_client.is_connected():
            return await interaction.send(content="☹️ Bot is **not connected**", delete_after=3)
        if not voice_client.is_playing():
            return await interaction.send(content="☹️ Bot is **not playing**", delete_after=5)
        if voice_client.is_paused():
            return await interaction.send("⏸ **Already Paused**", delete_after=2)
        player = await self.get_player(interaction=interaction)
        await player._channel.add_user(interaction.user)
        voice_client.pause()
        embed = nextcord.Embed(
            title="⏸ **Paused**",
            description=f"[{interaction.user.mention}]",
            color=nextcord.Color.yellow(),
        )
        await player.set_embed_status(embed=embed)
        await interaction.send("⏸ **Paused**", delete_after=2)

    @_player.subcommand(name="resume", description="Resumes the player")
    async def _resume(self, interaction: Interaction):
        await interaction.channel.trigger_typing()
        voice_client = interaction.guild.voice_client
        if not voice_client or not voice_client.is_connected():
            return await interaction.send(content="☹️ Bot is **not connected**", delete_after=3)
        if not voice_client.is_paused():
            return await interaction.send(content="☹️ Bot is **not paused**", delete_after=5)
        player = await self.get_player(interaction=interaction)
        await player._channel.add_user(interaction.user)
        voice_client.resume()
        await player.clear_embed_status()
        await interaction.send(f"⏯ **Resume** [{interaction.user.mention}]", delete_after=2)

    @slash_command(name="queue", description="queue main command")
    async def _queue(self, interaction: Interaction):
        pass

    @_queue.subcommand(name="show", description="Show queue")
    async def _show(self, interaction: Interaction):
        await interaction.channel.trigger_typing()
        voice_client = interaction.guild.voice_client
        if not voice_client or not voice_client.is_connected():
            return await interaction.send(content="☹️ Bot is **not connected**", delete_after=3)
        player = await self.get_player(interaction=interaction)
        await player._channel.add_user(interaction.user)
        if player.queue.empty():
            return await interaction.send("Queue is **empty**.", delete_after=5)
        upcoming = list(itertools.islice(player.queue._queue, 0, int(len(player.queue._queue))))

        upcoming_msgs = (
            [
                f"\n__Now Playing__:\n[{voice_client.source.title}]({voice_client.source.web_url}) | "
                f" `{utils.duration_to_string(voice_client.source.duration)} Requested by:`"
                f" {voice_client.source.requester.mention}\n\n__Up Next:__\n"
            ]
            + [
                f"`{i + 1}.` [{upcoming[i]['title']}]({upcoming[i]['webpage_url']}) | `Requested by:`"
                f" {upcoming[i]['requester'].mention}\n"
                for i in range(len(upcoming))
            ]
            + [f"\n**{len(upcoming)} songs in queue**"]
        )
        msgs = utils.divide_messages_for_embed(upcoming_msgs)
        for msg in msgs:
            if msgs.index(msg) == 0:
                embed = nextcord.Embed(
                    title=f"🎧 Queue for {interaction.guild.name} [Page({msgs.index(msg) + 1})/{len(msgs)})]",
                    description=msg,
                    color=nextcord.Color.yellow(),
                )
            else:
                embed = nextcord.Embed(
                    title=f"[Page({msgs.index(msg) + 1}/{len(msgs)})]",
                    description=msg,
                    color=nextcord.Color.yellow(),
                )
            await interaction.send(embeds=[embed], delete_after=10)

    @_queue.subcommand(name="remove", description="Remove music from queue")
    async def _remove(
        self,
        interaction: Interaction,
        index: int = SlashOption(required=False, default=1),
    ):
        await interaction.channel.trigger_typing()
        voice_client = interaction.guild.voice_client
        if not voice_client or not voice_client.is_connected():
            return await interaction.send(content="☹️ Bot is **not connected**", delete_after=3)
        player = await self.get_player(interaction=interaction)
        await player._channel.add_user(interaction.user)

        try:
            removed = player.queue._queue[index - 1]
            del player.queue._queue[index - 1]
            embed = nextcord.Embed(
                title="",
                description=f'🗑 **Removed** [{removed["title"]}]',
                color=nextcord.Color.green(),
            )
        except Value:
            embed = nextcord.Embed(
                title="",
                description=f'😿 Could not find a track for "{index}"',
                color=nextcord.Color.red(),
            )
        await player.add_embed_msgs(embed, clear_after=10)
        await interaction.send("🗑 **Removed** [{interaction.user.mention}]", delete_after=5)

    @_queue.subcommand(name="clear", description="Clear the entire queue")
    async def _clear(self, interaction: Interaction):
        await interaction.channel.trigger_typing()
        voice_client = interaction.guild.voice_client
        if not voice_client or not voice_client.is_connected():
            return await interaction.send(content="☹️ Bot is **not connected**", delete_after=3)
        player = await self.get_player(interaction=interaction)
        await player._channel.add_user(interaction.user)
        player.queue._queue.clear()
        await interaction.send(f"😼 **Queue Cleared** [{interaction.user.mention}]", delete_after=5)

    @_queue.subcommand(name="shuffle", description="Shuffle the queue")
    async def _shuffle(self, interaction: Interaction):
        await interaction.channel.trigger_typing()
        voice_client = interaction.guild.voice_client
        if not voice_client or not voice_client.is_connected():
            return await interaction.send(content="☹️ Bot is **not connected**", delete_after=3)
        player = await self.get_player(interaction=interaction)
        await player._channel.add_user(interaction.user)
        if player.queue.empty():
            return await interaction.send("Queue is **empty**.", delete_after=5)
        random.shuffle(player.queue._queue)
        upcoming = list(itertools.islice(player.queue._queue, 0, int(len(player.queue._queue))))
        upcoming_msgs = (
            [
                f"\n__Now Playing__:\n[{voice_client.source.title}]({voice_client.source.web_url}) | "
                f" `{utils.duration_to_string(voice_client.source.duration)} Requested by:`"
                f" {voice_client.source.requester.mention}\n\n__Up Next:__\n"
            ]
            + [
                f"`{i + 1}.` [{upcoming[i]['title']}]({upcoming[i]['webpage_url']}) | `Requested by:`"
                f" {upcoming[i]['requester'].mention}\n"
                for i in range(len(upcoming))
            ]
            + [f"\n**{len(upcoming)} songs in queue**"]
        )
        msgs = utils.divide_messages_for_embed(upcoming_msgs)
        for msg in msgs:
            if msgs.index(msg) == 0:
                embed = nextcord.Embed(
                    title=f"🔀 Shuffled {interaction.guild.name} [Page({msgs.index(msg) + 1})/{len(msgs)})]",
                    description=msg,
                    color=nextcord.Color.yellow(),
                )
            else:
                embed = nextcord.Embed(
                    title=f"[Page({msgs.index(msg) + 1}/{len(msgs)})]",
                    description=msg,
                    color=nextcord.Color.yellow(),
                )
            await interaction.send(embeds=[embed], delete_after=10)

    @_queue.subcommand(name="save", description="Save the queue")
    async def _save(self, interaction: Interaction, name: str = SlashOption(required=True)):
        await interaction.channel.trigger_typing()
        voice_client = interaction.guild.voice_client
        if not voice_client or not voice_client.is_connected():
            return await interaction.send(content="☹️ Bot is **not connected**", delete_after=3)
        player = await self.get_player(interaction=interaction)
        await player._channel.add_user(interaction.user)
        self.saved_queue[name] = player.queue._queue.copy()
        await interaction.send(f"💾 **Saved** `{name}`[{interaction.user.mention}]", delete_after=5)

    @_queue.subcommand(name="load", description="Load a saved queue")
    async def _load(self, interaction: Interaction, name: str = SlashOption(required=True)):
        await interaction.channel.trigger_typing()
        voice_client = interaction.guild.voice_client
        if not voice_client or not voice_client.is_connected():
            return await interaction.send(content="☹️ Bot is **not connected**", delete_after=3)
        await interaction.send(f"💾 Loading... [{interaction.user.mention}] ", delete_after=10)
        sent = await interaction.original_message()
        player = await self.get_player(interaction=interaction)
        await player._channel.add_user(interaction.user)
        try:
            player.queue._queue.extend(self.saved_queue[name])
        except IndexError:
            return await sent.edit(f'😿 Could not find a queue named "{name}"', delete_after=5)
        upcoming = list(itertools.islice(player.queue._queue, 0, int(len(player.queue._queue))))
        upcoming_msgs = (
            [
                f"\n__Now Playing__:\n[{voice_client.source.title}]({voice_client.source.web_url}) | "
                f" `{utils.duration_to_string(voice_client.source.duration)} Requested by:`"
                f" {voice_client.source.requester.mention}\n\n__Up Next:__\n"
            ]
            + [
                f"`{i + 1}.` [{upcoming[i]['title']}]({upcoming[i]['webpage_url']}) | `Requested by:`"
                f" {upcoming[i]['requester'].mention}\n"
                for i in range(len(upcoming))
            ]
            + [f"\n**{len(upcoming)} songs in queue**"]
        )
        msgs = utils.divide_messages_for_embed(upcoming_msgs)
        for msg in msgs:
            if msgs.index(msg) == 0:
                embed = nextcord.Embed(
                    title=f"🎧 Queue for {interaction.guild.name} [Page({msgs.index(msg) + 1})/{len(msgs)})]",
                    description=msg,
                    color=nextcord.Color.yellow(),
                )
            else:
                embed = nextcord.Embed(
                    title=f"[Page({msgs.index(msg) + 1}/{len(msgs)})]",
                    description=msg,
                    color=nextcord.Color.yellow(),
                )
            await interaction.send(embeds=[embed], delete_after=10)

    @_queue.subcommand(name="list", description="List all saved queues")
    async def _list(self, interaction: Interaction):
        await interaction.channel.trigger_typing()
        voice_client = interaction.guild.voice_client
        if not voice_client or not voice_client.is_connected():
            return await interaction.send(content="☹️ Bot is **not connected**", delete_after=3)
        msg = ""
        for name in self.saved_queue:
            msg += f"`{name}`\n"
        embed = nextcord.Embed(title="💾 Saved Queues", description=msg, color=nextcord.Color.green())
        await interaction.send(embeds=[embed], delete_after=10)

    @_queue.subcommand(name="erase", description="Erase saved queue")
    async def _erase(self, interaction: Interaction, name: str = SlashOption(required=True)):
        await interaction.channel.trigger_typing()
        voice_client = interaction.guild.voice_client
        if not voice_client or not voice_client.is_connected():
            return await interaction.send(content="☹️ Bot is **not connected**", delete_after=3)
        try:
            del self.saved_queue[name]
        except KeyError:
            return await interaction.send(f'😿 Could not find a queue named "{name}"', delete_after=5)
        await interaction.send(f"🗑 **Erased** `{name}`[{interaction.user.mention}]", delete_after=5)


def setup(bot: commands.Bot):
    bot.add_cog(MusicCog(bot=bot))
