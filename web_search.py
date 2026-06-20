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


# URLs de repli essayees automatiquement si l'URL fournie echoue (DNS/connexion).
# Couvre les deux contextes courants : app en local et app en Docker.
_FALLBACK_URLS = [
    "http://localhost:8888",
    "http://127.0.0.1:8888",
    "http://searxng:8080",
]


def _candidate_urls(base_url: str) -> list[str]:
    """Construit la liste des URLs a essayer : celle fournie d'abord, puis les replis."""
    candidates = [base_url.rstrip("/")] if base_url else []
    for url in _FALLBACK_URLS:
        if url not in candidates:
            candidates.append(url)
    return candidates


def _query_one(base_url: str, query: str, max_results: int, timeout: int) -> list[SearchResult]:
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


def search(
    query: str,
    *,
    base_url: str = DEFAULT_SEARXNG_URL,
    max_results: int = 5,
    timeout: int = 15,
) -> list[SearchResult]:
    """Interroge SearXNG et retourne au plus `max_results` résultats.

    Essaie l'URL fournie puis des URLs de repli (localhost / searxng) afin de
    fonctionner aussi bien en local qu'en Docker, sans configuration manuelle.
    Lève la dernière exception réseau/HTTP si toutes les URLs échouent.
    """
    last_error: Exception | None = None
    for candidate in _candidate_urls(base_url):
        try:
            return _query_one(candidate, query, max_results, timeout)
        except (requests.ConnectionError, requests.Timeout) as error:
            # URL injoignable (DNS/connexion) : on tente la suivante.
            last_error = error
            continue
        except Exception as error:  # noqa: BLE001 - autre erreur : on remonte direct
            raise error

    if last_error is not None:
        raise last_error
    return []


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
