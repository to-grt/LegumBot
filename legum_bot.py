import asyncio
import logging
import os
import re
import time
import random
import discord

from discord.ext import commands
from vocabulary import GREETINGS, TRIGGERS_BOT_NAME, MESSAGES_ANTOINE, MESSAGES_MUTED, MESSAGES_TYPING, MESSAGES_GOODBYE
from deals_cog import DealsCog
from llm import LlmClient

import TOKEN

log = logging.getLogger("legum_bot")

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
# Routage par recherche : {nom de watch pc-deals-bot: [IDs à prévenir en MP]}.
# Les watches absentes suivent DEAL_DM_USER_IDS / DEAL_CHANNEL_IDS.
DEAL_ROUTES = getattr(TOKEN, "DEAL_ROUTES", {})
# Commande !scan : argv à lancer pour un passage immédiat de pc-deals-bot
# (liste), et répertoire de travail. Vide => commande !scan désactivée.
DEALS_SCAN_CMD = getattr(TOKEN, "DEALS_SCAN_CMD", [])
DEALS_SCAN_CWD = getattr(TOKEN, "DEALS_SCAN_CWD", None)

# --- Génération locale des réponses (llm.py + llama-server) ---------------
LLM_ENABLED = getattr(TOKEN, "LLM_ENABLED", True)
LLM_URL = getattr(TOKEN, "LLM_URL", "http://127.0.0.1:8080/v1/chat/completions")
LLM_TIMEOUT = getattr(TOKEN, "LLM_TIMEOUT", 30)
LLM_BUCKET_CAPACITY = getattr(TOKEN, "LLM_BUCKET_CAPACITY", 40)
LLM_REFILL_PER_HOUR = getattr(TOKEN, "LLM_REFILL_PER_HOUR", 120)
# Prénoms que le modèle ne doit jamais citer : s'il en produit un malgré la
# consigne, on retombe sur vocabulary.py.
LLM_KNOWN_NAMES = getattr(
    TOKEN, "LLM_KNOWN_NAMES",
    ["theo", "antoine", "yoann", "marie", "victor", "nicolas", "lucas"],
)

# --- Probabilités de déclenchement (ajustables sans toucher au code) ------
P_TYPING = getattr(TOKEN, "P_TYPING", 0.20)
P_MUTED = getattr(TOKEN, "P_MUTED", 0.20)
P_GOODBYE = getattr(TOKEN, "P_GOODBYE", 0.20)
P_IMAGE = getattr(TOKEN, "P_IMAGE", 0.20)
P_ANTOINE = getattr(TOKEN, "P_ANTOINE", 0.50)
P_MESSAGE = getattr(TOKEN, "P_MESSAGE", 0.20)

# Salon où sont annoncés les événements vocaux. Repli sur le premier salon
# écrivable si ce nom n'existe pas sur le serveur.
VOICE_CHANNEL_NAME = getattr(TOKEN, "VOICE_CHANNEL_NAME", "general")

IMAGE_EXTS = ("jpg", "jpeg", "png", "gif", "webp")
PICTURES_DIR = "assets/database_pictures"
MAX_CONTEXT_CHARS = 200

# Frontières de mot : « j'ai mis mes bottes » ne doit pas réveiller le bot.
_BOT_NAME_RE = re.compile(
    r"\b(" + "|".join(
        sorted({re.escape(t.lower()) for t in TRIGGERS_BOT_NAME}, key=len, reverse=True)
    ) + r")\b",
    re.IGNORECASE,
)

# Situations envoyées au modèle. Aucune ne contient de prénom : le modèle
# écrit une phrase anonyme, le bot appose lui-même la mention.
SIT_HELLO = "Salue chaleureusement quelqu'un qui vient de dire bonjour."
SIT_TYPING = "Quelqu'un tape un message depuis un moment. Fais une remarque taquine et bienveillante."
SIT_MUTED = "Quelqu'un vient de couper son micro en vocal. Charrie-le gentiment."
SIT_GOODBYE = "Il fait nuit et quelqu'un quitte le salon vocal. Dis-lui au revoir avec humour."
SIT_RETOUR = "Quelqu'un revient apres une longue absence. Accueille-le chaleureusement."
SIT_IMAGE = "Quelqu'un vient de poster une image dans le salon. Reagis avec enthousiasme."
SIT_ANTOINE = "Quelqu'un vient d'ecrire un message. Envoie-lui un compliment sincere et chaleureux."
SIT_CITE = 'Quelqu\'un vient de citer ton nom en disant : "{msg}". Reponds-lui avec complicite.'
SIT_MESSAGE = 'Quelqu\'un vient d\'ecrire ce message dans le salon : "{msg}". Rebondis dessus avec complicite.'


