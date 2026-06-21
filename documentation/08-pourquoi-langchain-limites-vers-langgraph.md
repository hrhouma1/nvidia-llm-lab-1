# Pourquoi LangChain ? Ses limites, et le passage à LangGraph

> Ce cours raconte une **progression** : on part d'un agent écrit à la main, on
> voit pourquoi LangChain aide, on bute sur ses **limites**, et on comprend
> pourquoi LangGraph existe. Fil rouge : le **même** agent (outils `web_search`
> + `calculator`, endpoint NVIDIA).

---

## 1. Étape 0 — L'agent « à la main » (`tools.py`)

On a d'abord écrit la boucle nous-mêmes avec le SDK OpenAI :

```text
[question + schémas d'outils] → modèle → tool_calls ? → on exécute → on réinjecte → on recommence
```

Ce qu'on a dû coder **manuellement** :
- les **schémas JSON** des outils ;
- le **parsing** des `tool_calls` (`json.loads`) ;
- le **routage** vers la bonne fonction Python ;
- la **réinjection** du résultat avec le bon `tool_call_id` ;
- la **boucle** et sa limite d'itérations.

✅ Avantage : transparent, zéro dépendance.
❌ Coût : verbeux, à réécrire à chaque projet.

---

## 2. Étape 1 — Pourquoi on a introduit LangChain

LangChain répond à une question simple : **« pourquoi réécrire la même plomberie
à chaque fois ? »** Il fournit des **briques réutilisables** :

| Besoin | Sans framework | Avec LangChain |
|---|---|---|
| Décrire un outil | écrire le JSON-schema | `@tool` (déduit de la signature + docstring) |
| Brancher les outils | construire l'appel `tools=[...]` | `llm.bind_tools(tools)` |
| Lire la décision du modèle | parser le JSON | `ai_msg.tool_calls` (déjà en dict) |
| Représenter la conversation | dicts `{role, content}` | messages typés (`HumanMessage`, `ToolMessage`…) |
| Changer de fournisseur | tout recoder | changer la classe de chat |
| Mémoire, RAG, tracing | à construire | composants prêts (LangSmith, retrievers…) |

**Ce qu'on a fait (branche4)** : `agent_langchain.py` refait le même agent avec
`bind_tools`. Résultat **identique** (calcul exact + recherche web à jour), mais
**code plus court et plus composable**.

> ⚠️ Leçon vécue : LangChain **bouge vite**. `AgentExecutor` a changé de place
> entre 0.3 et 1.x. On a donc choisi les **primitives stables** de
> `langchain_core` (`bind_tools`) plutôt que les helpers de haut niveau.

**Idée-clé :** LangChain ne rend pas le modèle « plus intelligent ». Il
**raccourcit et standardise le code** autour du modèle.

---

## 3. Étape 2 — Les LIMITES de LangChain (le déclic LangGraph)

Notre agent LangChain reste une **boucle linéaire simple** :

```text
modèle → outil → modèle → outil → … → réponse
```

Ça marche tant que le flux est **droit**. Mais un vrai agent a besoin de plus,
et c'est là que LangChain (la chaîne) montre ses limites :

1. **Pas de vrai graphe de contrôle.**
   Une « chaîne » va de A à B. Dès qu'on veut des **branches conditionnelles**
   (« si la recherche échoue → reformuler, sinon → répondre »), on se remet à
   coder des `if/while` à la main, et on perd le bénéfice du framework.

2. **Boucles et arrêts difficiles à maîtriser.**
   Combien d'itérations ? Quand forcer l'arrêt ? Comment éviter qu'un agent
   tourne en rond ? Dans une chaîne, c'est du bricolage.

3. **État partagé fragile.**
   On trimballe `messages` à la main. Dès qu'il faut un état riche (compteurs,
   résultats intermédiaires, drapeaux), ça devient désordonné.

