"""Génération des réponses de LegumBot par un modèle local.

Le modèle (Ministral-3-3B) tourne dans un llama-server résident sur
127.0.0.1:8080. Rien ne sort de la machine.

Principe de conception : le modèle n'écrit JAMAIS de prénom. Il produit une
phrase anonyme, et l'appelant appose lui-même la mention Discord, comme le
faisait déjà le tirage dans vocabulary.py. Ministral confondait les
destinataires dans 3 cas sur 12 ; cette contrainte rend l'erreur impossible.

Tout échec — serveur absent, délai dépassé, quota épuisé, sortie douteuse —
retombe silencieusement sur les listes de vocabulary.py. Le bot ne peut donc
jamais devenir moins bon qu'avant.
"""

import asyncio
import logging
import random
import re
import time
import unicodedata
from pathlib import Path

import aiohttp

log = logging.getLogger("legum_bot.llm")

SYSTEM_PROMPT = (
    "Tu es LegumBot, le bot Discord d'une bande de potes.\n\n"
    "REGLES ABSOLUES :\n"
    "- Reponds en francais uniquement.\n"
    "- UNE seule phrase, maximum 50 mots.\n"
    "- Ne cite AUCUN prenom, AUCUN pseudo, AUCUN @.\n"
    "- Parle a la personne en disant tu, jamais par son nom.\n"
    "- Aucun guillemet, aucun asterisque, aucun markdown.\n"
    "- Aucune insulte, aucun propos blessant, aucune moquerie mechante.\n"
    "- Pas de preambule ni d'explication : uniquement la phrase.\n\n"
    "Ton : chaleureux, taquin, complice. Tu peux etre familier."
)

# 50 mots de francais valent ~93 tokens pour le tokenizer de Ministral
# (mesure : 63 tokens pour 34 mots). On laisse un peu de marge.
MAX_TOKENS = 110
MAX_CHARS = 400
TEMPERATURE = 0.85
TOP_P = 0.9

# Au-dela de ce nombre d'echecs consecutifs, on cesse d'essayer un moment
# plutot que d'ajouter un delai a chaque message.
FAILURES_BEFORE_BACKOFF = 3
BACKOFF_SECONDS = 300

# Grossieretes tolerees (choix assume) : putain, merde, bordel, chier...
# Ne sont bloques que les termes insultants ou blessants adresses a quelqu'un.
# La liste vit dans insultes.txt, hors du depot (voir .gitignore) : une entree
# par ligne, sans accents. Un mot seul est compare mot a mot, une expression
# de plusieurs mots est cherchee telle quelle dans le texte replie.
INSULT_FILE = Path(__file__).with_name("insultes.txt")


def _fold(text):
    """Minuscules sans accents, pour comparer prenoms et insultes."""
    text = unicodedata.normalize("NFD", text.lower())
    return "".join(c for c in text if unicodedata.category(c) != "Mn")


def _load_insults(path=INSULT_FILE):
    """Renvoie (mots, expressions). Fichier absent : aucun filtrage, avec un avertissement."""
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        log.warning("%s introuvable : filtrage des insultes desactive", path.name)
        return frozenset(), ()
    entries = [_fold(line.strip()) for line in lines]
    entries = [e for e in entries if e and not e.startswith("#")]
    words = frozenset(e for e in entries if " " not in e)
    phrases = tuple(e for e in entries if " " in e)
    return words, phrases


INSULT_WORDS, INSULT_PHRASES = _load_insults()


