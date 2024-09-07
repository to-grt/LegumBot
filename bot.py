import discord
from discord.ext import commands

from TOKEN import PRIVATE_TOKEN

# Define intents (this specifies which events the bot can receive)
intents = discord.Intents.default()
intents.message_content = True  # Allows the bot to read message content

# Define the bot prefix, e.g., '!'
bot = commands.Bot(command_prefix='/', intents=intents)

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user.name}')

@bot.command()
async def ping(ctx):
    await ctx.send('Pong!')

# Run the bot
bot.run(PRIVATE_TOKEN)
