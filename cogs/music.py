import random
import itertools
import asyncio
from async_timeout import timeout
from functools import partial, lru_cache

import nextcord
from nextcord import slash_command, message_command, user_command, SlashOption, Interaction, Message, Member
from nextcord.ext import commands
import youtube_dl
from youtube_dl import YoutubeDL

from config import Config
import utils

youtube_dl.utils.bug_reports_message = lambda: ''

ydl_opts = {
    'format': 'bestaudio/best',
    'outtmpl': 'downloads/%(extractor)s-%(id)s-%(title)s.%(ext)s',
    'restrictfilenames': True,
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0'
}

ffmpegopts = {
    'before_options': '-nostdin',
    'options': '-vn'
}

ytdl = YoutubeDL(ydl_opts)


class YTDLSource(nextcord.PCMVolumeTransformer):

    def __init__(self, source, *, data, requester):
        super().__init__(source)
        self.requester = requester

        self.title = data.get('title')
        self.web_url = data.get('webpage_url')
        self.duration = data.get('duration')

    def __getitem__(self, item: str):
        return self.__getattribute__(item)

    @classmethod
    @lru_cache(maxsize=32)
    @utils.cacheable
    async def create_source(cls, member: nextcord.Member, search: str, *, bot: commands.Bot, download=False):
        loop = bot.loop or asyncio.get_event_loop()

        to_run = partial(ytdl.extract_info, url=search, download=download)
        data = await loop.run_in_executor(None, to_run)

        if 'entries' in data:
            data = data['entries'][0]

        if download:
            source = ytdl.prepare_filename(data)
        else:
            return {'webpage_url': data['webpage_url'], 'requester': member, 'title': data['title']}

        return cls(nextcord.FFmpegPCMAudio(source), data=data, requester=member)

    @classmethod
    async def regather_stream(cls, data, *, loop):
        loop = loop or asyncio.get_event_loop()
        requester = data['requester']

        to_run = partial(ytdl.extract_info,
                         url=data['webpage_url'], download=False)
        data = await loop.run_in_executor(None, to_run)

        return cls(nextcord.FFmpegPCMAudio(data['url']), data=data, requester=requester)


class MusicPlayer:

    __slots__ = ('client', '_guild', '_channel',
                 'queue', 'next', 'current', 'players', 'volume')

    def __init__(self, interaction: Interaction, players: list):
        self.client = interaction.client
        self._guild = interaction.guild
        self._channel = interaction.channel

        self.queue = asyncio.Queue()
        self.next = asyncio.Event()

        self.current = None
        self.players = players

        interaction.client.loop.create_task(self.player_loop())

    async def player_loop(self):
        await self.client.wait_until_ready()
        while not self.client.is_closed():
            self.next.clear()
            try:
                async with timeout(300):
                    source = await self.queue.get()
            except asyncio.TimeoutError:
                return self.client.loop.create_task(MusicPlayer.destroy(self.players, self._guild))
            if not isinstance(source, YTDLSource):
                try:
                    source = await YTDLSource.regather_stream(source, loop=self.client.loop)
                except Exception as e:
                    await self._channel.send(f'🤕 Error while processing')
                    continue
            source.volume = Config.volume_music
            self.current = source
            await asyncio.sleep(0.5)
            self._guild.voice_client.play(
                source, after=lambda _: self.client.loop.call_soon_threadsafe(self.next.set))
            await asyncio.sleep(0.5)
            if self._guild.voice_client.is_playing():
                embed = nextcord.Embed(
                    title='🎧 Now Playing', description=f'{source.title} {source.web_url} [{source.requester.mention}]', color=nextcord.Color.green())
            else:
                embed = nextcord.Embed(
                    title='🤕 Error / Skipping to next', description=f'{source.title} {source.web_url} [{source.requester.mention}]', color=nextcord.Color.green())
            await self._channel.send(embeds=[embed], delete_after=10)
            await self.next.wait()
            self.current = None

    @classmethod
    async def destroy(self, players, guild):
        try:
            del players[guild.id]
        except KeyError:
            pass
        voice_client = guild.voice_client
        if voice_client and voice_client.is_connected():
            await voice_client.disconnect()


class MusicCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.players = {}
        self.saved_queue = {}

    def get_player(self, interaction: Interaction):
        try:
            player = self.players[interaction.guild.id]
        except KeyError:
            player = MusicPlayer(interaction, self.players)
            self.players[interaction.guild.id] = player
        return player

    def duration_to_string(self, duration: int):
        seconds = duration % (24 * 3600)
        hour = seconds // 3600
        seconds %= 3600
        minutes = seconds // 60
        seconds %= 60
        if hour > 0:
            return "%dh %02dm %02ds" % (hour, minutes, seconds)
        else:
            return "%02dm %02ds" % (minutes, seconds)

    @slash_command("clm", guild_ids=Config.guild_ids, description='Clear messages')
    async def _clm(self, interaction: Interaction):
        try:
            deleted = await interaction.channel.purge(limit=100, check=lambda m: m.author == self.bot.user)
        except Exception as e:
            return await interaction.send(f'🤒```\n{e}\n```', delete_after=5)
        await interaction.send(f'{len(deleted)}', delete_after=5)

    @slash_command(name='join', description='Connects to voice channel', guild_ids=Config.guild_ids)
    async def _join(
            self,
            interaction: Interaction,
            channel: nextcord.abc.GuildChannel
            = SlashOption(name='channel', description='Select the channel to join', channel_types=[nextcord.ChannelType.voice], required=False)):
        await interaction.channel.trigger_typing()
        if not channel:
            channel = interaction.guild.voice_channels[0]
        voice_client = interaction.guild.voice_client

        if voice_client:
            if voice_client.channel.id == channel.id:
                await interaction.send('😕 Already connected', delete_after=5)
                return
            else:
                await interaction.send(f'🏃‍♀️ Moving to {channel}', delete_after=3)
                await voice_client.move_to(channel)
        else:
            try:
                await channel.connect()
            except asyncio.TimeoutError:
                return

        await interaction.send(f'🙋‍♂️ Connected to {channel}', delete_after=5)

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

    @slash_command(name='dc', description='Diconnect the voice client and Destroy the music player', guild_ids=Config.guild_ids)
    async def _dc(self, interaction: Interaction):
        await interaction.channel.trigger_typing()
        voice_client = interaction.guild.voice_client
        if not voice_client or not voice_client.is_connected():
            return await interaction.send(content='☹️ Bot is **not connected**')
        player = self.get_player(interaction)
        player.queue._queue.clear()
        voice_client.stop()
        await voice_client.disconnect()
        await interaction.send('😼 **Disconnected** [{interaction.user.mention}]', delete_after=5)

    @message_command(name='Find and Play', guild_ids=Config.guild_ids)
    async def _findNplay(self, interaction: Interaction, message: Message):
        voice_client = interaction.guild.voice_client
        if not voice_client or not voice_client.is_connected():
            return await utils.send_ephemeral_message(interaction=interaction, content='☹️ Bot is **not connected**',)
        player = self.get_player(interaction=interaction)
        msg = ''
        for keyword in message.content.split(','):
            if keyword.isspace():
                continue
            try:
                source = await YTDLSource.create_source(member=interaction.user, search=keyword, bot=interaction.client, download=False)
            except youtube_dl.utils.DownloadError as e:
                msg += f'! Video Unavailable ```ansi\n{e}\n```'
                break
            await player.queue.put(source)
            msg += f'+ Added [{source["title"]}]\n'
        msgs = utils.divide_messages_for_embed(msg.strip().split('\n'))
        for i in range(len(msgs)):
            if i == 0:
                embed = nextcord.Embed(
                    title=f'😎 Added to queue [Page({i + 1}/{len(msgs)})]', description=msgs[i], color=nextcord.Color.green())
            else:
                embed = nextcord.Embed(
                    title=f'[Page({i + 1}/{len(msgs)})]', description=msgs[i], color=nextcord.Color.yellow())
            await utils.send_ephemeral_message(interaction=interaction, content='', embeds=[embed])

    @slash_command(name='play', description='play music.', guild_ids=Config.guild_ids)
    async def _play(self, interaction: Interaction, search: str = SlashOption(description='keyword or [multiple, keywords, seperated, with, comma]', required=True)):
        await interaction.channel.trigger_typing()
        voice_client = interaction.guild.voice_client
        if not voice_client or not voice_client.is_connected():
            return await interaction.send(content='☹️ Bot is **not connected**', delete_after=5)
        await interaction.send(f'🔍 Searching... [{interaction.user.mention}] ', delete_after=10)
        sent = await interaction.original_message()
        player = self.get_player(interaction=interaction)
        msg = ''
        for keyword in search.split(','):
            if keyword.isspace():
                continue
            try:
                source = await YTDLSource.create_source(member=interaction.user, search=keyword, bot=interaction.client, download=False)
            except youtube_dl.utils.DownloadError as e:
                msg += f'! Video Unavailable ```ansi\n{e}\n```'
                break
            await player.queue.put(source)
            msg += f'+ Added [{source["title"]}]\n'
        msgs = utils.divide_messages_for_embed(msg.strip().split('\n'))
        for i in range(len(msgs)):
            if i == 0:
                embed = nextcord.Embed(
                    title=f'😎 Added to queue [Page({i + 1}/{len(msgs)})]', description=msgs[i], color=nextcord.Color.green())
            else:
                embed = nextcord.Embed(
                    title=f'[Page({i + 1}/{len(msgs)})]', description=msgs[i], color=nextcord.Color.yellow())
            await interaction.send(embeds=[embed], delete_after=10)
    
    @slash_command(name='stop', description='stop player', guild_ids=Config.guild_ids)
    async def _stop(self, interaction: Interaction):
        await interaction.channel.trigger_typing()
        voice_client = interaction.guild.voice_client
        if not voice_client or not voice_client.is_connected():
            return await interaction.send(content='☹️ Bot is **not connected**', delete_after=5)

        if voice_client.is_paused():
            pass
        elif not voice_client.is_playing:
            return
        player = self.get_player(interaction)
        player.queue._queue.clear()
        voice_client.stop()
        await interaction.send(content=f'🛑 **Stopped** [{interaction.user.mention}]', delete_after=5)
    
    @slash_command(name='np', description='Now playing', guild_ids=Config.guild_ids)
    async def _now_playing(self, interaction: Interaction):
        await interaction.channel.trigger_typing()
        voice_client = interaction.guild.voice_client
        if not voice_client or not voice_client.is_connected():
            return await interaction.send(content='☹️ Bot is **not connected**', delete_after=5)
        if not voice_client.is_playing() and not voice_client.is_paused():
            return await interaction.send(content='☹️ Bot is **not playing**', delete_after=5)
        msg = f"\n__Now Playing__:\n[{voice_client.source.title}]({voice_client.source.web_url}) |  `{self.duration_to_string(voice_client.source.duration)} Requested by:` {voice_client.source.requester.mention}"
        embed = nextcord.Embed(
            title=f'🎧 Now Playing {interaction.guild.name}', description=msg, color=nextcord.Color.yellow())
        await interaction.send(embeds=[embed], delete_after=10)

    @slash_command(name='player', description='player main command', guild_ids=Config.guild_ids)
    async def _player(self, interaction: Interaction):
        pass

    @_player.subcommand(name='pause', description='Pauses the player')
    async def _pause(self, interaction: Interaction):
        await interaction.channel.trigger_typing()
        voice_client = interaction.guild.voice_client
        if not voice_client or not voice_client.is_connected():
            return await interaction.send(content='☹️ Bot is **not connected**', delete_after=5)
        if not voice_client.is_playing():
            return await interaction.send(content='☹️ Bot is **not playing**', delete_after=5)
        voice_client.pause()
        await interaction.send(content=f'⏸ **Paused** [{interaction.user.mention}]', delete_after=5)

    @_player.subcommand(name='resume', description='Resumes the player')
    async def _resume(self, interaction: Interaction):
        await interaction.channel.trigger_typing()
        voice_client = interaction.guild.voice_client
        if not voice_client or not voice_client.is_connected():
            return await interaction.send(content='☹️ Bot is **not connected**', delete_after=5)
        if not voice_client.is_paused():
            return await interaction.send(content='☹️ Bot is **not paused**', delete_after=5)
        voice_client.resume()
        await interaction.send(content=f'▶️ **Resume** [{interaction.user.mention}]', delete_after=5)

    @_player.subcommand(name='skip', description='Skips current music')
    async def _skip(self, interaction: Interaction):
        await interaction.channel.trigger_typing()
        voice_client = interaction.guild.voice_client
        if not voice_client or not voice_client.is_connected():
            return await interaction.send(content='☹️ Bot is **not connected**', delete_after=5)

        if voice_client.is_paused():
            pass
        elif not voice_client.is_playing:
            return

        voice_client.stop()
        await interaction.send(content=f'⏩ **Skip** [{interaction.user.mention}]', delete_after=5)

    @_player.subcommand(name='volume', description='Get/Set volume')
    async def _volume(self, interaction: Interaction, volume: int = SlashOption(description="Volume", required=False, min_value=0, max_value=100)):
        await interaction.channel.trigger_typing()
        if not volume:
            await interaction.send(f'Volume : **{Config.volume_music*100} %**', delete_after=5)
        else:
            await interaction.send(f'Volume : {Config.volume_music*100} % -> **{volume} %**', delete_after=5)
            Config.volume_music = volume / 100
            voice_client = interaction.guild.voice_client
            if voice_client and voice_client.is_connected():
                voice_client.source.volume = Config.volume_music

    @slash_command(name='queue', description='queue main command', guild_ids=Config.guild_ids)
    async def _queue(self, interaction: Interaction):
        pass

    @_queue.subcommand(name='show', description='Show queue')
    async def _show(self, interaction: Interaction):
        await interaction.channel.trigger_typing()
        voice_client = interaction.guild.voice_client
        if not voice_client or not voice_client.is_connected():
            return await interaction.send(content='☹️ Bot is **not connected**', delete_after=5)
        player = self.get_player(interaction)
        if player.queue.empty():
            return await interaction.send('Queue is **empty**.', delete_after=5)

        upcoming = list(itertools.islice(player.queue._queue,
                                         0, int(len(player.queue._queue))))

        upcoming_msgs = [f"\n__Now Playing__:\n[{voice_client.source.title}]({voice_client.source.web_url}) |  `{self.duration_to_string(voice_client.source.duration)} Requested by:` {voice_client.source.requester.mention}\n\n__Up Next:__\n"] + [
            f"`{i + 1}.` [{upcoming[i]['title']}]({upcoming[i]['webpage_url']}) | `Requested by:` {upcoming[i]['requester'].mention}\n" for i in range(len(upcoming))] + [f"\n**{len(upcoming)} songs in queue**"]
        msgs = utils.divide_messages_for_embed(upcoming_msgs)
        for i in range(len(msgs)):
            if i == 0:
                embed = nextcord.Embed(
                    title=f'🎧 Queue for {interaction.guild.name} [Page({i + 1})/{len(msgs)})]', description=msgs[i], color=nextcord.Color.yellow())
            else:
                embed = nextcord.Embed(
                    title=f'[Page({i + 1}/{len(msgs)})]', description=msgs[i], color=nextcord.Color.yellow())
            await interaction.send(embeds=[embed], delete_after=10)


    @_queue.subcommand(name='remove', description='Remove music from queue')
    async def _remove(self, interaction: Interaction, index: int = SlashOption(required=False, default=1)):
        await interaction.channel.trigger_typing()
        voice_client = interaction.guild.voice_client
        if not voice_client or not voice_client.is_connected():
            return await interaction.send(content='☹️ Bot is **not connected**', delete_after=5)
        player = self.get_player(interaction)

        try:
            removed = player.queue._queue[index-1]
            del player.queue._queue[index-1]
            embed = nextcord.Embed(
                title='', description=f'🗑 **Removed** [{removed["title"]}]', color=nextcord.Color.green())
        except:
            embed = nextcord.Embed(
                title='', description=f'😿 Could not find a track for "{index}"', color=nextcord.Color.red())
        await interaction.send(embeds=[embed], delete_after=5)

    @_queue.subcommand(name='clear', description='Clear the entire queue')
    async def _clear(self, interaction: Interaction):
        await interaction.channel.trigger_typing()
        voice_client = interaction.guild.voice_client
        if not voice_client or not voice_client.is_connected():
            return await interaction.send(content='☹️ Bot is **not connected**', delete_after=5)
        player = self.get_player(interaction)
        player.queue._queue.clear()
        await interaction.send(f'😼 **Cleared** [{interaction.user.mention}]', delete_after=5)

    @_queue.subcommand(name='shuffle', description='Shuffle the queue')
    async def _shuffle(self, interaction: Interaction):
        await interaction.channel.trigger_typing()
        voice_client = interaction.guild.voice_client
        if not voice_client or not voice_client.is_connected():
            return await interaction.send(content='☹️ Bot is **not connected**', delete_after=5)
        player = self.get_player(interaction)
        if player.queue.empty():
            return await interaction.send('Queue is **empty**.', delete_after=5)
        random.shuffle(player.queue._queue)
        upcoming = list(itertools.islice(player.queue._queue,
                                         0, int(len(player.queue._queue))))
        upcoming_msgs = [f"\n__Now Playing__:\n[{voice_client.source.title}]({voice_client.source.web_url}) |  `{self.duration_to_string(voice_client.source.duration)} Requested by:` {voice_client.source.requester.mention}\n\n__Up Next:__\n"] + [
            f"`{i + 1}.` [{upcoming[i]['title']}]({upcoming[i]['webpage_url']}) | `Requested by:` {upcoming[i]['requester'].mention}\n" for i in range(len(upcoming))] + [f"\n**{len(upcoming)} songs in queue**"]
        msgs = utils.divide_messages_for_embed(upcoming_msgs)
        for i in range(len(msgs)):
            if i == 0:
                embed = nextcord.Embed(
                    title=f'🔀 Shuffled {interaction.guild.name} [Page({i + 1})/{len(msgs)})]', description=msgs[i], color=nextcord.Color.yellow())
            else:
                embed = nextcord.Embed(
                    title=f'[Page({i + 1}/{len(msgs)})]', description=msgs[i], color=nextcord.Color.yellow())
            await interaction.send(embeds=[embed], delete_after=10)

    @_queue.subcommand(name='save', description='Save the queue')
    async def _save(self, interaction: Interaction, name: str = SlashOption(required=True)):
        await interaction.channel.trigger_typing()
        voice_client = interaction.guild.voice_client
        if not voice_client or not voice_client.is_connected():
            return await interaction.send(content='☹️ Bot is **not connected**', delete_after=5)
        player = self.get_player(interaction)
        self.saved_queue[name] = player.queue._queue.copy()
        await interaction.send(f'💾 **Saved** `{name}`[{interaction.user.mention}]', delete_after=5)

    @_queue.subcommand(name='load', description='Load a saved queue')
    async def _load(self, interaction: Interaction, name: str = SlashOption(required=True)):
        await interaction.channel.trigger_typing()
        voice_client = interaction.guild.voice_client
        if not voice_client or not voice_client.is_connected():
            return await interaction.send(content='☹️ Bot is **not connected**', delete_after=5)
        await interaction.send(f'💾 Loading... [{interaction.user.mention}] ', delete_after=10)
        sent = await interaction.original_message()
        player = self.get_player(interaction)
        try:
            player.queue._queue.extend(self.saved_queue[name])
        except KeyError:
            return await sent.edit(f'😿 Could not find a queue named "{name}"', delete_after=5)
        upcoming = list(itertools.islice(player.queue._queue,
                                         0, int(len(player.queue._queue))))
        upcoming_msgs = [f"\n__Now Playing__:\n[{voice_client.source.title}]({voice_client.source.web_url}) |  `{self.duration_to_string(voice_client.source.duration)} Requested by:` {voice_client.source.requester.mention}\n\n__Up Next:__\n"] + [
            f"`{i + 1}.` [{upcoming[i]['title']}]({upcoming[i]['webpage_url']}) | `Requested by:` {upcoming[i]['requester'].mention}\n" for i in range(len(upcoming))] + [f"\n**{len(upcoming)} songs in queue**"]
        msgs = utils.divide_messages_for_embed(upcoming_msgs)
        for i in range(len(msgs)):
            if i == 0:
                embed = nextcord.Embed(
                    title=f'🎧 Queue for {interaction.guild.name} [Page({i + 1})/{len(msgs)})]', description=msgs[i], color=nextcord.Color.yellow())
            else:
                embed = nextcord.Embed(
                    title=f'[Page({i + 1}/{len(msgs)})]', description=msgs[i], color=nextcord.Color.yellow())
            await interaction.send(embeds=[embed], delete_after=10)

    @_queue.subcommand(name='list', description='List all saved queues')
    async def _list(self, interaction: Interaction):
        await interaction.channel.trigger_typing()
        voice_client = interaction.guild.voice_client
        if not voice_client or not voice_client.is_connected():
            return await interaction.send(content='☹️ Bot is **not connected**', delete_after=5)
        msg = ''
        for name in self.saved_queue:
            msg += f'`{name}`\n'
        embed = nextcord.Embed(title='💾 Saved Queues',
                               description=msg, color=nextcord.Color.green())
        await interaction.send(embeds=[embed], delete_after=10)

    @_queue.subcommand(name='erase', description='Erase saved queue')
    async def _erase(self, interaction: Interaction, name: str = SlashOption(required=True)):
        await interaction.channel.trigger_typing()
        voice_client = interaction.guild.voice_client
        if not voice_client or not voice_client.is_connected():
            return await interaction.send(content='☹️ Bot is **not connected**', delete_after=5)
        try:
            del self.saved_queue[name]
        except KeyError:
            return await interaction.send(f'😿 Could not find a queue named "{name}"', delete_after=5)
        await interaction.send(f'🗑 **Erased** `{name}`[{interaction.user.mention}]', delete_after=5)


def setup(bot: commands.Bot):
    bot.add_cog(MusicCog(bot=bot))
