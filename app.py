"""Clone de Claude (façon Opus) propulsé par les GPU NVIDIA.

Interface de chat Streamlit branchée sur l'endpoint d'inférence hébergé de
NVIDIA (build.nvidia.com / NIM), compatible OpenAI. Streaming, multi-tours,
sélecteur de modèles dynamique et affichage de la chaîne de raisonnement.

Lancement :  streamlit run app.py
"""

from __future__ import annotations

import os

import streamlit as st
from dotenv import load_dotenv

from nvidia_client import (
    DEFAULT_MODEL,
    FALLBACK_MODELS,
    StreamDelta,
    get_client,
    list_models,
    stream_chat,
)
from web_search import (
    DEFAULT_SEARXNG_URL,
    augment_prompt,
    build_context,
    search,
)
from tools import run_agent

load_dotenv()

st.set_page_config(page_title="Clone Opus · NVIDIA NIM", page_icon="🟢", layout="centered")

DEFAULT_SYSTEM_PROMPT = (
    "Tu es un assistant IA expert, clair et rigoureux. "
    "Tu réponds en français, de façon structurée et concise."
)


def init_state() -> None:
    if "messages" not in st.session_state:
        st.session_state.messages = []  # liste de {role, content, reasoning?}
    if "models" not in st.session_state:
        st.session_state.models = []


def resolve_api_key(sidebar_key: str) -> str:
    return (sidebar_key or os.environ.get("NVIDIA_API_KEY") or "").strip()


def render_sidebar() -> dict:
    with st.sidebar:
        st.header("Configuration")

        env_key = os.environ.get("NVIDIA_API_KEY", "")
        api_key_input = st.text_input(
            "Clé API NVIDIA (nvapi-...)",
            value="",
            type="password",
            placeholder="nvapi-..." if not env_key else "(chargée depuis .env)",
            help="Obtiens-la sur build.nvidia.com → Get API Key. Jamais commitée.",
        )
        api_key = resolve_api_key(api_key_input)

        if api_key:
            st.success("Clé détectée.")
        else:
            st.warning("Aucune clé : saisis-la ci-dessus ou place-la dans .env.")

        st.divider()

        if api_key and not st.session_state.models:
            with st.spinner("Chargement du catalogue de modèles..."):
                st.session_state.models = list_models(get_client(api_key))
        models = st.session_state.models or FALLBACK_MODELS

        default_index = models.index(DEFAULT_MODEL) if DEFAULT_MODEL in models else 0
        model = st.selectbox("Modèle", models, index=default_index)

        col_a, col_b = st.columns(2)
        with col_a:
            if st.button("Rafraîchir les modèles", use_container_width=True):
                st.session_state.models = []
                st.rerun()
        with col_b:
            if st.button("Nouvelle conversation", use_container_width=True):
                st.session_state.messages = []
                st.rerun()

        st.divider()

        system_prompt = st.text_area(
            "System prompt", value=DEFAULT_SYSTEM_PROMPT, height=120
        )
        temperature = st.slider("Température", 0.0, 1.5, 0.7, 0.05)
        top_p = st.slider("Top-p", 0.1, 1.0, 0.95, 0.05)
        max_tokens = st.slider("Tokens max", 256, 8192, 2048, 256)

        st.divider()
        st.subheader("Mode outils (agent)")
        agent_enabled = st.toggle(
            "Activer le mode agent (function calling)",
            value=False,
            help=(
                "Le MODÈLE décide lui-même d'appeler des outils (recherche web, "
                "calculatrice). Prend le pas sur la recherche web manuelle."
            ),
        )

        st.divider()
        st.subheader("Recherche web (SearXNG)")
        web_enabled = st.toggle(
            "Activer la recherche web",
            value=False,
            help="Interroge SearXNG avant de répondre pour des infos à jour (RAG web manuel).",
        )
        searxng_url = st.text_input(
            "URL SearXNG",
            value=os.environ.get("SEARXNG_URL", DEFAULT_SEARXNG_URL),
            help="Instance SearXNG avec le format JSON activé. Voir docker-compose.yml.",
        )
        web_max_results = st.slider("Nb de résultats", 1, 10, 5)

        st.caption("Endpoint : integrate.api.nvidia.com/v1 · Palier gratuit ~40 req/min")

    return {
        "api_key": api_key,
        "model": model,
        "system_prompt": system_prompt,
        "temperature": temperature,
        "top_p": top_p,
        "max_tokens": max_tokens,
        "agent_enabled": agent_enabled,
        "web_enabled": web_enabled,
        "searxng_url": searxng_url.strip(),
        "web_max_results": web_max_results,
    }


def render_sources(sources: list[dict]) -> None:
    with st.expander(f"Sources web ({len(sources)})"):
        for i, s in enumerate(sources, start=1):
            st.markdown(f"[{i}] [{s['title'] or s['url']}]({s['url']})")


def render_tool_steps(steps: list[dict]) -> None:
    with st.expander(f"Outils utilisés ({len(steps)})"):
        for i, s in enumerate(steps, start=1):
            st.markdown(f"**{i}. {s['name']}** — `{s['arguments']}`")


def render_history() -> None:
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            if msg["role"] == "assistant" and msg.get("reasoning"):
                with st.expander("Réflexion du modèle"):
                    st.markdown(msg["reasoning"])
            if msg["role"] == "assistant" and msg.get("tool_steps"):
                render_tool_steps(msg["tool_steps"])
            st.markdown(msg["content"])
            if msg["role"] == "assistant" and msg.get("sources"):
                render_sources(msg["sources"])


