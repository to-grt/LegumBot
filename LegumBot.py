from TOKEN import ALLOWED_USERS
from discord.ext import commands


class LegumBot(commands.bot):

    AVAILABLE_LANGUAGE = ['french', 'english']

    def __init__(self, command_prefix, **options):
        super().__init__(self, command_prefix, **options)

        self.add_command(self.ping)
        self.add_command(self.stop)

        self.language = 'french'

    async def on_ready(self):
        print(f"Bot connected as {self.user}")

    @commands.command()
    async def ping(self, ctx):
        await self.send(ctx, "Pong!")

    @commands.command()
    async def stop(self, ctx):
        if ctx.author.id in ALLOWED_USERS:
            await ctx.send("Stopping the bot...")
            await self.close()
        else:
            await ctx.send("Someone thinks they can stop me...")