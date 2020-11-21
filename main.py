import asyncio
import json
from datetime import datetime
import os
from dotenv import load_dotenv
load_dotenv()

import discord
import tts

# 추가 파일

with open('config.json') as f:
    config = json.load(f)
    guild_id = config['guild_id']
    tch_id = config['tch_id']
    vch_id = config['vch_id']

client = discord.Client()
guild: discord.Guild
tch = None
vch = None
vc = None
tch_list = []
vch_list = []
goingtodiscon = False
vol = 0.2
prefix = ';'
mp3_files = {
    '^오^': 'teemo.mp3',
    '비둘기': 'pigeon.mp3',
    '네이스': 'nayce.mp3',
    '기모링': 'gimoring.mp3',
    '빡빡이': 'bald.mp3'
}

def is_me(m):
    return m.author == client.user


def is_privileged(u):
    return u in guild.get_role(694430139395735642).members

def is_registerd(t):
    for key in mp3_files.keys():
        if key in t:
            return key
    return False

@client.event
async def on_message(message):  
    now = datetime.now()
    date_time = now.strftime("%m/%d/%Y, %H:%M:%S")
    global tch, tch_id, vch, vch_id, guild, vc, vol, goingtodiscon, prefix
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
        vc.play(discord.PCMVolumeTransformer(original=discord.FFmpegPCMAudio(mp3_files[txt]), volume=0.2))
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
        if content.startswith('t'):
            txt = content[1:]
            vc.play(tts.tts(txt, vol, 'Takumi'))
        elif content.startswith('m'):
            txt = content[1:]
            vc.play(tts.tts(txt, vol, 'Matthew'))
        elif content.startswith('f'):
            txt = content[1:]
            vc.play(tts.tts(txt, vol, 'Filiz'))
        elif content.startswith('s'):
            txt = content[1:]
            with open("symbol.json", encoding="utf-8") as f:
                symbol = json.load(f)
                for key, item in symbol.items():
                    if key in txt:
                        txt = txt.replace(key, item)
                vc.play(tts.tts(txt, vol, 'Seoyeon'))
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

    if content.startswith('vol'):
        if not is_privileged(author):
            return
        arg = content[3:].replace(' ', '')
        if arg.__len__() > 0 and arg.isdigit():
            if 0 < int(arg) <= 100:
                vol = int(arg) / 100
        embed = discord.Embed(title="**Volume**", description=f'{int(vol * 100)}%', color=0xff2f00)
        sent = await channel.send(embed=embed)
        await asyncio.sleep(5)
        await sent.delete()

    if content.startswith('pre'):
        if not is_privileged(author):
            return
        prefix = content[3:].replace(' ', '')

    if content.startswith('disconnect'):
        if not is_privileged(author):
            return
        if vc:
            await vc.disconnect()
            vc = None
            goingtodiscon = False

    return

@client.event
async def on_ready():
    global guild, guild_id, tch, tch_id, vch, vch_id, tch_list, vch_list, vc
    guild = client.get_guild(guild_id)
    tch = guild.get_channel(tch_id)
    vch = guild.get_channel(vch_id)
    print('\n\n\n\nLogged in as')
    print(f"{client.user.name}({client.user.id})")
    print('------------------------------------------------------------')
    print('Server Info')
    print(f"{guild.name}({guild.id})")
    print('------------------------------------------------------------')
    await tch.purge(limit=200, check=is_me)

client.run(os.getenv('TOKEN'))