4. **Pas de persistance / reprise native.**
   Reprendre une exécution interrompue, ou la rejouer, n'est pas prévu.

5. **Human-in-the-loop compliqué.**
   Mettre en **pause** pour demander une validation humaine, puis **reprendre**,
   n'est pas naturel dans une chaîne.

6. **Multi-agents / cycles.**
   Faire collaborer plusieurs agents (un « chercheur », un « rédacteur », un
   « vérificateur ») qui se repassent la main = un **graphe**, pas une ligne.

➡️ Dès que le workflow devient **non linéaire** (branches, cycles, pauses,
état), la « chaîne » n'est plus le bon outil.

---

## 4. Étape 3 — Pourquoi LangGraph

**LangGraph** (du même éditeur) modélise l'agent comme un **graphe d'états** :

- **Nœuds** = des étapes (appeler le modèle, exécuter un outil, vérifier…).
- **Arêtes** = des transitions, qui peuvent être **conditionnelles**.
- **State** = un objet d'**état partagé** typé, mis à jour à chaque nœud.
- **Cycles** = autorisés et **contrôlés** (l'agent peut revenir en arrière).
- **Checkpoints** = **persistance** → pause, reprise, rejouabilité.
- **Interrupt** = **human-in-the-loop** natif (pause → validation → reprise).

```text
        ┌──────────┐      tool_calls ?      ┌──────────┐
  ───▶  │  modèle  │ ───────────oui───────▶ │  outils  │
        └──────────┘                        └────┬─────┘
              ▲                                   │
              └───────────────────────────────────┘
                         (boucle contrôlée)
              │ non
              ▼
          [réponse]
```

| Question | Chaîne LangChain | Graphe LangGraph |
|---|---|---|
| Branches conditionnelles | `if` manuels | arêtes conditionnelles natives |
| Boucles contrôlées | bricolage | cycles + condition d'arrêt |
| État partagé | `messages` à la main | `State` typé centralisé |
| Pause / reprise | non | checkpoints |
| Validation humaine | difficile | `interrupt` natif |
| Multi-agents | lourd | graphe de sous-agents |

**En une phrase :** on passe de **« enchaîner des appels »** (LangChain) à
**« orchestrer un workflow d'agent »** (LangGraph).

---

## 5. Récapitulatif de la progression

| Étape | Branche | Outil | Ce qu'on gagne | La limite qui pousse à l'étape suivante |
|---|---|---|---|---|
| Agent maison | branche3 | SDK OpenAI | comprendre le function calling | trop de plomberie répétée |
| Agent LangChain | branche4 | `bind_tools` | code court, composable | reste une boucle **linéaire** |
| Agent LangGraph | branche5 | graphe d'états | branches, cycles, état, pause/reprise | (l'aboutissement pour workflows complexes) |

---

## 6. Quand utiliser quoi (règle simple)

- **Maison** : apprendre, ou micro-projet sans dépendance.
- **LangChain** : flux **linéaire** simple, on veut juste éviter la plomberie.
- **LangGraph** : flux **non linéaire** — branches, boucles maîtrisées, état
  riche, persistance, validation humaine, ou plusieurs agents.

> Règle du pouce : **si vous dessinez votre agent et que ça fait une ligne →
> LangChain suffit. Si ça fait un schéma avec des flèches qui reviennent →
> LangGraph.**

---

## 7. Exercice de réflexion

Avant de coder LangGraph (branche5), dessinez sur papier le graphe de cet agent :

> « Cherche une info sur le web ; **si** aucun résultat, reformule la requête et
> recherche une 2ᵉ fois ; **sinon** calcule si nécessaire, puis réponds. »

Repérez : les **nœuds**, les **arêtes conditionnelles** (« si aucun résultat »),
et la **boucle** (reformuler → rechercher). C'est exactement ce que LangGraph
permet d'exprimer proprement — et ce qu'une chaîne LangChain rend pénible.
