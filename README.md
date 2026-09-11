# LegumBot

Bot Discord d'une bande de potes, qui tourne sur un Raspberry Pi 5.
Il réagit aux événements du serveur (messages, frappe, vocal, images) et
annonce les bons plans détectés par [pc-deals-bot](../pc-deals-bot).

Depuis août 2026, ses réponses ne sont plus tirées au sort dans des listes
figées : elles sont **générées localement** par un modèle de langage qui
tourne sur la machine. Rien ne sort du Pi.

---

## Commandes

| Commande | Accès | Effet |
|---|---|---|
| `!hello` | tous | Te salue chaleureusement |
| `!ping` | tous | Vérifie que le bot répond encore |
| `!help` | tous | Liste les commandes |
| `!llm on\|off\|status` | **admin** | Coupe / réactive la génération, affiche les compteurs |
| `!restart` | **admin** | Redémarre le bot (systemd le relance) |
| `!scan` (`!veille`, `!deals`) | **admin** | Passage de veille immédiat — cooldown 30 s |

« admin » = les IDs listés dans `ALLOWED_USERS` de `TOKEN.py`.

### `!llm status`
Affiche l'état du serveur de génération, les jetons restants, le nombre de
phrases générées, le nombre de replis sur les listes figées, et la dernière
erreur rencontrée. C'est le premier réflexe quand le bot semble moins inspiré.

---

## Déclenchements automatiques

| Situation | Probabilité | Liste de repli |
|---|---|---|
| Quelqu'un cite le bot (`legum`, `bot`, `robot`…) | 100 % | `GREETINGS` |
| Quelqu'un poste une pièce jointe | `P_IMAGE` (20 %) | `GREETINGS` |
| Antoine écrit un message | `P_ANTOINE` (30 %) | `MESSAGES_ANTOINE` |
| N'importe quel autre message | `P_MESSAGE` (10 %) | `MESSAGES_TYPING` |
| Quelqu'un est en train d'écrire | `P_TYPING` (10 %) | `MESSAGES_TYPING` |
| Quelqu'un coupe son micro en vocal | `P_MUTED` (10 %) | `MESSAGES_MUTED` |
| Quelqu'un quitte le vocal entre 0h et 8h | `P_GOODBYE` (10 %) | `MESSAGES_GOODBYE` |
| Une commande après plus de 10 min d'absence | 100 % | `GREETINGS` |

Les commandes (`!…`) ne déclenchent jamais de réponse générique en plus.

**Si le bot devient trop bavard**, baisse les probabilités dans `TOKEN.py` puis
`sudo systemctl restart legum-bot`. Aucune modification de code nécessaire.

---

## Architecture

```
llama-server (systemd)          legum-bot (systemd)
  Ministral-3-3B Q4_K_M   <--   llm.py  <--  legum_bot.py
  127.0.0.1:8080                             deals_cog.py
  ~4,2 Go de RAM                             vocabulary.py (repli)
```

`llm.py` interroge le serveur en HTTP local. **Tout échec — serveur absent,
délai dépassé, quota épuisé, sortie douteuse — retombe silencieusement sur les
listes de `vocabulary.py`.** Le bot ne peut donc jamais devenir moins bavard
qu'avant l'ajout du modèle.

### Le modèle n'écrit jamais de prénom
Ministral confondait les destinataires dans 3 cas sur 12. La consigne système
lui interdit donc tout prénom : il produit une phrase anonyme, et le bot appose
lui-même la mention Discord. Un filet de sécurité (`LLM_KNOWN_NAMES`) replie
sur les listes figées si un prénom passe malgré tout.

### Garde-fous
- Une génération à la fois, **jamais de file d'attente** — si occupé, repli
- Seau à jetons : 40 d'affilée pour absorber les vagues, puis 120/heure
- Timeout 30 s ; après 3 échecs consécutifs, pause de 5 min
- Nettoyage : markdown retiré, guillemets encadrants retirés, 400 caractères max
- Insultes et propos blessants bloqués ; **grossièretés tolérées**
- Les emoji sont conservés (choix assumé)

Latence typique mesurée : **10 s** (6 à 15 s), masquée par l'indicateur
« écrit… » de Discord.

---

## Installation

```bash
cp TOKEN.example.py TOKEN.py   # puis remplir, au minimum PRIVATE_TOKEN
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
```

`TOKEN.example.py` documente toutes les clés : IDs, routage des deals,
paramètres du modèle et probabilités de déclenchement. Seul `PRIVATE_TOKEN`
est obligatoire — tout le reste a une valeur par défaut.

La liste des insultes bloquées vit dans `insultes.txt`, à côté de `llm.py`,
volontairement hors du dépôt : une entrée par ligne, sans accents. Sans ce
fichier, le bot démarre quand même mais ne filtre plus les insultes (un
avertissement apparaît dans le journal).

### Services

```bash
sudo systemctl status llama-server   # serveur de génération
sudo systemctl status legum-bot      # le bot
journalctl -u legum-bot -f           # journal en direct
```

Le modèle vit dans `/home/theo/legum-llm/` (binaire `llama-server`, modèle
GGUF, mesures de benchmark). Il n'est pas dans ce dépôt : 2 Go.

---

## Dépannage

| Symptôme | Piste |
|---|---|
| Réponses répétitives, déjà vues | Le modèle ne répond plus → `!llm status`, puis `systemctl status llama-server` |
| Bot muet | `journalctl -u legum-bot -n 50` |
| Trop bavard | Baisser `P_*` dans `TOKEN.py`, redémarrer |
| Réponses trop lentes | Normal (10 s). Sinon vérifier `vcgencmd get_throttled` |
| Annonces vocales absentes | Le bot journalise au démarrage quel salon il utilise |
| Tout couper sans redémarrer | `!llm off` — retour immédiat aux phrases toutes faites |