class GeneralCommands(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.last_interaction = {}
        self.llm = LlmClient(
            url=LLM_URL,
            enabled=LLM_ENABLED,
            timeout=LLM_TIMEOUT,
            known_names=LLM_KNOWN_NAMES,
            bucket_capacity=LLM_BUCKET_CAPACITY,
            refill_per_hour=LLM_REFILL_PER_HOUR,
        )

    def cog_unload(self):
        asyncio.create_task(self.llm.close())

    # ------------------------------------------------------------- outils

    async def _say(self, channel, situation, fallback, mention=None):
        """Génère une phrase et l'envoie, avec l'indicateur « écrit… »."""
        async with channel.typing():
            texte = await self.llm.phrase(situation, fallback)
        if mention:
            texte = f"{texte} {mention}"
        await channel.send(texte)

    def _voice_text_channel(self, guild):
        """Salon des annonces vocales, avec repli si le nom configuré manque."""
        channel = discord.utils.get(guild.text_channels, name=VOICE_CHANNEL_NAME)
        if channel is None:
            channel = next(
                (c for c in guild.text_channels
                 if c.permissions_for(guild.me).send_messages),
                None,
            )
            if channel is not None:
                log.warning(
                    "Salon '%s' introuvable sur %s : repli sur #%s",
                    VOICE_CHANNEL_NAME, guild.name, channel.name,
                )
        return channel

    @staticmethod
    def _context(message):
        return message.content.strip()[:MAX_CONTEXT_CHARS].replace('"', "'")

    # ----------------------------------------------------------- commandes

    @commands.command()
    async def hello(self, ctx):
        """Te salue chaleureusement."""
        await self._say(ctx.channel, SIT_HELLO, GREETINGS, ctx.author.mention)

    @commands.command()
    async def ping(self, ctx):
        """Vérifie que le bot répond encore."""
        await ctx.send("Pong!")

    @commands.command()
    async def restart(self, ctx):
        """[Admin] Redémarre le bot."""
        if ctx.author.id in ALLOWED_USERS:
            await ctx.send("Redémarrage du bot :)")
            await self.bot.close()
        else:
            await ctx.send("Tu pensais vraiment pouvoir m'arrêter ?")

    @commands.command(name="llm")
    async def llm_cmd(self, ctx, action: str = "status"):
        """[Admin] Génération locale : !llm on | off | status"""
        if ALLOWED_USERS and ctx.author.id not in ALLOWED_USERS:
            await ctx.send("Seuls les patrons touchent à mes neurones :)")
            return

        action = action.lower()
        if action == "on":
            self.llm.enabled = True
            await ctx.send("🧠 Génération locale activée.")
        elif action == "off":
            self.llm.enabled = False
            await ctx.send("💤 Génération locale coupée, retour aux phrases toutes faites.")
        else:
            s = self.llm.status()
            await ctx.send(
                f"🧠 **LegumBot / génération locale**\n"
                f"• état : {'active' if s['actif'] else 'coupée'}"
                f"{' (en pause après erreurs)' if s['en_pause'] else ''}\n"
                f"• jetons : {s['jetons']}/{s['capacite']}\n"
                f"• générées : {s['generees']} · replis : {s['replis']}\n"
                f"• échecs consécutifs : {s['echecs_consecutifs']}\n"
                f"• dernière erreur : {s['derniere_erreur'] or 'aucune'}"
            )

    @llm_cmd.error
    async def llm_cmd_error(self, ctx, error):
        if isinstance(error, commands.BadArgument):
            await ctx.send("Usage : `!llm on`, `!llm off` ou `!llm status`")
        else:
            raise error

    # ---------------------------------------------------------- écouteurs

    @commands.Cog.listener()
    async def on_typing(self, channel, user, when):
        if user.bot:
            return
        if random.random() < P_TYPING:
            await self._say(channel, SIT_TYPING, MESSAGES_TYPING, user.mention)

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        if member.bot:
            return
        # before.channel is not None : sinon rejoindre un vocal déjà muté
        # déclencherait le message « tu viens de couper ton micro ».
        vient_de_couper = (
            before.channel is not None
            and not before.self_mute
            and after.self_mute
        )
        if vient_de_couper and random.random() < P_MUTED:
            channel = self._voice_text_channel(member.guild)
            if channel:
                await self._say(channel, SIT_MUTED, MESSAGES_MUTED, member.mention)
        elif (
            after.channel is None
            and 0 <= time.localtime().tm_hour <= 8
            and random.random() < P_GOODBYE
        ):
            channel = self._voice_text_channel(member.guild)
            if channel:
                await self._say(channel, SIT_GOODBYE, MESSAGES_GOODBYE, member.mention)

    @commands.Cog.listener()
    async def on_command(self, ctx):
        current_time = time.time()
        author_id = ctx.author.id
        est_hello = ctx.command is not None and ctx.command.name == "hello"
        if not est_hello and (
            author_id not in self.last_interaction
            or current_time - self.last_interaction[author_id] > 600
        ):
            await self._say(ctx.channel, SIT_RETOUR, GREETINGS, ctx.author.mention)
        self.last_interaction[author_id] = current_time

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return
        # Les commandes (!hello, !ping, !scan…) sont déjà traitées ailleurs :
        # sans ce garde, elles déclencheraient en plus une réponse générique.
        if message.content.startswith(self.bot.command_prefix):
            return

        cite = bool(_BOT_NAME_RE.search(message.content)) or self.bot.user in message.mentions

        if cite:
            await self._say(
                message.channel,
                SIT_CITE.format(msg=self._context(message)),
                GREETINGS,
                message.author.mention,
            )
        elif message.attachments and random.random() < P_IMAGE:
            await self._on_image(message)
        elif (
            ANTOINE_ID
            and message.author.id == ANTOINE_ID
            and random.random() < P_ANTOINE
        ):
            await self._say(message.channel, SIT_ANTOINE, MESSAGES_ANTOINE, message.author.mention)
        elif random.random() < P_MESSAGE:
            await self._say(
                message.channel,
                SIT_MESSAGE.format(msg=self._context(message)),
                MESSAGES_TYPING,
                message.author.mention,
            )

    async def _on_image(self, message):
        """Réagit à une pièce jointe : image du dossier si présent, puis phrase."""
        est_image = any(
            attachment.filename.lower().endswith("." + ext)
            for attachment in message.attachments
            for ext in IMAGE_EXTS
        )
        if est_image and os.path.isdir(PICTURES_DIR) and os.listdir(PICTURES_DIR):
            choix = os.path.join(PICTURES_DIR, random.choice(os.listdir(PICTURES_DIR)))
            await message.channel.send(file=discord.File(choix))
        await self._say(message.channel, SIT_IMAGE, GREETINGS, message.author.mention)


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
                routes=DEAL_ROUTES,
                allowed_user_ids=ALLOWED_USERS,
                scan_cmd=DEALS_SCAN_CMD,
                scan_cwd=DEALS_SCAN_CWD,
            )
        )

    async def on_ready(self):
        print(f"Bot connected as {self.user}")
        # Le salon des annonces vocales est configurable : on dit tout de suite
        # lequel sera réellement utilisé, serveur par serveur.
        for guild in self.guilds:
            cible = discord.utils.get(guild.text_channels, name=VOICE_CHANNEL_NAME)
            if cible is not None:
                log.info("[%s] annonces vocales -> #%s", guild.name, cible.name)
            else:
                repli = next(
                    (c for c in guild.text_channels
                     if c.permissions_for(guild.me).send_messages),
                    None,
                )
                log.warning(
                    "[%s] salon '%s' introuvable -> repli sur %s",
                    guild.name, VOICE_CHANNEL_NAME,
                    f"#{repli.name}" if repli else "AUCUN salon ecrivable",
                )


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    legum_bot = LegumBot()
    legum_bot.run(PRIVATE_TOKEN)
