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
import logging

Log_Format = "%(levelname)s %(asctime)s - %(message)s"

logging.basicConfig(filename = "ggtts.log",
                    filemode = "w",
                    format = Log_Format, 
                    level = logging.INFO)

logger = logging.getLogger()

load_dotenv()
client = discord.Client()
slash = SlashCommand(client, sync_commands=True)
latest_covid_data = {}
vol = 1
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
    'ㅃ!': 'byebye.mp3',
    'ㅂ!' : 'bye.mp3',
    '안물': 'anmul.mp3',
    '애옹': 'meow.mp3',
    '음?' : 'wdis.mp3'
}

default_voice = 't'

voices = {
    ' ': None,
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
    global default_voice
    if initial in voices.keys():
        if initial == ' ':
            if default_voice not in voices.keys():
                default_voice = 't'
            return voices[default_voice]
        return voices[initial]
    else:
        return False


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
    global vol, default_voice
    date_time = datetime.datetime.now().strftime("%m/%d/%Y, %H:%M:%S")
    channel = message.channel
    content = str(message.content)
    author = message.author

    if is_me(message):
        return

    print(f"[{date_time}]{channel}({channel.id}) |  {author}({author.id}): {content}")
    key = is_registered(content)
    if key or content.startswith(prefix):
        voice_client = discord.utils.get(client.voice_clients, guild=message.guild)
        source = None
        if key:
            source = 'mp3_files/' + keywords[key]
            logger.info(f'author : {author}, voice : {key}, text : {content}')
        else:
            voice = get_voice(content[1:2])
            if voice:
                source = tts.tts(content[2:], voice)
                logger.info(f'author : {author}, voice : {voice}, text : {content[2:]}')
        if voice_client is None:
            if author.voice:
                voice_client = await author.voice.channel.connect(reconnect=True)
        else:
            if author.voice:
                await voice_client.move_to(author.voice.channel)
        while voice_client.is_playing():
            await asyncio.sleep(0.1)
        if source is not None:
            voice_client.play(discord.PCMVolumeTransformer(original=discord.FFmpegPCMAudio(source), volume=vol))

    if content.startswith('vol'):
        arg = content[3:].replace(' ', '')
        if arg.__len__() > 0 and arg.isdigit():
            if 0 < int(arg) <= 100:
                vol = int(arg) / 100
        embed = discord.Embed(title="**Volume**",
                              description=f'{int(vol * 100)}%', color=0xff2f00)
        await channel.send(embed=embed, delete_after=5)

    if content.startswith('dc'):
        voice_client = discord.utils.get(client.voice_clients, guild=message.guild)
        if voice_client:
            logger.info(f'Disconnecting from {voice_client.channel}, Command issuer : {author}')
            await voice_client.disconnect()
    return


@client.event
async def on_ready():
    print('\n\n\n\nLogged in as')
    print(f"{client.user.name}({client.user.id})")
    print('------------------------------------------------------------')


@slash.slash(name="covid", guild_ids=guild_ids, description='COVID-19')
async def _covid(ctx):
    await update_covid_new_cases_count()
    await ctx.send(f"신규 확진자 {latest_covid_data['new_cases_count']}명 [{latest_covid_data['date']} 0시 기준]")


client.run(os.getenv('TOKEN'))