def build_api_messages(system_prompt: str, last_user_override: str | None = None) -> list[dict]:
    """Construit les messages pour l'API.

    `last_user_override` remplace le contenu du dernier message utilisateur
    (utilisé pour injecter le contexte de recherche web sans polluer l'historique
    affiché).
    """
    api_messages = [{"role": "system", "content": system_prompt}]
    msgs = list(st.session_state.messages)
    for idx, msg in enumerate(msgs):
        content = msg["content"]
        is_last_user = msg["role"] == "user" and idx == len(msgs) - 1
        if is_last_user and last_user_override is not None:
            content = last_user_override
        api_messages.append({"role": msg["role"], "content": content})
    return api_messages


def run_web_search(query: str, config: dict) -> tuple[str, list[dict]]:
    """Lance la recherche web ; retourne (prompt enrichi, sources).

    En cas d'échec, retourne le prompt original et une liste vide.
    """
    try:
        results = search(
            query,
            base_url=config["searxng_url"],
            max_results=config["web_max_results"],
        )
    except Exception as error:  # noqa: BLE001
        st.warning(
            f"Recherche web indisponible ({error}). Réponse sans contexte web. "
            "Vérifie que SearXNG tourne (docker compose up -d)."
        )
        return query, []

    if not results:
        st.info("Aucun résultat web trouvé pour cette requête.")
        return query, []

    context = build_context(results)
    augmented = augment_prompt(query, context)
    sources = [{"title": r.title, "url": r.url} for r in results]
    return augmented, sources


def main() -> None:
    init_state()
    config = render_sidebar()

    st.title("Clone Opus — propulsé par NVIDIA")
    st.caption(
        "Chat compatible OpenAI sur les GPU NVIDIA. Pas de modèle local, "
        "pas de VRAM, pas de stockage."
    )

    render_history()

    prompt = st.chat_input("Pose ta question...")
    if not prompt:
        return

    if not config["api_key"]:
        st.error("Ajoute ta clé NVIDIA (nvapi-...) dans la barre latérale ou un fichier .env.")
        return

    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    client = get_client(config["api_key"])

    # MODE AGENT : le modèle décide lui-même d'appeler des outils.
    if config["agent_enabled"]:
        _run_agent_turn(client, config)
        return

    # MODE CLASSIQUE (avec recherche web manuelle optionnelle).
    sources: list[dict] = []
    last_user_override: str | None = None
    if config["web_enabled"]:
        with st.spinner("Recherche web en cours..."):
            last_user_override, sources = run_web_search(prompt, config)

    api_messages = build_api_messages(config["system_prompt"], last_user_override)

    with st.chat_message("assistant"):
        if sources:
            render_sources(sources)
        reasoning_box = st.expander("Réflexion du modèle", expanded=False)
        reasoning_placeholder = reasoning_box.empty()
        answer_placeholder = st.empty()

        reasoning_text = ""
        answer_text = ""

        try:
            for delta in stream_chat(
                client,
                config["model"],
                api_messages,
                temperature=config["temperature"],
                top_p=config["top_p"],
                max_tokens=config["max_tokens"],
            ):
                if delta.reasoning:
                    reasoning_text += delta.reasoning
                    reasoning_placeholder.markdown(reasoning_text)
                if delta.content:
                    answer_text += delta.content
                    answer_placeholder.markdown(answer_text + "▌")
            answer_placeholder.markdown(answer_text)
        except Exception as error:  # noqa: BLE001
            message = str(error)
            if "429" in message or "rate limit" in message.lower():
                st.error("Limite de débit atteinte (429). Patiente un instant puis réessaie.")
            elif "401" in message or "403" in message:
                st.error("Clé refusée (401/403). Vérifie ta clé nvapi-.")
            else:
                st.error(f"Erreur lors de l'appel : {message}")
            st.session_state.messages.pop()  # on retire le tour utilisateur échoué
            return

    st.session_state.messages.append(
        {
            "role": "assistant",
            "content": answer_text,
            "reasoning": reasoning_text,
            "sources": sources,
        }
    )


def _run_agent_turn(client, config: dict) -> None:
    """Exécute un tour en mode agent (function calling) et l'affiche."""
    api_messages = build_api_messages(config["system_prompt"])
    with st.chat_message("assistant"):
        status = st.status("Agent : réflexion et appels d'outils...", expanded=True)

        def on_tool(name: str, args: dict) -> None:
            status.write(f"Appel outil **{name}** : `{args}`")

        try:
            result = run_agent(
                client,
                config["model"],
                api_messages,
                searxng_url=config["searxng_url"],
                temperature=config["temperature"],
                top_p=config["top_p"],
                max_tokens=config["max_tokens"],
                on_tool=on_tool,
            )
        except Exception as error:  # noqa: BLE001
            status.update(label="Erreur", state="error")
            st.error(f"Erreur en mode agent : {error}")
            st.session_state.messages.pop()
            return

        label = (
            f"Agent : {len(result.steps)} appel(s) d'outil"
            if result.steps
            else "Agent : aucune action nécessaire"
        )
        status.update(label=label, state="complete", expanded=False)

        if result.reasoning:
            with st.expander("Réflexion du modèle"):
                st.markdown(result.reasoning)
        st.markdown(result.content)

    st.session_state.messages.append(
        {
            "role": "assistant",
            "content": result.content,
            "reasoning": result.reasoning,
            "tool_steps": result.steps,
        }
    )


if __name__ == "__main__":
    main()
