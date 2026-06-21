# Clone Opus — propulsé par NVIDIA NIM

Une app web **Streamlit** type « clone de Claude » branchée sur l'endpoint
d'inférence hébergé de NVIDIA (`build.nvidia.com` / NIM), **compatible OpenAI**.

- Pas de modèle local, pas de VRAM, pas de 200 Go à télécharger.
- Sélecteur de modèles **dynamique** (récupéré via `/v1/models`).
- Streaming mot à mot + affichage de la **chaîne de raisonnement** (DeepSeek-R1, Nemotron…).
- Gestion automatique du rate limit (429) avec backoff exponentiel.

> NVIDIA n'héberge pas Claude/Opus. On utilise des modèles open de très haut
> niveau (DeepSeek, Nemotron, Llama, gpt-oss, Qwen…) comme « équivalents Opus ».

## 1. Obtenir une clé API (gratuit, ~3 min)

1. Va sur [build.nvidia.com](https://build.nvidia.com) et connecte-toi (compte développeur NVIDIA gratuit, **sans carte bancaire**).
2. Ouvre n'importe quel modèle, clique sur **Get API Key**.
3. Copie la clé qui commence par `nvapi-` — **elle n'est affichée qu'une seule fois**.

> Palier gratuit : ~1 000 crédits à l'inscription, ~40 requêtes/minute.

## 2. Installation

```bash
pip install -r requirements.txt
```

## 3. Configurer la clé

Option A — fichier `.env` (recommandé) :

```bash
copy .env.example .env   # Windows
# cp .env.example .env   # macOS / Linux
```

Puis colle ta clé dans `.env`. Le fichier `.env` est ignoré par Git.

Option B — saisir la clé directement dans la barre latérale de l'app.

## 4. Lancer

```bash
streamlit run app.py
```

L'app s'ouvre sur `http://localhost:8501`.

## Option Docker (recommandée) : tout en conteneurs

Lance l'app **et** SearXNG d'un coup, isolés sur un réseau interne. Prérequis : Docker Desktop.

```powershell
copy .env.example .env   # puis colle ta clé nvapi- dedans
docker compose up --build -d
```

Ou via le script (gère .env + clé secrète SearXNG automatiquement) :

```powershell
powershell -ExecutionPolicy Bypass -File scripts\02-docker-up.ps1
```

- App : http://localhost:8501
- SearXNG : http://localhost:8888 (debug ; l'app l'appelle en interne via `http://searxng:8080`)
- Logs : `docker compose logs -f` · Arrêt : `docker compose down`

Bonnes pratiques appliquées : `Dockerfile` multi-stage (`python:3.12-slim`),
utilisateur **non-root**, `HEALTHCHECK` Streamlit, réseau interne, `.env` monté
(jamais dans l'image), `.dockerignore` excluant secrets et fichiers superflus.

## Utilisation

- **Barre latérale** : clé API, sélecteur de modèle, system prompt, température, top-p, tokens max.
- **Rafraîchir les modèles** : recharge la liste depuis `/v1/models`.
- **Nouvelle conversation** : vide l'historique.
- Le volet **« Réflexion du modèle »** affiche la chaîne de pensée quand le modèle en renvoie une.

## Structure

| Fichier | Rôle |
| --- | --- |
| `app.py` | Interface de chat Streamlit |
| `nvidia_client.py` | Client OpenAI vers NVIDIA, listing des modèles, streaming + retry |
| `web_search.py` | Recherche web (SearXNG) pour le RAG |
| `tools.py` | Agent « maison » (function calling : web_search + calculator) |
| `agent_langchain.py` | Même agent, version LangChain (`bind_tools`) |
| `requirements.txt` | Dépendances Python |
| `.env.example` | Modèle de configuration de la clé |
| `ARTICLE.md` | Article détaillé sur build.nvidia.com |
| `documentation/` | Cours et exercices (limites LLM, RAG, paramètres, agent, LangChain) |

## Dépannage

| Problème | Cause probable | Solution |
| --- | --- | --- |
| « Aucune clé » | `.env` absent ou vide | Saisis la clé dans la sidebar ou remplis `.env` |
| Erreur 401 / 403 | Clé invalide ou expirée | Régénère une clé `nvapi-` sur build.nvidia.com |
| Erreur 429 | Limite de débit (40 req/min) | Attends quelques secondes (l'app réessaie déjà avec backoff) |
| Liste de modèles courte | `/v1/models` inaccessible | Liste de secours utilisée ; vérifie ta connexion / clé |

## Sécurité

Ne committe **jamais** ta clé `nvapi-`. Sur le palier gratuit, les entrées/sorties
peuvent être enregistrées par NVIDIA : n'envoie pas de données sensibles.
