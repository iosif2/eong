import datetime
import json

import nextcord
import requests
import xmltodict
from nextcord.ext import commands

from config import Config


class Covid:
    def __init__(self, serviceKey):
        self.url = "http://openapi.data.go.kr/openapi/service/rest/Covid19/getCovid19InfStateJson"
        self.serviceKey = serviceKey
        self.latest_covid_data = {}

    async def fetchData(self):
        today = datetime.datetime.today()
        day_before_yesterday = datetime.datetime.today() - datetime.timedelta(2)
        res = requests.get(
            "http://openapi.data.go.kr/openapi/service/rest/Covid19/getCovid19InfStateJson",
            params={
                "serviceKey": self.serviceKey,
                "startCreateDt": day_before_yesterday.strftime("%Y%m%d"),
                "endCreateDt": today.strftime("%Y%m%d"),
            },
        )
        data = json.loads(json.dumps(xmltodict.parse(res.content))).get("response").get("body").get("items").get("item")
        self.latest_covid_data["date"] = data[0].get("createDt")[0:10].replace("-", "")
        self.latest_covid_data["new_cases_count"] = int(data[0].get("decideCnt")) - int(data[1].get("decideCnt"))

    async def getData(self):
        today = datetime.datetime.today()
        if self.latest_covid_data.get("date") != today.strftime("%Y%m%d"):
            await self.fetchData()
            return self.latest_covid_data


class CovidCog(commands.Cog):
    def __init__(self, bot):
        self.bot: commands.Bot = bot
        self.covid = Covid(serviceKey=Config.serviceKey)

    def is_me(self, m):
        return m.author == self.bot.user

    @nextcord.slash_command("covid", description="covid19")
    async def _covid(self, interaction: nextcord.Interaction):
        latest_covid_data = await self.covid.getData()
        embed = nextcord.Embed(
            title="코로나 신규 확진자",
            colour=nextcord.Color.yellow(),
            timestamp=datetime.datetime.strptime(latest_covid_data["date"], "%Y%m%d"),
        )
        embed.add_field(name=f'{latest_covid_data["new_cases_count"]:,} 명', value="\u200B")
        await interaction.send(embeds=[embed])


def setup(bot: commands.Bot):
    pass
    # bot.add_cog(CovidCog(bot=bot)) # Uncomment to enable the cog
