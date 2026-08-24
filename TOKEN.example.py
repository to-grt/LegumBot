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

# --- Génération locale des réponses (llm.py + llama-server) ---------------
# Le modèle Ministral-3-3B tourne dans un llama-server sur 127.0.0.1:8080
# (service systemd llama-server). Si le serveur est absent ou trop lent, le
# bot retombe automatiquement sur les listes de vocabulary.py : il ne peut
# jamais devenir moins bavard qu'avant.
LLM_ENABLED = True
LLM_URL = "http://127.0.0.1:8080/v1/chat/completions"
# Une réponse prend 7 à 12 s en pratique. 30 s laisse de la marge.
LLM_TIMEOUT = 30
# Seau à jetons : LLM_BUCKET_CAPACITY générations peuvent partir d'affilée
# (pour absorber les vagues), puis le rythme se régule à LLM_REFILL_PER_HOUR.
LLM_BUCKET_CAPACITY = 40
LLM_REFILL_PER_HOUR = 120
# Le modèle a pour consigne de ne jamais citer de prénom (c'est le bot qui
# appose la mention). S'il en produit un quand même, on replie sur
# vocabulary.py. Mets ici les prénoms de la bande, en minuscules sans accent.
LLM_KNOWN_NAMES = ["theo", "antoine", "yoann", "marie", "victor", "nicolas", "lucas"]

# --- Probabilités de déclenchement ----------------------------------------
# Ajustables à chaud sans toucher au code. Attention : à ces valeurs, une
# soirée à 200 messages/heure produit 60 à 100 messages du bot. Baisse-les
# si ça devient pénible.
P_TYPING = 0.20    # quelqu'un est en train d'écrire
P_MUTED = 0.20     # quelqu'un coupe son micro en vocal
P_GOODBYE = 0.20   # quelqu'un quitte le vocal entre 0h et 8h
P_IMAGE = 0.20     # quelqu'un poste une pièce jointe
P_ANTOINE = 0.50   # Antoine écrit un message
P_MESSAGE = 0.20   # n'importe quel autre message

# Salon où sont annoncés les événements vocaux (micro coupé, départ nocturne).
# Si ce salon n'existe pas, le bot se replie sur le premier salon où il peut
# écrire et le signale dans ses logs.
VOICE_CHANNEL_NAME = "general"
