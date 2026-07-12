"""Annonce sur Discord les deals détectés par pc-deals-bot.

Le bot pc-deals-bot (qui tourne sur la même machine) enregistre chaque deal
dans une base SQLite avec la colonne matched_watch renseignée quand le deal
correspond à une recherche. Ce cog interroge cette base toutes les minutes et
envoie les deals pas encore annoncés en MP et/ou dans un salon, puis les
marque comme annoncés dans une table dédiée (discord_announced) pour ne
jamais notifier deux fois.
"""

import logging
import sqlite3
from pathlib import Path

import discord
from discord.ext import commands, tasks

log = logging.getLogger("legum_bot.deals")

CHECK_INTERVAL_SECONDS = 60


class DealsCog(commands.Cog):
    def __init__(self, bot, db_path, dm_user_id=None, channel_id=None):
        self.bot = bot
        self.db_path = Path(db_path) if db_path else None
        self.dm_user_id = dm_user_id
        self.channel_id = channel_id
        if self.db_path and (self.dm_user_id or self.channel_id):
            self.check_deals.start()
        else:
            log.warning(
                "Annonce des deals désactivée : DEALS_DB_PATH et au moins un "
                "de DEAL_DM_USER_ID / DEAL_CHANNEL_ID doivent être renseignés"
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

    async def _send_everywhere(self, embed):
        """Envoie l'embed à toutes les cibles. Vrai si au moins une a reçu."""
        delivered = False

        if self.dm_user_id:
            try:
                user = self.bot.get_user(self.dm_user_id) or await self.bot.fetch_user(
                    self.dm_user_id
                )
                await user.send(embed=embed)
                delivered = True
            except discord.DiscordException:
                log.exception("Échec du MP à l'utilisateur %s", self.dm_user_id)

        if self.channel_id:
            try:
                channel = self.bot.get_channel(
                    self.channel_id
                ) or await self.bot.fetch_channel(self.channel_id)
                await channel.send(embed=embed)
                delivered = True
            except discord.DiscordException:
                log.exception("Échec de l'envoi dans le salon %s", self.channel_id)

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
            if await self._send_everywhere(embed):
                # marqué seulement si au moins une cible a reçu : sinon on
                # retentera au prochain passage
                self._mark_announced(deal_id)

        if pending:
            log.info("%d deal(s) annoncé(s) sur Discord", len(pending))

    @check_deals.before_loop
    async def before_check_deals(self):
        await self.bot.wait_until_ready()
