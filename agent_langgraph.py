"""Le MÊME agent, version LangGraph : un GRAPHE d'états.

Là où `agent_langchain.py` était une boucle linéaire écrite à la main, ici on
DÉCLARE un graphe :

    START → [model] → (tool_calls ?) ─oui→ [tools] ─┐
                          │ non                      │
                          ▼                           └─(retour)─▶ [model]
                         END

- `model` : appelle le LLM (avec outils attachés) ;
- `tools` : exécute les outils demandés (ToolNode, fourni par LangGraph) ;
- l'arête conditionnelle (`tools_condition`) route vers `tools` ou `END` ;
- l'arête `tools → model` crée la BOUCLE contrôlée.

LangGraph gère pour nous : l'état partagé (`messages`), la boucle, et la
condition d'arrêt. On réutilise exactement les mêmes outils que LangChain.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated, TypedDict

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition

from agent_langchain import NVIDIA_BASE_URL, _build_tools
from web_search import DEFAULT_SEARXNG_URL


class AgentState(TypedDict):
    """L'etat partage circule entre les noeuds. `add_messages` ACCUMULE les
    messages au lieu de les ecraser (reducer)."""

    messages: Annotated[list, add_messages]


@dataclass
class LangGraphResult:
    content: str
    steps: list[dict]  # {name, arguments, result}


def _build_graph(llm_with_tools, tools):
    """Construit et compile le graphe d'etats de l'agent."""

    def call_model(state: AgentState) -> dict:
        response = llm_with_tools.invoke(state["messages"])
        return {"messages": [response]}

    graph = StateGraph(AgentState)
    graph.add_node("model", call_model)
    graph.add_node("tools", ToolNode(tools))

    graph.add_edge(START, "model")
    # tools_condition : si le dernier message a des tool_calls -> "tools", sinon -> END
    graph.add_conditional_edges("model", tools_condition)
    graph.add_edge("tools", "model")  # la boucle controlee

    return graph.compile()


def run_langgraph_agent(
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
    recursion_limit: int = 12,
) -> LangGraphResult:
    """Execute l'agent LangGraph et renvoie reponse + outils utilises."""
    tools = _build_tools(searxng_url)
    llm = ChatOpenAI(
        base_url=NVIDIA_BASE_URL,
        api_key=api_key,
        model=model,
        temperature=temperature,
        top_p=top_p,
        max_tokens=max_tokens,
    ).bind_tools(tools)

    app = _build_graph(llm, tools)

    messages = [SystemMessage(content=system_prompt)]
    for msg in history:
        if msg["role"] == "user":
            messages.append(HumanMessage(content=msg["content"]))
        elif msg["role"] == "assistant":
            messages.append(AIMessage(content=msg["content"]))
    messages.append(HumanMessage(content=query))

    final_state = app.invoke(
        {"messages": messages}, config={"recursion_limit": recursion_limit}
    )

    out_messages = final_state["messages"]

    # Reconstituer les etapes outils : on associe chaque appel (AIMessage) a son
    # resultat (ToolMessage) via tool_call_id.
    pending: dict[str, dict] = {}
    steps: list[dict] = []
    for m in out_messages:
        for tc in getattr(m, "tool_calls", None) or []:
            pending[tc["id"]] = {"name": tc["name"], "arguments": tc.get("args", {})}
        if isinstance(m, ToolMessage):
            base = pending.get(m.tool_call_id, {"name": "?", "arguments": {}})
            steps.append({**base, "result": str(m.content)})

    final = out_messages[-1]
    content = final.content if isinstance(final.content, str) else str(final.content)
    return LangGraphResult(content=content, steps=steps)
