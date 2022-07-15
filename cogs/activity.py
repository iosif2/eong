import nextcord
from nextcord.ext import commands
from nextcord.ui import Button, View


class ActivityCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.client = bot

    @nextcord.slash_command(name="activity", description="Activity Invites")
    async def activities(
        self,
        interaction: nextcord.Interaction,
        channel: nextcord.abc.GuildChannel = nextcord.SlashOption(channel_types=[nextcord.ChannelType.voice]),
        activity: str = nextcord.SlashOption(
            choices={
                "유튜브": "880218394199220334",
                "Sketch Heads": "902271654783242291",
                "Awkword": "879863881349087252",
                "8[Boost Level >= 1]": "832025144389533716",
                "Letter League[Boost Level >= 1]": "879863753519292467",
                "포커[Boost Level >= 1]": "755827207812677713",
            }
        ),
    ):
        invite = await channel.create_invite(
            target_type=nextcord.InviteTarget.embedded_application,
            target_application_id=activity,
        )
        view = View()
        button = Button(label=f"{invite.target_application.name} on {channel.name}", url=invite.url)
        view.add_item(button)
        await interaction.send(view=view)


def setup(bot: commands.Bot):
    bot.add_cog(ActivityCog(bot))
