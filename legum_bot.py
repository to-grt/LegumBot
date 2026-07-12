import logging
import os
import time
import random
import discord

from discord.ext import commands
from vocabulary import GREETINGS, TRIGGERS_BOT_NAME, MESSAGES_ANTOINE, MESSAGES_MUTED, MESSAGES_TYPING, MESSAGES_GOODBYE
from deals_cog import DealsCog

import TOKEN

PRIVATE_TOKEN = TOKEN.PRIVATE_TOKEN
# Optionnels : le bot démarre même si TOKEN.py ne définit que le token
ALLOWED_USERS = getattr(TOKEN, "ALLOWED_USERS", [])
ANTOINE_ID = getattr(TOKEN, "ANTOINE_ID", None)
YOANN_ID = getattr(TOKEN, "YOANN_ID", None)
DEALS_DB_PATH = getattr(TOKEN, "DEALS_DB_PATH", None)


def _as_id_list(plural_name, singular_name):
    """Accepte la liste (nouveau format) ou l'ID seul (ancien format)."""
    ids = getattr(TOKEN, plural_name, None)
    if not ids:  # absente OU vide : repli sur l'ancien champ au singulier
        single = getattr(TOKEN, singular_name, None)
        ids = [single] if single else []
    return [int(i) for i in ids]


DEAL_DM_USER_IDS = _as_id_list("DEAL_DM_USER_IDS", "DEAL_DM_USER_ID")
DEAL_CHANNEL_IDS = _as_id_list("DEAL_CHANNEL_IDS", "DEAL_CHANNEL_ID")


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
    async def restart(self, ctx):
        if ctx.author.id in ALLOWED_USERS:
            await ctx.send("Redémarrage du bot :)")
            await self.bot.close()
        else:
            await ctx.send("Tu pensais vraiment pouvoir m'arrêter ?")

    @commands.Cog.listener()
    async def on_typing(self, channel, user, when):
        if random.random() < 0.05:
            random_message = random.choice(MESSAGES_TYPING) + f" {user.mention}"
            await channel.send(random_message)

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        if before.self_mute == False and after.self_mute == True and random.random() < 0.05:
            if member.id != YOANN_ID:
                guild = member.guild
                general_channel = discord.utils.get(guild.text_channels, name="general")
                if general_channel:
                    random_message = random.choice(MESSAGES_MUTED) + f" {member.mention}"
                    await general_channel.send(random_message)
        elif after.channel is None and 0 <= time.localtime().tm_hour <= 8 and random.random() < 0.05:
            guild = member.guild
            general_channel = discord.utils.get(guild.text_channels, name="general")
            if general_channel:
                random_message = random.choice(MESSAGES_GOODBYE) + f" {member.mention}"
                await general_channel.send(random_message)

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
        elif message.attachments and random.random() < 0.05:
            for attachment in message.attachments:
                if any(attachment.filename.lower().endswith(ext) for ext in ['jpg', 'jpeg', 'png', 'gif']):
                    path = "assets/database_pictures"
                    if os.path.isdir(path) and os.listdir(path):
                        random_image_path = os.path.join(path, random.choice(os.listdir(path)))
                        await message.channel.send(file=discord.File(random_image_path))
        elif message.author.id == ANTOINE_ID and random.random() < 0.20:
            await message.channel.send(random.choice(MESSAGES_ANTOINE))
        elif any(trigger in message.content for trigger in TRIGGERS_BOT_NAME) or self.bot.user in message.mentions:
            greeting = f"Tu parles de moi {message.author.mention}? {random.choice(GREETINGS)} {message.author.name} :)"
            await message.channel.send(greeting)


class LegumBot(commands.Bot):
    def __init__(self, **options):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix='!', intents=intents, **options)

    async def setup_hook(self):
        await self.add_cog(GeneralCommands(self))
        await self.add_cog(
            DealsCog(
                self,
                db_path=DEALS_DB_PATH,
                dm_user_ids=DEAL_DM_USER_IDS,
                channel_ids=DEAL_CHANNEL_IDS,
            )
        )

    async def on_ready(self):
        print(f"Bot connected as {self.user}")


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    legum_bot = LegumBot()
    legum_bot.run(PRIVATE_TOKEN)
