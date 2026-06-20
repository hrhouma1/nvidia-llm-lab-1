"""Recherche web via SearXNG pour donner des informations fraîches au LLM (RAG web).

SearXNG est un métamoteur auto-hébergé qui expose une API JSON
(`/search?q=...&format=json`). On récupère les meilleurs résultats, on les
formate en contexte, et `app.py` les injecte dans le prompt pour que le modèle
réponde avec des faits à jour et cite ses sources.

Le modèle ne navigue pas lui-même : c'est nous qui faisons la recherche.
"""

from __future__ import annotations

from dataclasses import dataclass

import requests

DEFAULT_SEARXNG_URL = "http://localhost:8888"


@dataclass
class SearchResult:
    title: str
    url: str
    content: str


def search(
    query: str,
    *,
    base_url: str = DEFAULT_SEARXNG_URL,
    max_results: int = 5,
    timeout: int = 15,
) -> list[SearchResult]:
    """Interroge SearXNG et retourne au plus `max_results` résultats.

    Lève une exception réseau/HTTP en cas d'échec (gérée par l'appelant).
    """
    endpoint = base_url.rstrip("/") + "/search"
    params = {
        "q": query,
        "format": "json",
        "safesearch": 0,
        "language": "fr",
    }
    # User-Agent explicite : certaines instances rejettent les requêtes "robot".
    headers = {"User-Agent": "clone-opus-nvidia/1.0"}

    response = requests.get(endpoint, params=params, headers=headers, timeout=timeout)
    response.raise_for_status()
    data = response.json()

    results: list[SearchResult] = []
    for item in data.get("results", [])[:max_results]:
        results.append(
            SearchResult(
                title=item.get("title", "") or "",
                url=item.get("url", "") or "",
                content=item.get("content", "") or "",
            )
        )
    return results


def build_context(results: list[SearchResult]) -> str:
    """Formate les résultats en bloc de contexte injectable dans le prompt."""
    if not results:
        return ""
    lines = ["Résultats de recherche web (sources numérotées) :", ""]
    for i, r in enumerate(results, start=1):
        lines.append(f"[{i}] {r.title}")
        lines.append(f"URL : {r.url}")
        if r.content:
            lines.append(f"Extrait : {r.content}")
        lines.append("")
    return "\n".join(lines).strip()


def augment_prompt(user_query: str, context: str) -> str:
    """Construit le message utilisateur enrichi avec le contexte web + consignes."""
    if not context:
        return user_query
    return (
        f"{context}\n\n"
        "En t'appuyant sur les résultats de recherche ci-dessus (et tes "
        "connaissances si nécessaire), réponds à la question suivante. "
        "Cite tes sources avec leur numéro entre crochets, par ex. [1], [2]. "
        "Si les sources ne suffisent pas, dis-le clairement.\n\n"
        f"Question : {user_query}"
    )