class LlmClient:
    """Client du llama-server, avec quota, verrou et repli sur listes figées."""

    def __init__(
        self,
        url="http://127.0.0.1:8080/v1/chat/completions",
        enabled=True,
        timeout=30,
        known_names=(),
        bucket_capacity=40,
        refill_per_hour=120,
    ):
        self.url = url
        self.enabled = enabled
        self.timeout = timeout
        self.known_names = [_fold(n) for n in known_names if n]
        self.bucket_capacity = float(bucket_capacity)
        self.refill_rate = float(refill_per_hour) / 3600.0

        self._session = None
        self._lock = asyncio.Lock()
        self._tokens = float(bucket_capacity)
        self._last_refill = time.monotonic()
        self._failures = 0
        self._blocked_until = 0.0
        self._generated = 0
        self._fallbacks = 0
        self._last_error = None

    # ------------------------------------------------------------- interne

    def _take_token(self):
        """Seau à jetons : autorise les vagues, régule le débit soutenu."""
        now = time.monotonic()
        self._tokens = min(
            self.bucket_capacity,
            self._tokens + (now - self._last_refill) * self.refill_rate,
        )
        self._last_refill = now
        if self._tokens >= 1.0:
            self._tokens -= 1.0
            return True
        return False

    def _clean(self, text):
        """Nettoie la sortie du modèle. Renvoie None si elle est inutilisable."""
        if not text:
            return None
        text = text.strip().split("\n")[0].strip()
        text = re.sub(r"[*_`~]", "", text)
        text = text.strip().strip('"«»“”‘’').strip()

        if len(text) > MAX_CHARS:
            coupe = max(text.rfind(". ", 0, MAX_CHARS), text.rfind("! ", 0, MAX_CHARS),
                        text.rfind("? ", 0, MAX_CHARS))
            text = text[: coupe + 1] if coupe > 60 else text[:MAX_CHARS].rsplit(" ", 1)[0]
            text = text.strip()

        if len(text) < 3:
            return None

        plie = _fold(text)
        for nom in self.known_names:
            if re.search(r"\b" + re.escape(nom) + r"\b", plie):
                log.info("Repli : le modele a cite un prenom (%s)", nom)
                return None
        for phrase in INSULT_PHRASES:
            if phrase in plie:
                log.info("Repli : propos blessant detecte (%s)", phrase)
                return None
        blessants = INSULT_WORDS & set(re.findall(r"[a-z]+", plie))
        if blessants:
            log.info("Repli : insulte detectee (%s)", ", ".join(sorted(blessants)))
            return None
        return text

    async def _ask(self, situation):
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        payload = {
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": situation},
            ],
            "max_tokens": MAX_TOKENS,
            "temperature": TEMPERATURE,
            "top_p": TOP_P,
        }
        async with self._session.post(
            self.url, json=payload,
            timeout=aiohttp.ClientTimeout(total=self.timeout),
        ) as reponse:
            reponse.raise_for_status()
            data = await reponse.json()
        return data["choices"][0]["message"]["content"]

    # ------------------------------------------------------------- publique

    async def phrase(self, situation, fallback):
        """Renvoie une phrase générée, ou une phrase de `fallback` si impossible.

        Ne lève jamais : tout échec devient un repli silencieux.
        """
        repli = random.choice(list(fallback)) if fallback else ""

        if not self.enabled:
            return repli
        if time.monotonic() < self._blocked_until:
            self._fallbacks += 1
            return repli
        if self._lock.locked():          # une generation a la fois, jamais de file
            self._fallbacks += 1
            return repli
        if not self._take_token():
            self._fallbacks += 1
            log.debug("Repli : quota horaire epuise")
            return repli

        async with self._lock:
            try:
                brut = await self._ask(situation)
            except Exception as err:
                self._failures += 1
                self._last_error = f"{type(err).__name__}: {err}"
                if self._failures >= FAILURES_BEFORE_BACKOFF:
                    self._blocked_until = time.monotonic() + BACKOFF_SECONDS
                    log.warning(
                        "llama-server injoignable (%s) : pause de %ds",
                        self._last_error, BACKOFF_SECONDS,
                    )
                self._fallbacks += 1
                return repli

        self._failures = 0
        propre = self._clean(brut)
        if propre is None:
            self._fallbacks += 1
            return repli
        self._generated += 1
        return propre

    def status(self):
        """État courant, pour la commande !llm status."""
        return {
            "actif": self.enabled,
            "jetons": round(
                min(self.bucket_capacity,
                    self._tokens + (time.monotonic() - self._last_refill) * self.refill_rate),
                1,
            ),
            "capacite": int(self.bucket_capacity),
            "generees": self._generated,
            "replis": self._fallbacks,
            "echecs_consecutifs": self._failures,
            "en_pause": time.monotonic() < self._blocked_until,
            "derniere_erreur": self._last_error,
        }

    async def close(self):
        if self._session is not None and not self._session.closed:
            await self._session.close()
