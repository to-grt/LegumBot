import discord

from LegumBot import LegumBot
from TOKEN import PRIVATE_TOKEN

intents = discord.Intents.default()
intents.message_content = True

legum_bot = LegumBot(command_prefix='!', intents=intents)

legum_bot.run(PRIVATE_TOKEN)
