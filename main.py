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

def is_me(m):
    return m.author == client.user


def is_privileged(u):
    return u in guild.get_role(694430139395735642).members

@client.event
async def on_message(message):
    now = datetime.now()
    date_time = now.strftime("%m/%d/%Y, %H:%M:%S")
    global tch, tch_id, vch, vch_id, guild, vc, vol, goingtodiscon
    channel = message.channel
    content = str(message.content)
    audpname = message.author.display_name
    auid = message.author.id
    author = message.author

    if is_me(message):
        return

    print(
        f"[{date_time}]{channel}({channel.id}) |  {audpname}({auid}): {content}")
    if '^오^' in content:
        goingtodiscon = False
        if vc == None:
            vc = await vch.connect()
        if vc.is_playing():
            return
        vc.play(discord.PCMVolumeTransformer(original=discord.FFmpegPCMAudio('teemo.mp3'), volume=0.15))
        while vc.is_playing():
            await asyncio.sleep(1)
        goingtodiscon = True
        for i in range(120):
            await asyncio.sleep(1)
            if not goingtodiscon:
                break
            if i == 119:
                await vc.disconnect()
                vc = None
    if content.startswith(': '):
        txt = content[2:]
        symbol: dict
        with open("symbol.json", encoding="utf-8") as f:
            symbol = json.load(f)
        for key, item in symbol.items():
            if key in txt:
                txt = txt.replace(key, item)
        goingtodiscon = False
        if vc == None:
            vc = await vch.connect()
        if vc.is_playing():
            return
        vc.play(tts.tts(txt, vol))
        while vc.is_playing():
            await asyncio.sleep(1)
        goingtodiscon = True
        for i in range(120):
            await asyncio.sleep(1)
            if not goingtodiscon:
                break
            if i == 119:
                await vc.disconnect()
                vc = None

    if content.startswith('🔈'):
        if not is_privileged(author):
            return
        arg = content[1:].replace(' ', '')
        if arg.__len__() > 0 and arg.isdigit():
            if 0 < int(arg) <= 100:
                vol = int(arg) / 100
        embed = discord.Embed(title="**Volume**", description=f'{int(vol * 100)}%', color=0xff2f00)
        sent = await channel.send(embed=embed)
        await asyncio.sleep(5)
        await sent.delete()

    return


@client.event
async def on_ready():
    global guild, guild_id, tch, tch_id, vch, vch_id, tch_list, vch_list, vc
    guild = client.get_guild(guild_id)
    for ch in client.get_all_channels():
        if ch.type is discord.ChannelType.text:
            tch_list.append(ch)
        elif ch.type is discord.ChannelType.voice:
            vch_list.append(ch)
        else:
            continue
    tch = guild.get_channel(tch_id)
    vch = guild.get_channel(vch_id)
    print('\n\n\n\nLogged in as')
    print(f"{client.user.name}({client.user.id})")
    print('------------------------------------------------------------')
    print('Server Info')
    print(f"{guild.name}({guild.id})")
    print(f"TextChannel List : ")
    for ch in tch_list:
        print(f"{ch.name}({ch.id})")
    print(f"VoiceChannel List : ")
    for ch in vch_list:
        print(f"{ch.name}({ch.id})")
    print('------------------------------------------------------------')
    await tch.purge(limit=200, check=is_me)

client.run(os.getenv('TOKEN'))
