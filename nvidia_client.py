"""Couche d'accès à l'endpoint d'inférence hébergé de NVIDIA (build.nvidia.com / NIM).

L'endpoint est compatible avec l'API OpenAI : on réutilise donc le SDK `openai`
en changeant uniquement `base_url` et `api_key`. Ce module isole toute la logique
réseau pour que `app.py` reste centré sur l'interface Streamlit.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Iterator

from openai import OpenAI

BASE_URL = "https://integrate.api.nvidia.com/v1"

# Liste de secours d'identifiants RÉELS vérifiés sur le catalogue NVIDIA.
# Utilisée si l'appel /v1/models échoue (pas de réseau, clé invalide, etc.).
# La vraie source de vérité reste l'endpoint dynamique `client.models.list()`.
FALLBACK_MODELS: list[str] = [
    "deepseek-ai/deepseek-v4-pro",
    "deepseek-ai/deepseek-v4-flash",
    "meta/llama-3.3-70b-instruct",
    "meta/llama-3.1-405b-instruct",
    "nvidia/llama-3.1-nemotron-ultra-253b-v1",
    "nvidia/llama-3.3-nemotron-super-49b-v1.5",
    "openai/gpt-oss-120b",
    "qwen/qwen3-235b-a22b",
    "moonshotai/kimi-k2-instruct",
    "mistralai/mistral-large-2-instruct",
]

# Modèle par défaut : bon raisonnement, proche de l'esprit "Opus".
DEFAULT_MODEL = "deepseek-ai/deepseek-v4-pro"


@dataclass
class StreamDelta:
    """Un fragment de réponse en streaming.

    `reasoning` = chaîne de pensée (modèles type DeepSeek-R1 / Nemotron) ;
    `content`   = réponse finale destinée à l'utilisateur.
    """

    reasoning: str = ""
    content: str = ""


def get_client(api_key: str) -> OpenAI:
    """Construit un client OpenAI pointant vers l'endpoint NVIDIA."""
    return OpenAI(base_url=BASE_URL, api_key=api_key)


def list_models(client: OpenAI) -> list[str]:
    """Récupère la liste des modèles via /v1/models, triée par fournisseur.

    Retombe sur `FALLBACK_MODELS` si l'appel échoue.
    """
    try:
        response = client.models.list()
        ids = [m.id for m in response.data if getattr(m, "id", None)]
        if not ids:
            return FALLBACK_MODELS
        return sorted(ids)
    except Exception:
        return FALLBACK_MODELS


def _is_rate_limit(error: Exception) -> bool:
    text = str(error).lower()
    return "429" in text or "too many requests" in text or "rate limit" in text


def stream_chat(
    client: OpenAI,
    model: str,
    messages: list[dict],
    *,
    temperature: float = 0.7,
    top_p: float = 0.95,
    max_tokens: int = 2048,
    max_retries: int = 5,
) -> Iterator[StreamDelta]:
    """Streame une réponse de chat en gérant le rate limit (429) avec backoff.

    Génère des `StreamDelta` ; le raisonnement et le contenu sont séparés pour
    que l'UI puisse afficher la "réflexion" dans un volet repliable.
    """
    last_error: Exception | None = None

    for attempt in range(max_retries):
        try:
            stream = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                top_p=top_p,
                max_tokens=max_tokens,
                stream=True,
            )
            for chunk in stream:
                if not chunk.choices:
                    continue
                delta = chunk.choices[0].delta
                reasoning = getattr(delta, "reasoning_content", None) or ""
                content = delta.content or ""
                if reasoning or content:
                    yield StreamDelta(reasoning=reasoning, content=content)
            return
        except Exception as error:  # noqa: BLE001 - on relaie l'erreur à l'UI
            last_error = error
            if _is_rate_limit(error) and attempt < max_retries - 1:
                time.sleep(2 ** attempt)  # 1s, 2s, 4s, 8s...
                continue
            raise

    if last_error is not None:
        raise last_error
