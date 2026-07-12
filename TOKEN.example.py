# Copier ce fichier vers TOKEN.py (gitignoré) et remplir.
# Seul PRIVATE_TOKEN est obligatoire.

# Token du bot : Discord Developer Portal > ton application > Bot > Reset Token
PRIVATE_TOKEN = "colle-le-token-ici"

# --- Fonctions historiques du bot (optionnel) ---
ALLOWED_USERS = []  # IDs autorisés à faire !restart
ANTOINE_ID = None
YOANN_ID = None

# --- Annonce des deals de pc-deals-bot (optionnel) ---
# Chemin de la base SQLite remplie par pc-deals-bot
DEALS_DB_PATH = "/home/theo/pc-deals-bot/data/deals.db"
# ID de la personne à prévenir en MP (clic droit sur le profil > Copier l'identifiant,
# avec le mode développeur Discord activé). None pour désactiver.
DEAL_DM_USER_ID = None
# ID du salon texte où poster les deals. None pour désactiver.
DEAL_CHANNEL_ID = None
