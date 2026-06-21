"""Function calling (mode agent) pour l'app.

Contrairement au RAG manuel (où l'utilisateur force la recherche), ici c'est le
**modèle** qui décide d'appeler un outil. On déclare des outils au format OpenAI
(`tools`), le modèle renvoie des `tool_calls`, on les exécute, on lui rend le
résultat, et on recommence jusqu'à la réponse finale.

Deux outils fournis :
- `web_search`  : informations à jour (via SearXNG).
- `calculator`  : calcul arithmétique exact (le LLM seul est mauvais en calcul).
"""

from __future__ import annotations

import ast
import json
import operator
from dataclasses import dataclass
from typing import Callable

from openai import OpenAI

from web_search import DEFAULT_SEARXNG_URL, build_context, search

# Schémas exposés au modèle (format OpenAI / compatible NVIDIA).
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": (
                "Recherche des informations À JOUR sur le web. À utiliser pour "
                "l'actualité, les évènements récents, les dates, les prix, les "
                "versions logicielles, ou toute information postérieure à la date "
                "de coupure du modèle."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "La requête de recherche, en langage naturel.",
                    }
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "calculator",
            "description": (
                "Évalue une expression mathématique et renvoie le résultat EXACT. "
                "À utiliser pour tout calcul numérique (le modèle seul se trompe "
                "souvent sur les grands nombres)."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "expression": {
                        "type": "string",
                        "description": "Expression arithmétique, ex: '(1234*5678)+90'.",
                    }
                },
                "required": ["expression"],
            },
        },
    },
]

# Opérateurs autorisés pour l'évaluation sécurisée (pas de eval() brut).
_ALLOWED_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}


def _safe_eval(expression: str) -> str:
    """Évalue une expression arithmétique sans exécuter de code arbitraire."""

    def _eval(node: ast.AST) -> float:
        if isinstance(node, ast.Constant):
            if isinstance(node.value, (int, float)):
                return node.value
            raise ValueError("Constante non numérique")
        if isinstance(node, ast.BinOp) and type(node.op) in _ALLOWED_OPERATORS:
            return _ALLOWED_OPERATORS[type(node.op)](_eval(node.left), _eval(node.right))
        if isinstance(node, ast.UnaryOp) and type(node.op) in _ALLOWED_OPERATORS:
            return _ALLOWED_OPERATORS[type(node.op)](_eval(node.operand))
        raise ValueError("Expression non autorisée")

    try:
        tree = ast.parse(expression, mode="eval")
        return str(_eval(tree.body))
    except Exception as error:  # noqa: BLE001
        return f"Erreur de calcul : {error}"


def execute_tool(name: str, arguments: dict, *, searxng_url: str = DEFAULT_SEARXNG_URL) -> str:
    """Exécute un outil et renvoie un résultat textuel à rendre au modèle."""
    if name == "web_search":
        try:
            results = search(arguments.get("query", ""), base_url=searxng_url, max_results=5)
        except Exception as error:  # noqa: BLE001
            return f"Recherche web indisponible : {error}"
        return build_context(results) or "Aucun résultat web."
    if name == "calculator":
        return _safe_eval(arguments.get("expression", ""))
    return f"Outil inconnu : {name}"


@dataclass
class AgentResult:
    content: str
    reasoning: str
    steps: list[dict]  # historique des appels d'outils {name, arguments, result}


def run_agent(
    client: OpenAI,
    model: str,
    messages: list[dict],
    *,
    searxng_url: str = DEFAULT_SEARXNG_URL,
    temperature: float = 0.7,
    top_p: float = 0.95,
    max_tokens: int = 2048,
    max_steps: int = 5,
    on_tool: Callable[[str, dict], None] | None = None,
) -> AgentResult:
    """Boucle d'agent : le modèle peut appeler des outils jusqu'à la réponse finale."""
    msgs = list(messages)
    steps: list[dict] = []

    for _ in range(max_steps):
        response = client.chat.completions.create(
            model=model,
            messages=msgs,
            tools=TOOLS,
            tool_choice="auto",
            temperature=temperature,
            top_p=top_p,
            max_tokens=max_tokens,
        )
        message = response.choices[0].message
        tool_calls = getattr(message, "tool_calls", None)

        if not tool_calls:
            reasoning = getattr(message, "reasoning_content", None) or ""
            return AgentResult(content=message.content or "", reasoning=reasoning, steps=steps)

        # On rejoue le message assistant (avec ses tool_calls) dans l'historique.
        msgs.append(
            {
                "role": "assistant",
                "content": message.content or "",
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    }
                    for tc in tool_calls
                ],
            }
        )

        for tc in tool_calls:
            try:
                args = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {}
            if on_tool is not None:
                on_tool(tc.function.name, args)
            result = execute_tool(tc.function.name, args, searxng_url=searxng_url)
            steps.append({"name": tc.function.name, "arguments": args, "result": result})
            msgs.append({"role": "tool", "tool_call_id": tc.id, "content": str(result)})

    return AgentResult(
        content="(Limite d'étapes d'outils atteinte sans réponse finale.)",
        reasoning="",
        steps=steps,
    )
