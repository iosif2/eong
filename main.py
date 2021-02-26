import requests
from requests.api import get
import tts
import discord
import asyncio
import json
import datetime
import os
from dotenv import load_dotenv
load_dotenv()


# 추가 파일

guild_id = int(os.getenv('GUILD_ID'))
vch_id = int(os.getenv('VCH_ID'))

client = discord.Client()
guild: discord.Guild
vch = None
vc = None
goingtodiscon = False
vol = 0.4
prefix = ';'
mp3_files = {
    '^오^': 'teemo.mp3',
    '비둘기': 'pigeon.mp3',
    '네이스': 'nayce.mp3',
    '기모링': 'gimoring.mp3',
    '빡빡이': 'bald.mp3',
    '무야호': 'muyaho.mp3',
    '시옹포포': 'sop.mp3',
    'muyaho': 'myh.mp3',
    'ㅇㅈㅇㅈㅎㄴ': 'dizzy.mp3',
    '🖕': 'fy.mp3'
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


def is_registerd(t):
    for key in mp3_files.keys():
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
                    'url': 'https://github.com/losifz/GGTTS',
                    'color': 5439232,
                    'fields': fields,
                    'author': {
                        'name': 'losif',
                        'url': 'http://losifz.com',
                        'icon_url': 'https://avatars1.githubusercontent.com/u/54474221?s=460&u=4528d15da4babf939a10038f17427b44483dbc0f&v=4'
                    },
                    'footer': {
                        'text': 'losif',
                        'icon_url': 'https://avatars1.githubusercontent.com/u/54474221?s=460&u=4528d15da4babf939a10038f17427b44483dbc0f&v=4'
                    },
                    'timestamp': datetime.datetime.now(datetime.timezone.utc).isoformat()
                }
            ]

        }),
        headers={'Content-Type': 'application/json; charset=utf-8'}
    )


@client.event
async def on_message(message):
    now = datetime.datetime.now()
    date_time = now.strftime("%m/%d/%Y, %H:%M:%S")
    global vch, vch_id, guild, vc, vol, goingtodiscon, prefix
    channel = message.channel
    content = str(message.content)
    audpname = message.author.display_name
    auid = message.author.id
    author = message.author

    if is_me(message):
        return

    print(
        f"[{date_time}]{channel}({channel.id}) |  {audpname}({auid}): {content}")
    txt = is_registerd(content)
    if txt:
        goingtodiscon = False
        if vc == None:
            if author.voice:
                vc = await author.voice.channel.connect()
            else:
                vc = await vch.connect()
        if vc.is_playing():
            return
        vc.play(discord.PCMVolumeTransformer(
            original=discord.FFmpegPCMAudio(mp3_files[txt]), volume=0.2))
        while vc.is_playing():
            await asyncio.sleep(1)
        goingtodiscon = True
        for i in range(300):
            await asyncio.sleep(1)
            if not goingtodiscon:
                break
            if i == 299:
                await vc.disconnect()
                vc = None
                goingtodiscon = False

    if content.startswith(prefix):
        content = content[1:]
        goingtodiscon = False
        if vc == None:
            if author.voice:
                vc = await author.voice.channel.connect()
            else:
                vc = await vch.connect()
        if vc.is_playing():
            return
        voice = ''
        txt = content[1:]
        if content.startswith('s'):
            with open("symbol.json", encoding="utf-8") as f:
                symbol = json.load(f)
                for key, item in symbol.items():
                    if key in txt:
                        txt = txt.replace(key, item)
        voice = get_voice(content[0])
        if voice:
            vc.play(tts.tts(txt, vol, voice))
        else:
            return

        await discord_webhook(author, voice, content[1:])
        while vc.is_playing():
            await asyncio.sleep(1)
        goingtodiscon = True
        for i in range(300):
            await asyncio.sleep(1)
            if not goingtodiscon:
                break
            if i == 299:
                await vc.disconnect()
                vc = None
                goingtodiscon = False

    if content.startswith('vol'):
        arg = content[3:].replace(' ', '')
        if arg.__len__() > 0 and arg.isdigit():
            if 0 < int(arg) <= 100:
                vol = int(arg) / 100
        embed = discord.Embed(title="**Volume**",
                              description=f'{int(vol * 100)}%', color=0xff2f00)
        sent = await channel.send(embed=embed)
        await asyncio.sleep(30)
        await sent.delete()

    if content.startswith('pre'):
        prefix = content[3:].replace(' ', '')

    if content.startswith('disconnect'):
        if vc:
            await vc.disconnect()
            vc = None
            goingtodiscon = False

    return


@client.event
async def on_ready():
    global guild, guild_id, vch, vch_id, vc
    guild = client.get_guild(guild_id)
    vch = guild.get_channel(vch_id)
    print('\n\n\n\nLogged in as')
    print(f"{client.user.name}({client.user.id})")
    print('------------------------------------------------------------')
    print('Server Info')
    print(f"{guild.name}({guild.id})")
    print('------------------------------------------------------------')

client.run(os.getenv('TOKEN'))
