#!venv/bin/python
import requests
import tts
import discord
import asyncio
import json
import datetime
import os
from dotenv import load_dotenv
from discord_slash import SlashCommand
import xmltodict

load_dotenv()

client = discord.Client()
slash = SlashCommand(client, sync_commands=True)
voice_clients = {}
latest_covid_data = {}
vol = 0.4
prefix = ';'
keywords = {
    '^오^': 'teemo.mp3',
    '비둘기': 'pigeon.mp3',
    '네이스': 'nayce.mp3',
    '기모링': 'gimoring.mp3',
    '빡빡이': 'bald.mp3',
    '무야호': 'muyaho.mp3',
    '시옹포포': 'sop.mp3',
    'muyaho': 'myh.mp3',
    'ㅇㅈㅇㅈㅎㄴ': 'dizzy.mp3',
    '🖕': 'fy.mp3',
    'ㅃ!': 'bye.mp3',
    '안물': 'anmul.mp3'
}

voices = {
    't': 'Takumi',
    'm': 'Matthew',
    'f': 'Filiz',
    'e': 'Enrique',
    'z': 'Zeina',
    'l': 'Lotte',
    's': 'Seoyeon',
    'р': 'Tatyana'
}
guild_ids = json.loads(os.getenv('guild_ids'))
serviceKey = os.getenv('serviceKey')


def is_me(m):
    return m.author == client.user


def is_registered(t):
    for key in keywords.keys():
        if key in t:
            return key
    else:
        return False


def get_voice(initial):
    if initial in voices.keys():
        return voices[initial]
    else:
        return False


async def discord_webhook(author, voice, text):
    fields = [{'name': 'User', 'value': author.mention, 'inline': True}, {
        'name': voice, 'value': text, 'inline': True}]
    requests.post(
        os.getenv('DISCORD_WEBHOOK_URL'),
        data=json.dumps({
            'content': '',
            'embeds': [
                {
                    'title': 'TTS log',
                    'url': 'https://github.com/pushedq/GGTTS',
                    'color': 5439232,
                    'fields': fields,
                    'author': {
                        'name': 'iosif',
                        'url': 'https://iosif.app',
                        'icon_url': 'https://avatars1.githubusercontent.com/u/54474221?s=460&u'
                                    '=4528d15da4babf939a10038f17427b44483dbc0f&v=4 '
                    },
                    'footer': {
                        'text': 'losif',
                        'icon_url': 'https://avatars1.githubusercontent.com/u/54474221?s=460&u'
                                    '=4528d15da4babf939a10038f17427b44483dbc0f&v=4 '
                    },
                    'timestamp': datetime.datetime.now(datetime.timezone.utc).isoformat()
                }
            ]

        }),
        headers={'Content-Type': 'application/json; charset=utf-8'}
    )


async def update_covid_new_cases_count():
    today = datetime.datetime.today()
    day_before_yesterday = datetime.datetime.today() - datetime.timedelta(2)
    if latest_covid_data.get('date') != today.strftime('%Y%m%d'):
        res = requests.get('http://openapi.data.go.kr/openapi/service/rest/Covid19/getCovid19InfStateJson', params={
            'serviceKey': serviceKey,
            'startCreateDt': day_before_yesterday.strftime('%Y%m%d'),
            'endCreateDt': today.strftime('%Y%m%d')
        })
        data = json.loads(json.dumps(xmltodict.parse(res.content))).get('response').get('body').get('items').get('item')
        createDt = data[0].get('createDt')[0:10].replace('-', '')
        if latest_covid_data.get('date') != createDt:
            latest_covid_data['date'] = createDt
            latest_covid_data['new_cases_count'] = int(data[0].get('decideCnt')) - int(data[1].get('decideCnt'))
            print(latest_covid_data)


@client.event
async def on_message(message):
    global vol
    date_time = datetime.datetime.now().strftime("%m/%d/%Y, %H:%M:%S")
    channel = message.channel
    content = str(message.content)
    author = message.author
    guild_id = str(message.guild.id) if message.guild else None
    voice_client = voice_clients.get(guild_id) if guild_id else None

    if is_me(message):
        return

    print(f"[{date_time}]{channel}({channel.id}) |  {author}({author.id}): {content}")
    index = is_registered(content)
    if index or content.startswith(prefix):
        source = None
        if index:
            source = keywords[index]
            await discord_webhook(author, index, content)
        else:
            voice = get_voice(content[1:2])
            if voice:
                source = tts.tts(content[2:], voice)
                await discord_webhook(author, voice, content[2:])
        if voice_client is None:
            if author.voice:
                voice_clients[guild_id] = await author.voice.channel.connect()
                voice_client = voice_clients.get(guild_id)
            else:
                await channel.send('연결먼저 ㄱ', delete_after=5)
        while voice_client.is_playing():
            await asyncio.sleep(0.1)
        if source is not None:
            voice_client.play(discord.PCMVolumeTransformer(original=discord.FFmpegPCMAudio(source), volume=vol))
        while voice_client.is_playing():
            await asyncio.sleep(0.1)
        for i in range(300):
            await asyncio.sleep(1)
            if voice_client.is_playing():
                break
            if i == 299:
                await voice_client.disconnect()
                voice_clients.pop(guild_id)

    if content.startswith('vol'):
        arg = content[3:].replace(' ', '')
        if arg.__len__() > 0 and arg.isdigit():
            if 0 < int(arg) <= 100:
                vol = int(arg) / 100
        embed = discord.Embed(title="**Volume**",
                              description=f'{int(vol * 100)}%', color=0xff2f00)
        await channel.send(embed=embed, delete_after=5)

    if content.startswith('dc'):
        if voice_client:
            await voice_client.disconnect()
            voice_clients.pop(guild_id)
    return


@client.event
async def on_ready():
    print('\n\n\n\nLogged in as')
    print(f"{client.user.name}({client.user.id})")
    print('------------------------------------------------------------')


@slash.slash(name="covid", guild_ids=guild_ids, description='COVID-19')
async def _covid(ctx):
    await update_covid_new_cases_count()
    await ctx.send(f"신규 확진자 {latest_covid_data['new_cases_count']}명 [{latest_covid_data['date']}]")


client.run(os.getenv('TOKEN'))
