import random
import discord

from discord.ext import commands
from vocabulary import GREETINGS
from TOKEN import ALLOWED_USERS, PRIVATE_TOKEN


class GeneralCommands(commands.Cog):



    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def hello(self, ctx):
        author = ctx.author
        await ctx.send(f"{random.choice(GREETINGS)} {author.mention}!")

    @commands.command()
    async def ping(self, ctx):
        await ctx.send("Pong!")

    @commands.command()
    async def restart(self, ctx):
        if ctx.author.id in ALLOWED_USERS:
            await ctx.send("Rebooting the bot :)")
            await self.bot.close()
        else:
            await ctx.send("Someone thinks they can stop me...")


class LegumBot(commands.Bot):

    def __init__(self, **options):
        intents = discord.Intents.default()
        intents.message_content = True

        super().__init__(command_prefix='!', intents=intents, **options)

    async def setup_hook(self):
        await self.add_cog(GeneralCommands(self))

    async def on_ready(self):
        print(f"Bot connected as {self.user}")


if __name__ == '__main__':
    legum_bot = LegumBot()
    legum_bot.run(PRIVATE_TOKEN)
