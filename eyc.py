import nextcord
from nextcord.ui import View
from nextcord.application_command import ClientCog, slash_command
import json
import os

guild_ids = json.loads(os.getenv('guild_ids'))


class EyesYChick:
    def __init__(self):
        self.count_eyes = 0;
        self.count_chick = 0;
    
    def add_eyes(self):
        self.count_eyes += 1;
        
    def add_chick(self):
        self.count_chick += 1;

class EYC_View(View):
    def __init__(self, client: nextcord.Client):
        super().__init__(timeout=0)
        self.value = None
        self.client: nextcord.Client = client
        
    @nextcord.ui.button(style=nextcord.ButtonStyle.blurple, emoji='👀')
    async def yes(self, button : nextcord.ui.Button, interaction : nextcord.Interaction):
        self.client.eyc.add_eyes()
        await interaction.send(content=f'👀 {interaction.user.mention}', delete_after=0)

    @nextcord.ui.button(style=nextcord.ButtonStyle.green, emoji='🐥')
    async def no(self, button : nextcord.ui.Button, interaction : nextcord.Interaction):
        self.client.eyc.add_chick()
        await interaction.send(content=f'👀 {interaction.user.mention}', delete_after=0)

class EYCCog(ClientCog):
    def __init__(self, client):
        self.client: nextcord.Client = client
    
    def is_me(self, m):
        return m.author == self.client.user
    
    @slash_command("button", guild_ids=guild_ids, description='buttons')
    async def _button(self, interaction: nextcord.Interaction):
        view = EYC_View(self.client)
        await interaction.send(view=view)
        await view.wait()
