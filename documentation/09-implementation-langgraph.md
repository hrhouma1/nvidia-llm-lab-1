# Implémentation LangGraph : l'agent en graphe d'états

> Suite du cours 08. Ici on **code** concrètement l'agent avec LangGraph et on
> voit, ligne par ligne, comment le **graphe d'états** résout les limites de la
> chaîne LangChain. Fichier : `agent_langgraph.py`.

---

## 1. L'idée : un graphe, pas une ligne

Avec LangChain on avait une **boucle linéaire** écrite à la main. LangGraph nous
fait **déclarer** un graphe et s'occupe de l'exécuter :

```text
        ┌──────────┐   tool_calls ?   ┌──────────┐
START ─▶│  model   │ ───── oui ─────▶ │  tools   │
        └────┬─────┘                  └────┬─────┘
             │ non                          │
             ▼                              │ (retour)
            END  ◀───────────────────────────┘
```

- **`model`** : appelle le LLM (outils attachés) ;
- **`tools`** : exécute les outils demandés ;
- **arête conditionnelle** : « le dernier message contient-il des `tool_calls` ? »
  → oui : aller à `tools` ; non : `END` ;
- **arête `tools → model`** : la **boucle** (le modèle revoit les résultats).

---

## 2. Les 3 concepts clés

### a) L'état partagé (`State`)

```python
class AgentState(TypedDict):
    messages: Annotated[list, add_messages]
```

`messages` est l'état qui circule entre les nœuds. `add_messages` est un
**reducer** : il **ajoute** les nouveaux messages au lieu d'**écraser** la liste.
C'est LangGraph qui gère cet état → fini le `messages` trimballé à la main.

### b) Les nœuds (`node`)

Un nœud = une fonction qui reçoit l'état et renvoie une **mise à jour** :

```python
def call_model(state: AgentState) -> dict:
    response = llm_with_tools.invoke(state["messages"])
    return {"messages": [response]}   # ajouté à l'état grâce au reducer
```

Le nœud `tools` est **fourni** par LangGraph (`ToolNode(tools)`) : il lit les
`tool_calls`, exécute les bons outils et renvoie des `ToolMessage`.

### c) Les arêtes (`edge`), dont les conditionnelles

```python
graph.add_edge(START, "model")
graph.add_conditional_edges("model", tools_condition)  # -> "tools" ou END
graph.add_edge("tools", "model")                       # la boucle
app = graph.compile()
```

`tools_condition` est un **routeur** prêt à l'emploi : il regarde le dernier
message et décide la suite. **C'est ça qu'on devait coder en `if` à la main
avant.**

---

## 3. Exécution

```python
final_state = app.invoke(
    {"messages": messages},
    config={"recursion_limit": 12},   # garde-fou anti-boucle infinie
)
```

- `recursion_limit` : nombre max de transitions → empêche un agent de tourner en
  rond (la « boucle contrôlée » du cours 08).
- À la fin, `final_state["messages"]` contient **tout** l'historique (questions,
  décisions du modèle, résultats d'outils, réponse finale). On le parcourt pour
  reconstruire la liste des outils appelés (affichée dans l'app).

---

## 4. Ce que LangGraph a résolu (vs limites du cours 08)

| Limite de la chaîne LangChain | Réponse de LangGraph (dans ce code) |
|---|---|
| Boucle écrite à la main | arête `tools → model` + `tools_condition` |
| `if` de routage manuels | arêtes **conditionnelles** natives |
| `messages` géré à la main | `State` + reducer `add_messages` |
| Risque de boucle infinie | `recursion_limit` |
| Difficile à étendre | il suffit d'**ajouter un nœud / une arête** |

Et ce qu'on n'a pas (encore) utilisé mais que le graphe **rend possible
gratuitement** :
- **checkpoints** (persistance, pause/reprise d'une exécution) ;
- **interrupt** (human-in-the-loop : pause → validation → reprise) ;
- **multi-agents** (chaque agent = un sous-graphe).

---

## 5. Les 3 moteurs côte à côte (récap du projet)

| | Maison (`tools.py`) | LangChain (`agent_langchain.py`) | LangGraph (`agent_langgraph.py`) |
|---|---|---|---|
| Qui écrit la boucle ? | nous | nous (courte) | **le graphe** |
| Outils | JSON à la main | `@tool` | `@tool` (réutilisés) |
| Routage modèle/outils | `if` manuel | `if` manuel | `tools_condition` |
| État | dicts | messages typés | `State` + reducer |
| Extensible (branches, pause) | dur | dur | **facile** |

> Les **trois** donnent le même résultat sur une question simple. La différence
> apparaît quand le workflow se **complexifie** : c'est là que le graphe gagne.

---

## 6. Exercice (dans l'application)

1. Barre latérale → activez **« Mode outils (agent) »**.
2. **Moteur de l'agent** : choisissez **`LangGraph`**.
3. Posez la même question qu'avec les autres moteurs :
   > « Calcule 87654 × 4321 puis dis-moi qui est le premier ministre du Canada. »
4. Comparez les **outils appelés** et la **réponse** avec `Maison` et
   `LangChain` : identiques. Le code, lui, est passé d'une **boucle** à un
   **graphe**.

### Pour aller plus loin (idée d'extension)

Ajoutez un nœud `verifier` entre `tools` et `model` qui contrôle que la
recherche web a renvoyé des résultats ; **si vide**, une arête conditionnelle
renvoie vers un nœud `reformuler`. Vous venez de créer un workflow **non
linéaire** — impossible à exprimer proprement avec une simple chaîne.
