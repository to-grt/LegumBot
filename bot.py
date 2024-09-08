import os
import sys
import discord
from discord.ext import commands

from TOKEN import PRIVATE_TOKEN

# Define intents (this specifies which events the bot can receive)
intents = discord.Intents.default()
intents.message_content = True  # Allows the bot to read message content

# Define the bot prefix, e.g., '!'
bot = commands.Bot(command_prefix=';', intents=intents)

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user.name}')

@bot.command(name='ping')
async def ping(ctx):
    await ctx.send('Pong!')

@bot.command(name='stop')
async def stop(ctx):
    if ctx.author.id == bot.owner_id:
        await ctx.send("Stopping the bot...")
        await bot.close()
    else:
        await ctx.send('You do not have permission to stop the bot! :)')

# Run the bot
bot.run(PRIVATE_TOKEN)
