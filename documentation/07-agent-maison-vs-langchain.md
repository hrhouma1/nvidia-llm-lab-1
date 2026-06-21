# Agent « à la main » vs LangChain

> Objectif : comprendre **ce qu'apporte un framework** comme LangChain pour
> construire un agent, en comparant deux implémentations du **même** agent
> (mêmes outils : `web_search` + `calculator`, même endpoint NVIDIA).

---

## 1. Le rappel : qu'est-ce qu'un agent (function calling) ?

Un agent, c'est une boucle :

1. On envoie au modèle la question **+ la liste des outils** disponibles.
2. Le modèle répond soit par du texte (fin), soit par une **demande d'appel
   d'outil** (`tool_calls`).
3. Notre code **exécute** l'outil et renvoie le résultat au modèle.
4. On recommence jusqu'à ce que le modèle donne une réponse finale.

Cette boucle est la même partout. Ce qui change, c'est **qui écrit la
plomberie**.

---

## 2. Version « Maison » (`tools.py`)

On gère tout nous-mêmes avec le SDK OpenAI :

- on écrit les **schémas JSON** des outils à la main (`TOOLS = [...]`) ;
- on lit `response.choices[0].message.tool_calls` ;
- on **désérialise** les arguments (`json.loads(tc.function.arguments)`) ;
- on **route** vers la bonne fonction Python ;
- on **réinjecte** le résultat avec le bon `tool_call_id` ;
- on gère la boucle, le nombre max d'itérations, etc.

```python
# Extrait simplifié de tools.py
TOOLS = [
    {"type": "function", "function": {"name": "calculator", "parameters": {...}}},
    ...
]

while True:
    msg = client.chat.completions.create(model=..., messages=messages, tools=TOOLS)
    if not msg.tool_calls:
        return msg.content
    for tc in msg.tool_calls:
        args = json.loads(tc.function.arguments)   # parsing manuel
        result = dispatch(tc.function.name, args)  # routage manuel
        messages.append({"role": "tool", "tool_call_id": tc.id, "content": result})
```

Avantages : **zéro dépendance** supplémentaire, on voit **tout** ce qui se passe.
Inconvénient : c'est **verbeux** et il faut écrire/maintenir les schémas JSON.

---

## 3. Version LangChain (`agent_langchain.py`)

LangChain fournit des **briques** qui suppriment la plomberie répétitive :

| Plomberie manuelle | Brique LangChain |
|---|---|
| Écrire le schéma JSON de l'outil | Décorateur `@tool` (le schéma est **déduit** de la signature + docstring) |
| Attacher les outils à l'appel | `llm.bind_tools(tools)` |
| Parser `tool_calls` / arguments JSON | `ai_msg.tool_calls` (déjà en dict Python) |
| Construire les messages `role/content` | Objets typés `SystemMessage`, `HumanMessage`, `AIMessage`, `ToolMessage` |
| Exécuter l'outil | `tool.invoke(args)` |

```python
# Extrait de agent_langchain.py
@tool
def calculator(expression: str) -> str:
    """Evalue une expression mathematique et renvoie le resultat EXACT."""
    return _safe_eval(expression)

llm = ChatOpenAI(base_url=NVIDIA_BASE_URL, api_key=..., model=...).bind_tools(tools)

ai = llm.invoke(messages)
for tc in ai.tool_calls:          # déjà parsé en dict {name, args, id}
    observation = tools_by_name[tc["name"]].invoke(tc["args"])
    messages.append(ToolMessage(content=str(observation), tool_call_id=tc["id"]))
```

La **docstring** du `@tool` devient la description envoyée au modèle : la
documentation et le code ne peuvent plus diverger.

---

## 4. Tableau comparatif

| Critère | Maison (`tools.py`) | LangChain (`agent_langchain.py`) |
|---|---|---|
| Dépendances | SDK `openai` seul | `langchain` + `langchain-openai` |
| Schémas d'outils | écrits à la main (JSON) | générés depuis `@tool` |
| Parsing des appels | manuel (`json.loads`) | automatique (`.tool_calls`) |
| Lisibilité de la boucle | tout est explicite | briques + petite boucle |
| Courbe d'apprentissage | faible | moyenne (API qui bouge) |
| Portabilité multi-fournisseurs | à recoder | changer la classe de chat |
| Écosystème (mémoire, RAG, tracing…) | à construire | intégré (LangSmith, retrievers…) |

---

## 5. Le piège des versions (vécu dans ce projet)

LangChain bouge **vite**. L'API « haut niveau » `AgentExecutor` /
`create_tool_calling_agent` a changé d'emplacement entre LangChain **0.3** et
**1.x** (`ImportError: cannot import name 'AgentExecutor'`).

C'est pourquoi `agent_langchain.py` utilise l'approche **`bind_tools`** de
`langchain_core`, **stable** entre les deux versions. Leçon : avec un framework,
on gagne en confort mais on **dépend de ses choix d'API** — privilégier les
primitives stables (`langchain_core`) aux helpers de haut niveau quand la
robustesse compte.

---

## 6. Quand choisir quoi ?

- **Maison** : pour **apprendre** comment marche le function calling, pour un
  projet minimaliste, ou pour garder un contrôle total sans dépendance.
- **LangChain** : dès qu'on veut **composer** (mémoire, RAG, plusieurs modèles,
  tracing, multi-outils complexes) sans réécrire la plomberie à chaque fois.
- **LangGraph** (branche suivante) : quand l'agent devient un **graphe
  d'états** (branches conditionnelles, boucles contrôlées, reprise, human-in-
  the-loop). C'est l'étage au-dessus de LangChain pour les workflows complexes.

---

## 7. Exercice guidé (dans l'application)

1. Lancez l'app (Docker), ouvrez la **barre latérale**.
2. Activez **« Mode outils (agent) »**.
3. Un sélecteur **« Moteur de l'agent »** apparaît : `Maison` ou `LangChain`.
4. Posez **la même question** avec chaque moteur, par exemple :
   > « Calcule 87654 × 4321 puis dis-moi qui est le premier ministre du Canada. »
5. Observez dans les deux cas :
   - les **outils appelés** (`calculator`, puis `web_search`) ;
   - la **réponse finale** (le calcul exact + l'info à jour).

**À retenir :** le **résultat** est le même — c'est la **façon de l'obtenir**
côté code qui diffère. Le framework ne rend pas le modèle « plus intelligent »,
il rend votre **code plus court et plus composable**.
