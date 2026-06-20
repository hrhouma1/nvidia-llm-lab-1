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
| `requirements.txt` | Dépendances Python |
| `.env.example` | Modèle de configuration de la clé |
| `ARTICLE.md` | Article détaillé sur build.nvidia.com |

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
