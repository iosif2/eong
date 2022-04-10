import itertools
from async_timeout import timeout
from discord import SlashOption
import nextcord
from nextcord.ext import commands
from config import Config
import asyncio
import youtube_dl
from youtube_dl import YoutubeDL
from functools import partial

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
    async def create_source(cls, interaction: nextcord.Interaction, search: str, *, loop, download=False):
        loop = loop or asyncio.get_event_loop()

        to_run = partial(ytdl.extract_info, url=search, download=download)
        data = await loop.run_in_executor(None, to_run)

        if 'entries' in data:
            data = data['entries'][0]

        if download:
            source = ytdl.prepare_filename(data)
        else:
            return {'webpage_url': data['webpage_url'], 'requester': interaction.user, 'title': data['title']}

        return cls(nextcord.FFmpegPCMAudio(source), data=data, requester=interaction.user)

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
                 'queue', 'next', 'current', 'volume')

    def __init__(self, interaction: nextcord.Interaction):

        self.client: nextcord.Client = interaction.client
        self._guild = interaction.guild
        self._channel = interaction.channel

        self.queue = asyncio.Queue()
        self.next = asyncio.Event()

        self.current = None

        interaction.client.loop.create_task(self.player_loop())

    async def player_loop(self):
        await self.client.wait_until_ready()
        while not self.client.is_closed():
            self.next.clear()
            try:
                async with timeout(300):
                    source = await self.queue.get()
            except asyncio.TimeoutError:
                return self.client.loop.create_task(MusicPlayer.destroy(self.client, self._guild))
            if not isinstance(source, YTDLSource):
                try:
                    source = await YTDLSource.regather_stream(source, loop=self.client.loop)
                except Exception as e:
                    await self._channel.send(f'Error while processing')
                    continue
            embed = nextcord.Embed(
                title='Now Playing', description=f'{source.title} {source.web_url} [{source.requester.mention}]', color=nextcord.Color.green())
            await self._channel.send(embed=embed, delete_after=20)
            source.volume = Config.volume
            self.current = source
            await asyncio.sleep(1)
            self._guild.voice_client.play(
                source, after=lambda _: self.client.loop.call_soon_threadsafe(self.next.set))
            await self.next.wait()
            self.current = None

    @classmethod
    async def destroy(self, players, guild):
        try:
            await guild.voice_client.disconnect()
        except AttributeError:
            pass
        try:
            del players[guild.id]
        except KeyError:
            pass


class MusicCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.players = {}

    def get_player(self, interaction: nextcord.Interaction):
        try:
            player = self.players[interaction.guild.id]
        except KeyError:
            player = MusicPlayer(interaction=interaction)
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

    @nextcord.slash_command(name='join', description='Connects to voice channel', guild_ids=Config.guild_ids)
    async def _join(
            self,
            interaction: nextcord.Interaction,
            channel: nextcord.abc.GuildChannel
            = nextcord.SlashOption(name='channel', description='Select the channel to join', channel_types=[nextcord.ChannelType.voice], required=False)):
        await interaction.channel.trigger_typing()
        if not channel:
            channel = interaction.guild.voice_channels[0]
        voice_client = interaction.guild.voice_client

        if voice_client:
            if voice_client.channel.id == channel.id:
                await interaction.send('😕Already connected', delete_after=5)
                return
            else:
                await interaction.send(f'🏃‍♀️Moving to {channel}', delete_after=3)
                await voice_client.move_to(channel)
        else:
            try:
                await channel.connect()
            except asyncio.TimeoutError:
                return
        await interaction.send(f'🙋‍♂️Connected to {channel}', delete_after=5)

    @nextcord.slash_command(name='dc', description='Diconnect the voice client and Destroy the music player', guild_ids=Config.guild_ids)
    async def _dc(self, interaction: nextcord.Interaction):
        await interaction.channel.trigger_typing()
        voice_client = interaction.guild.voice_client
        if not voice_client or not voice_client.is_connected():
            return await interaction.send(content='☹️Bot is **not connected**', delete_after=5)
        player = self.get_player(interaction)
        player.queue._queue.clear()
        await MusicPlayer.destroy(self.players, interaction.guild)
        await interaction.send('😼**Cleared/Disconnected**')

    @nextcord.slash_command(name='play', description='play music.', guild_ids=Config.guild_ids)
    async def _play(self, interaction: nextcord.Interaction, search: str = nextcord.SlashOption(description='keyword', required=True)):
        await interaction.channel.trigger_typing()
        voice_client = interaction.guild.voice_client
        if not voice_client or not voice_client.is_connected():
            return await interaction.send(content='☹️Bot is **not connected**', delete_after=5)

        player = self.get_player(interaction=interaction)
        try:
            source = await YTDLSource.create_source(interaction, search, loop=interaction.client.loop, download=False)
        except youtube_dl.utils.DownloadError as e:
            return await interaction.send(f'🤒Video unavilable```ansi\n{e}\n```', delete_after=5)
        await player.queue.put(source)
        embed = nextcord.Embed(
            title='😎Added to Queue', description=f'+ [{source["title"]}]', color=nextcord.Color.green())
        await interaction.send(embed=embed, delete_after=20)

    @nextcord.slash_command(name='pause', description='Pauses the player', guild_ids=Config.guild_ids)
    async def _pause(self, interaction: nextcord.Interaction):
        await interaction.channel.trigger_typing()
        voice_client = interaction.guild.voice_client
        if not voice_client or not voice_client.is_connected():
            return await interaction.send(content='☹️Bot is **not connected**', delete_after=5)
        if not voice_client.is_playing():
            return await interaction.send(content='☹️Bot is **not playing**', delete_after=5)
        voice_client.pause()
        embed = nextcord.Embed(
            title='⏸Paused', description=f'{interaction.user.mention}', color=nextcord.Color.orange())
        await interaction.send(embed=embed, delete_after=20)

    @nextcord.slash_command(name='resume', description='Resumes the player', guild_ids=Config.guild_ids)
    async def _resume(self, interaction: nextcord.Interaction):
        await interaction.channel.trigger_typing()
        voice_client = interaction.guild.voice_client
        if not voice_client or not voice_client.is_connected():
            return await interaction.send(content='☹️Bot is **not connected**', delete_after=5)
        if not voice_client.is_paused():
            return await interaction.send(content='☹️Bot is **not paused**', delete_after=5)
        voice_client.resume()
        embed = nextcord.Embed(
            title='▶️**Resume**', description=f'{interaction.user.mention}', color=nextcord.Color.green())
        await interaction.send(embed=embed, delete_after=20)

    @nextcord.slash_command(name='skip', description='Skips current music', guild_ids=Config.guild_ids)
    async def _skip(self, interaction: nextcord.Interaction):
        await interaction.channel.trigger_typing()
        voice_client = interaction.guild.voice_client
        if not voice_client or not voice_client.is_connected():
            return await interaction.send(content='☹️Bot is **not connected**', delete_after=5)

        if voice_client.is_paused():
            pass
        elif not voice_client.is_playing:
            return

        voice_client.stop()
        embed = nextcord.Embed(
            title='⏩**Skip**', description=f'{interaction.user.mention}', color=nextcord.Color.orange())
        await interaction.send(embed=embed, delete_after=5)

    @nextcord.slash_command(name='queue', description='Show queue', guild_ids=Config.guild_ids)
    async def _queue(self, interaction: nextcord.Interaction):
        await interaction.channel.trigger_typing()
        voice_client = interaction.guild.voice_client
        if not voice_client or not voice_client.is_connected():
            return await interaction.send(content='☹️Bot is **not connected**', delete_after=5)
        player = self.get_player(interaction)
        if player.queue.empty():
            return await interaction.send('Queue is **empty**.')

        upcoming = list(itertools.islice(player.queue._queue,
                        0, int(len(player.queue._queue))))
        fmt = '\n'.join(
            f"`{i + 1}.` [{upcoming[i]['title']}]({upcoming[i]['webpage_url']}) | ` Requested by: `{upcoming[i]['requester'].mention}\n" for i in range(len(upcoming)))
        fmt = f"\n__Now Playing__:\n[{voice_client.source.title}]({voice_client.source.web_url}) | ` {self.duration_to_string(voice_client.source.duration)}` Requested by: {voice_client.source.requester.mention}\n\n__Up Next:__\n" + \
            fmt + f"\n**{len(upcoming)} songs in queue**"
        embed = nextcord.Embed(
            title=f'🎧Queue for {interaction.guild.name}', description=fmt, color=nextcord.Color.yellow())
        await interaction.send(embed=embed, delete_after=30)

    @nextcord.slash_command(name='np', description='Now playing', guild_ids=Config.guild_ids)
    async def _now_playing(self, interaction: nextcord.Interaction):
        await interaction.channel.trigger_typing()
        voice_client = interaction.guild.voice_client
        if not voice_client or not voice_client.is_connected():
            return await interaction.send(content='☹️Bot is **not connected**', delete_after=5)
        if not voice_client.is_playing() and not voice_client.is_paused():
            return await interaction.send(content='☹️Bot is **not playing**', delete_after=5)
        fmt = f"\n__Now Playing__:\n[{voice_client.source.title}]({voice_client.source.web_url}) | ` {self.duration_to_string(voice_client.source.duration)}` Requested by: {voice_client.source.requester.mention}"
        embed = nextcord.Embed(
            title=f'🎧Now Playing {interaction.guild.name}', description=fmt, color=nextcord.Color.yellow())
        await interaction.send(embed=embed, delete_after=30)

    @nextcord.slash_command(name='remove', description='Remove music from queue', guild_ids=Config.guild_ids)
    async def _remove(self, interaction: nextcord.Interaction, index: int = SlashOption(required=False, default=1)):
        await interaction.channel.trigger_typing()
        voice_client = interaction.guild.voice_client
        if not voice_client or not voice_client.is_connected():
            return await interaction.send(content='☹️Bot is **not connected**', delete_after=5)
        player = self.get_player(interaction)

        try:
            removed = player.queue._queue[index-1]
            del player.queue._queue[index-1]
            embed = nextcord.Embed(
                title='', description=f'🗑**Removed** [{removed["title"]}]', color=nextcord.Color.green())
        except:
            embed = nextcord.Embed(
                title='', description=f'😿Could not find a track for "{index}"', color=nextcord.Color.red())
        await interaction.send(embed=embed, delete_after=5)

    @nextcord.slash_command(name='clear', description='Clear the entire queue', guild_ids=Config.guild_ids)
    async def _clear(self, interaction: nextcord.Interaction):
        await interaction.channel.trigger_typing()
        voice_client = interaction.guild.voice_client
        if not voice_client or not voice_client.is_connected():
            return await interaction.send(content='☹️Bot is **not connected**', delete_after=5)
        player = self.get_player(interaction)
        player.queue._queue.clear()
        await interaction.send('😼**Cleared**')

    @nextcord.slash_command(name='volume', description='Get/Set volume', guild_ids=Config.guild_ids)
    async def _volume(self, interaction: nextcord.Interaction, volume: int = nextcord.SlashOption(description="Volume", required=False, min_value=0, max_value=100)):
        await interaction.channel.trigger_typing()
        if not volume:
            await interaction.send(f'Volume : **{Config.volume*100} %**', delete_after=5)
        else:
            await interaction.send(f'Volume : {Config.volume*100} % -> **{volume} %**', delete_after=5)
            Config.volume = volume / 100
            voice_client = interaction.guild.voice_client
            if voice_client and voice_client.is_connected():
                voice_client.source.volume = Config.volume


def setup(bot: commands.Bot):
    bot.add_cog(MusicCog(bot=bot))
