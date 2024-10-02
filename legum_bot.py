import time
import random
import discord

from discord.ext import commands
from vocabulary import GREETINGS, TRIGGERS_BOT_NAME, MESSAGES_ANTOINE
from TOKEN import ALLOWED_USERS, PRIVATE_TOKEN, ANTOINE_ID


class GeneralCommands(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.last_interaction = {}

    @commands.command()
    async def hello(self, ctx):
        author = ctx.author
        await ctx.send(f"{random.choice(GREETINGS)} {author.mention}!")

    @commands.command()
    async def ping(self, ctx):
        await ctx.send("Pong!")

    @commands.command()
    async def pong(self, ctx):
        await ctx.send("Pang!")

    @commands.command()
    async def pang(self, ctx):
        await ctx.send("Pung?")

    @commands.command()
    async def pung(self, ctx):
        await ctx.send("Peng!")

    @commands.command()
    async def peng(self, ctx):
        await ctx.send("Pyng!")

    @commands.command()
    async def pyng(self, ctx):
        await ctx.send("Ping :)")

    @commands.command()
    async def restart(self, ctx):
        if ctx.author.id in ALLOWED_USERS:
            await ctx.send("Redémarrage du bot :)")
            await self.bot.close()
        else:
            await ctx.send("Tu pensais vraiment pouvoir m'arrêter ?")

    @commands.Cog.listener()
    async def on_command(self, ctx):
        current_time = time.time()
        author_id = ctx.author.id

        if ((author_id not in self.last_interaction) or (current_time - self.last_interaction[author_id] > 600)) and ctx.message.content != "!hello":
            greeting = f"Ça faisait longtemps {ctx.author.mention}, {random.choice(GREETINGS)}!"
            await ctx.send(greeting)

        self.last_interaction[author_id] = current_time

    @commands.Cog.listener()
    async def on_message(self, message):

        if message.author.bot:
            return

        elif message.author.id == ANTOINE_ID and random.random() < 0.20:
            await message.channel.send(random.choice(MESSAGES_ANTOINE))

        elif any(trigger in message.content for trigger in TRIGGERS_BOT_NAME) or self.bot.user in message.mentions:
            greeting = f"Tu parles de moi {message.author.mention}? {random.choice(GREETINGS)} {message.author} :)"
            await message.channel.send(greeting)


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
