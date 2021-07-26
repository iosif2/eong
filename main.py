#!venv/bin/python
import requests
import tts
import discord
import asyncio
import json
import datetime
import os
from dotenv import load_dotenv

load_dotenv()

client = discord.Client()
voiceClient = None
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


@client.event
async def on_message(message):
    global voiceClient, vol
    date_time = datetime.datetime.now().strftime("%m/%d/%Y, %H:%M:%S")
    channel = message.channel
    content = str(message.content)
    author = message.author

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
        if voiceClient is None:
            if author.voice:
                voiceClient = await author.voice.channel.connect()
            else:
                await channel.send('연결먼저 ㄱ', delete_after=5);
        while voiceClient.is_playing():
            await asyncio.sleep(0.1)
        if source is not None:
            voiceClient.play(discord.PCMVolumeTransformer(original=discord.FFmpegPCMAudio(source), volume=vol))
        while voiceClient.is_playing():
            await asyncio.sleep(0.1)
        for i in range(300):
            await asyncio.sleep(1)
            if voiceClient.is_playing():
                break
            if i == 299:
                await voiceClient.disconnect()
                voiceClient = None

    if content.startswith('vol'):
        arg = content[3:].replace(' ', '')
        if arg.__len__() > 0 and arg.isdigit():
            if 0 < int(arg) <= 100:
                vol = int(arg) / 100
        embed = discord.Embed(title="**Volume**",
                              description=f'{int(vol * 100)}%', color=0xff2f00)
        await channel.send(embed=embed, delete_after=5)

    if content.startswith('disconnect'):
        if voiceClient:
            await voiceClient.disconnect()
            voiceClient = None
    return


@client.event
async def on_ready():
    global voiceClient
    print('\n\n\n\nLogged in as')
    print(f"{client.user.name}({client.user.id})")
    print('------------------------------------------------------------')


client.run(os.getenv('TOKEN'))
