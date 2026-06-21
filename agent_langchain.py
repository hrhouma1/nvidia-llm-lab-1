"""Le MÊME agent que tools.py, mais écrit avec LangChain.

Objectif pédagogique : montrer ce qu'apporte LangChain. On utilise ici les
primitives stables de `langchain_core` :
- `ChatOpenAI.bind_tools(...)` : on attache les outils au modèle ;
- `@tool` : on déclare un outil (sa docstring sert de description) ;
- les messages typés `SystemMessage / HumanMessage / AIMessage / ToolMessage`.

On garde une petite boucle d'orchestration (comme tools.py), mais LangChain gère
la sérialisation des outils, le parsing des `tool_calls` et l'exécution via
`tool.invoke(...)`. Cette approche `bind_tools` est portable entre LangChain 0.3
et 1.x (contrairement à `AgentExecutor`, dont l'emplacement change selon les
versions).

Même endpoint NVIDIA (compatible OpenAI), mêmes deux outils.
"""

from __future__ import annotations

from dataclasses import dataclass

from langchain_core.messages import (
    AIMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI

from tools import _safe_eval
from web_search import DEFAULT_SEARXNG_URL, build_context, search

NVIDIA_BASE_URL = "https://integrate.api.nvidia.com/v1"


def _build_tools(searxng_url: str):
    """Cree les outils LangChain (la docstring sert de description au modele)."""

    @tool
    def web_search(query: str) -> str:
        """Recherche des informations A JOUR sur le web (actualite, dates, prix,
        versions). A utiliser pour toute information recente ou qui change."""
        try:
            results = search(query, base_url=searxng_url, max_results=5)
        except Exception as error:  # noqa: BLE001
            return f"Recherche web indisponible : {error}"
        return build_context(results) or "Aucun resultat web."

    @tool
    def calculator(expression: str) -> str:
        """Evalue une expression mathematique et renvoie le resultat EXACT.
        A utiliser pour tout calcul numerique."""
        return _safe_eval(expression)

    return [web_search, calculator]


@dataclass
class LangChainResult:
    content: str
    steps: list[dict]  # {name, arguments, result}


def run_langchain_agent(
    api_key: str,
    model: str,
    system_prompt: str,
    history: list[dict],
    query: str,
    *,
    searxng_url: str = DEFAULT_SEARXNG_URL,
    temperature: float = 0.7,
    top_p: float = 0.95,
    max_tokens: int = 2048,
    max_iterations: int = 5,
) -> LangChainResult:
    """Execute l'agent LangChain (bind_tools) et renvoie reponse + outils utilises."""
    tools = _build_tools(searxng_url)
    tools_by_name = {t.name: t for t in tools}

    llm = ChatOpenAI(
        base_url=NVIDIA_BASE_URL,
        api_key=api_key,
        model=model,
        temperature=temperature,
        top_p=top_p,
        max_tokens=max_tokens,
    ).bind_tools(tools)

    messages = [SystemMessage(content=system_prompt)]
    for msg in history:
        if msg["role"] == "user":
            messages.append(HumanMessage(content=msg["content"]))
        elif msg["role"] == "assistant":
            messages.append(AIMessage(content=msg["content"]))
    messages.append(HumanMessage(content=query))

    steps: list[dict] = []

    for _ in range(max_iterations):
        ai_msg: AIMessage = llm.invoke(messages)
        messages.append(ai_msg)

        tool_calls = getattr(ai_msg, "tool_calls", None) or []
        if not tool_calls:
            content = ai_msg.content if isinstance(ai_msg.content, str) else str(ai_msg.content)
            return LangChainResult(content=content, steps=steps)

        for tc in tool_calls:
            name = tc["name"]
            args = tc.get("args", {})
            selected = tools_by_name.get(name)
            observation = (
                selected.invoke(args) if selected is not None else f"Outil inconnu : {name}"
            )
            steps.append({"name": name, "arguments": args, "result": str(observation)})
            messages.append(ToolMessage(content=str(observation), tool_call_id=tc["id"]))

    return LangChainResult(
        content="(Limite d'iterations atteinte sans reponse finale.)", steps=steps
    )
