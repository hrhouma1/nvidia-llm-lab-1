# 01 — Clés API, meilleurs modèles, et NVIDIA vs OpenRouter

> Réponse détaillée à : « Est-ce que je peux créer plusieurs clés API, une par
> modèle ? Quels sont les meilleurs modèles ? Est-ce pertinent d'utiliser
> OpenRouter, et comment ça fonctionne ? »

---

## 1. Plusieurs clés API ? Pas par modèle

Une seule clé `nvapi-` ouvre **tous les modèles** du catalogue NVIDIA (121 au
moment de l'écriture). Pour changer de modèle, tu modifies seulement le champ
`model=...` dans ton code — **pas la clé**.

Créer **plusieurs clés** reste utile, mais pour d'autres raisons :

- une clé **par projet / par app** (révocable indépendamment) ;
- séparer les environnements **dev / prod** ;
- limiter les dégâts si une clé fuite (révoquer celle-là sans tout casser).

Ce n'est donc **jamais** « une clé = un modèle ».

> Sécurité : ne mets jamais ta clé en dur dans le code. Utilise un fichier
> `.env` (ignoré par Git) ou une variable d'environnement. Si une clé est
> exposée, régénère-la immédiatement sur build.nvidia.com.

---

## 2. Les meilleurs modèles du catalogue (réels, vérifiés)

| Usage | Modèle | Pourquoi |
| --- | --- | --- |
| Raisonnement / « équivalent Opus » | `deepseek-ai/deepseek-v4-pro` | Top raisonnement + code |
| Rapide / économique | `deepseek-ai/deepseek-v4-flash` | Même famille, plus léger |
| Très gros généraliste | `qwen/qwen3.5-397b-a17b` | 397B, polyvalent |
| Raisonnement NVIDIA | `nvidia/llama-3.1-nemotron-ultra-253b-v1` | Optimisé pour les agents |
| Open weights OpenAI | `openai/gpt-oss-120b` | Bon compromis qualité/coût |
| Long contexte | `moonshotai/kimi-k2.6` | Très grand contexte |
| Multilingue | `z-ai/glm-5.1` | Solide en multilingue |
| Agentique récent | `minimaxai/minimax-m3` | Raisonnement + tool use |

Dans l'app Streamlit livrée, tu n'as pas à les mémoriser : le sélecteur récupère
la liste complète dynamiquement via `/v1/models`.

### Lister soi-même les modèles

```python
import os
from openai import OpenAI

client = OpenAI(
    base_url="https://integrate.api.nvidia.com/v1",
    api_key=os.environ["NVIDIA_API_KEY"],
)
for m in sorted(model.id for model in client.models.list()):
    print(m)
```

---

## 3. OpenRouter : c'est quoi ?

OpenRouter est un **agrégateur** d'IA : une seule clé et une seule URL
(`https://openrouter.ai/api/v1`, elle aussi **compatible OpenAI**) pour router
vers **des centaines de modèles de dizaines de fournisseurs** — y compris les
modèles **propriétaires** (Anthropic Claude, OpenAI GPT, Google Gemini) en plus
des modèles open (DeepSeek, Llama, Qwen…).

Tu changes juste l'ID du modèle (par ex. `anthropic/claude-opus-4`) et
OpenRouter choisit le fournisseur derrière, gère le basculement (fallback) et la
facturation à un seul endroit.

```python
from openai import OpenAI

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key="sk-or-...",          # clé OpenRouter
)

resp = client.chat.completions.create(
    model="anthropic/claude-opus-4",   # un vrai Claude, via OpenRouter
    messages=[{"role": "user", "content": "Bonjour !"}],
)
print(resp.choices[0].message.content)
```

---

## 4. NVIDIA NIM vs OpenRouter

| Critère | NVIDIA build.nvidia.com | OpenRouter |
| --- | --- | --- |
| Modèles | ~121 (open : DeepSeek, Llama, Qwen, gpt-oss…) | Des centaines, **dont Claude / GPT / Gemini propriétaires** |
| Vrai Opus / Claude | Non (pas hébergé) | **Oui** |
| Gratuit | Oui (crédits offerts, ~40 req/min, sans carte) | Quelques modèles `:free`, sinon payant (carte requise) |
| Qui exécute | GPU NVIDIA | Le fournisseur d'origine (NVIDIA, Anthropic, OpenAI…) |
| Compatible OpenAI | Oui | Oui |
| Base URL | `https://integrate.api.nvidia.com/v1` | `https://openrouter.ai/api/v1` |
| Préfixe de clé | `nvapi-` | `sk-or-` |

---

## 5. Quand utiliser quoi

- **Reste sur NVIDIA** si : prototypage gratuit, modèles open
  (DeepSeek / Llama / Qwen) suffisants, pas envie de payer ni de fournir une
  carte bancaire.
- **Passe sur OpenRouter** si : tu veux le **vrai Claude Opus / GPT / Gemini** au
  même endroit, comparer beaucoup de fournisseurs, ou disposer d'un fallback
  automatique entre providers.

Comme les deux sont **compatibles OpenAI**, la même app fonctionne avec les
deux : il suffit de changer `base_url` + la clé (et l'ID de modèle).

```python
# Même code, deux fournisseurs — on ne change que ces lignes :
NVIDIA   = ("https://integrate.api.nvidia.com/v1", os.environ["NVIDIA_API_KEY"])
OPENROUTER = ("https://openrouter.ai/api/v1",       os.environ["OPENROUTER_API_KEY"])

base_url, api_key = NVIDIA   # ou OPENROUTER
client = OpenAI(base_url=base_url, api_key=api_key)
```
