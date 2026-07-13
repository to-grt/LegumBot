"""Annonce sur Discord les deals détectés par pc-deals-bot.

Le bot pc-deals-bot (qui tourne sur la même machine) enregistre chaque deal
dans une base SQLite avec la colonne matched_watch renseignée quand le deal
correspond à une recherche. Ce cog interroge cette base toutes les minutes et
envoie les deals pas encore annoncés en MP et/ou dans un salon, puis les
marque comme annoncés dans une table dédiée (discord_announced) pour ne
jamais notifier deux fois.

Routage par recherche : "routes" associe un nom de watch (côté pc-deals-bot)
à une liste d'IDs d'utilisateurs à prévenir en MP. Les watches absentes de
routes suivent le comportement historique : MP à dm_user_ids et publication
dans channel_ids.
"""

import logging
import sqlite3
from pathlib import Path

import discord
from discord.ext import commands, tasks

log = logging.getLogger("legum_bot.deals")

CHECK_INTERVAL_SECONDS = 60


class DealsCog(commands.Cog):
    def __init__(self, bot, db_path, dm_user_ids=(), channel_ids=(), routes=None):
        self.bot = bot
        self.db_path = Path(db_path) if db_path else None
        self.dm_user_ids = list(dm_user_ids)
        self.channel_ids = list(channel_ids)
        self.routes = {
            name: [int(i) for i in ids] for name, ids in (routes or {}).items()
        }
        if self.db_path and (self.dm_user_ids or self.channel_ids or self.routes):
            self.check_deals.start()
        else:
            log.warning(
                "Annonce des deals désactivée : DEALS_DB_PATH et au moins un "
                "destinataire (DEAL_DM_USER_IDS / DEAL_CHANNEL_IDS / "
                "DEAL_ROUTES) doivent être renseignés"
            )

    def cog_unload(self):
        self.check_deals.cancel()

    # ------------------------------------------------------------- SQLite

    def _fetch_pending(self):
        """Deals matchés pas encore annoncés, du plus ancien au plus récent."""
        if not self.db_path.exists():
            return []
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS discord_announced ("
                "  deal_id TEXT PRIMARY KEY,"
                "  announced_at TEXT DEFAULT CURRENT_TIMESTAMP)"
            )
            conn.commit()
            return conn.execute(
                """
                SELECT d.id, d.title, d.url, d.price, d.temperature, d.matched_watch
                FROM deals d
                LEFT JOIN discord_announced a ON a.deal_id = d.id
                WHERE d.matched_watch IS NOT NULL AND a.deal_id IS NULL
                ORDER BY d.fetched_at
                """
            ).fetchall()
        finally:
            conn.close()

    def _mark_announced(self, deal_id):
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute(
                "INSERT OR IGNORE INTO discord_announced (deal_id) VALUES (?)",
                (deal_id,),
            )
            conn.commit()
        finally:
            conn.close()

    # ------------------------------------------------------------ Discord

    def _build_embed(self, title, url, price, temperature, watch_name):
        embed = discord.Embed(
            title=title[:256],
            url=url,
            description=f"🔎 Recherche : **{watch_name}**",
            color=discord.Color.orange(),
        )
        embed.add_field(
            name="Prix",
            value=f"{price:.2f} €" if price is not None else "non détecté",
        )
        if temperature is not None:
            embed.add_field(name="Température", value=f"{temperature:.0f}°")
        return embed

    async def _send_to_users(self, user_ids, embed):
        """MP l'embed à chaque utilisateur. Vrai si au moins un a reçu."""
        delivered = False
        for user_id in user_ids:
            try:
                user = self.bot.get_user(user_id) or await self.bot.fetch_user(user_id)
                await user.send(embed=embed)
                delivered = True
            except discord.DiscordException:
                log.exception("Échec du MP à l'utilisateur %s", user_id)
        return delivered

    async def _send_to_channels(self, channel_ids, embed):
        """Poste l'embed dans chaque salon. Vrai si au moins un a reçu."""
        delivered = False
        for channel_id in channel_ids:
            try:
                channel = self.bot.get_channel(
                    channel_id
                ) or await self.bot.fetch_channel(channel_id)
                await channel.send(embed=embed)
                delivered = True
            except discord.DiscordException:
                log.exception("Échec de l'envoi dans le salon %s", channel_id)
        return delivered

    async def _dispatch(self, embed, watch_name):
        """Route l'embed selon la watch. Vrai si au moins une cible a reçu."""
        routed_user_ids = self.routes.get(watch_name)
        if routed_user_ids is not None:
            return await self._send_to_users(routed_user_ids, embed)
        # Watch sans route dédiée : destinataires par défaut
        delivered = await self._send_to_users(self.dm_user_ids, embed)
        delivered = await self._send_to_channels(self.channel_ids, embed) or delivered
        return delivered

    @tasks.loop(seconds=CHECK_INTERVAL_SECONDS)
    async def check_deals(self):
        try:
            pending = self._fetch_pending()
        except sqlite3.Error:
            log.exception("Lecture de la base des deals impossible")
            return

        for deal_id, title, url, price, temperature, watch_name in pending:
            embed = self._build_embed(title, url, price, temperature, watch_name)
            if await self._dispatch(embed, watch_name):
                # marqué seulement si au moins une cible a reçu : sinon on
                # retentera au prochain passage
                self._mark_announced(deal_id)

        if pending:
            log.info("%d deal(s) annoncé(s) sur Discord", len(pending))

    @check_deals.before_loop
    async def before_check_deals(self):
        await self.bot.wait_until_ready()
