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
# IDs des personnes à prévenir en MP (clic droit sur le profil > Copier
# l'identifiant, avec le mode développeur Discord activé). Chaque personne
# doit partager au moins un serveur avec le bot. [] pour désactiver.
DEAL_DM_USER_IDS = []  # ex: [123456789012345678, 987654321098765432]
# IDs des salons texte où poster les deals. [] pour désactiver.
DEAL_CHANNEL_IDS = []
# Routage par recherche : {nom de watch (config.yaml de pc-deals-bot): [IDs
# à prévenir en MP]}. Les recherches absentes de ce dict vont aux
# destinataires par défaut ci-dessus.
DEAL_ROUTES = {}  # ex: {"Casque gaming": [123456789012345678]}

# --- Commande !scan : veille manuelle immédiate (optionnel) ---
# argv lancé en sous-processus pour un passage unique de pc-deals-bot (sans
# --loop). Vide => la commande !scan est désactivée. Seuls les ALLOWED_USERS
# peuvent la déclencher.
DEALS_SCAN_CMD = []  # ex: ["/home/theo/pc-deals-bot/.venv/bin/python", "-m",
#      "pc_deals_bot", "--config", "/home/theo/pc-deals-bot/config.yaml"]
# Répertoire de travail du sous-processus (là où vit pc-deals-bot).
DEALS_SCAN_CWD = None  # ex: "/home/theo/pc-deals-bot"
