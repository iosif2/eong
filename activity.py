import nextcord
from nextcord.application_command import ClientCog, slash_command, SlashOption
from nextcord.ui import View, Button
from config import Config

class ActivityCog(ClientCog):
    def __init__(self, client: nextcord.Client):
        self.client = client
    
    @slash_command(name='activity', description='Activity Invites', guild_ids=Config.guild_ids)
    async def activities(self, interaction: nextcord.Interaction, channel: 
        nextcord.abc.GuildChannel = SlashOption(channel_types=[nextcord.ChannelType.voice]), 
        activity: str = SlashOption(choices={
            'Watch Together': '880218394199220334'
            })):
        invite = await channel.create_invite(target_type=nextcord.InviteTarget.embedded_application, target_application_id=activity)
        view = View()
        button = Button(label=f'{invite.target_application.name} on {channel.name}', url=invite.url)
        view.add_item(button)
        await interaction.send(view=view)