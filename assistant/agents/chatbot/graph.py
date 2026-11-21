"""
LangGraph sub-graph — Agent 4: the Chatbot

Flux :
    START → understand_intent
                ↓
            query_db         ← Uniquement si intent = "base_donnees"
                ↓
            generate_response
                ↓
              END

The chatbot has access to the context of the current document:
  - complete_entities  (entities extracted by Agent 1)
  - audit_report       (Agent 2 results)
  - analyst_report     (analyse Agent 3)
  - db_context         (recent documents from the database)
  - messages           (historique de conversation LangGraph)
"""

import json
import os
from typing import Literal

from langgraph.graph import StateGraph, START, END
from langchain_core.messages import AIMessage, SystemMessage

from state import ChatbotState


GROQ_BASE_URL      = "https://api.groq.com/openai/v1"
CHATBOT_MODEL      = "llama-3.3-70b-versatile"   # rapide + multilingue
CHATBOT_MODEL_ALT  = "llama3-groq-70b-8192-tool-use-preview"

SYSTEM_PROMPT = """Tu es ODSINET Assistant — un assistant IA expert en documents commerciaux tunisiens.

Tu accompagnes les utilisateurs dans l'analyse de leurs factures et lettres de change via le système OCR multi-agent ODSINET.

TES CAPACITÉS :
✅ Répondre aux questions sur le document analysé (entités, montants, fournisseur, articles)
✅ Expliquer les résultats de l'audit (conformité, TVA, arithmétique, doublons, gouvernance)
✅ Analyser les alertes et anomalies détectées
✅ Expliquer le fonctionnement du pipeline multi-agent (GLM → Extracteur → Auditeur → Analyste)
✅ Guider la correction manuelle des entités (HITL)
✅ Donner des recommandations basées sur l'historique

TES RÈGLES :
- Réponds en français par défaut (ou dans la langue de l'utilisateur)
- Sois concis : 2-4 phrases sauf si l'utilisateur demande plus de détails
- Si une information n'est pas dans le contexte : dis clairement que tu ne sais pas
- Pour les montants tunisiens : utilise la notation DT avec 3 décimales (ex: 1.234,567 DT)
- Ne génère jamais de données fictives
"""


def _build_context_block(
    entities : dict,
    audit    : dict,
    analyst  : dict,
    db_ctx   : list,
) -> str:
    """Builds the context block injected into the system prompt."""
    parts = []

    if entities:
        doc_type = entities.get("_document_type", "document")
        nb_art   = len(entities.get("articles", []))
        resume   = {k: v for k, v in entities.items()
                    if k not in ("articles",) and v is not None}
        parts.append(
            f"📄 DOCUMENT ANALYSÉ ({doc_type}, {nb_art} article(s)) :\n"
            + json.dumps(resume, ensure_ascii=False, indent=2)[:2000]
        )
        if nb_art:
            parts.append(
                f"🛒 ARTICLES ({nb_art} lignes) :\n"
                + json.dumps(entities["articles"], ensure_ascii=False, indent=2)[:1500]
            )

    if audit:
        status = audit.get("status_validite", "—")
        parts.append(
            f"🛡️ AUDIT — Statut : {status}\n"
            + json.dumps({k: v for k, v in audit.items() if k != "check_arithmetique_lignes"},
                         ensure_ascii=False, indent=2)[:1200]
        )

    if analyst:
        alert = analyst.get("alert_level", "NORMAL")
        insights = analyst.get("insights", "")
        anomalies = analyst.get("anomalies", [])
        parts.append(
            f"📊 ANALYSE — Alerte : {alert}\n"
            f"Insights : {insights}\n"
            f"Anomalies ({len(anomalies)}) : {json.dumps(anomalies, ensure_ascii=False)[:600]}"
        )

    if db_ctx:
        parts.append(f"🗄️ BASE DE DONNÉES : {len(db_ctx)} documents récents enregistrés")

    return "\n\n".join(parts)


# ── Nœuds ─────────────────────────────────────────────────────────────────────

def understand_intent_node(state: ChatbotState) -> dict:
    """Classifies the intent to decide whether a database query is needed."""
    messages = state.get("messages") or []
    if not messages:
        return {"intent": "general"}

    last_msg = str(messages[-1].content).lower()
    db_keywords = ["combien", "historique", "tous les", "liste", "base", "enregistrés",
                   "documents", "fournisseurs", "total", "statistique"]
    intent = "base_donnees" if any(k in last_msg for k in db_keywords) else "document"
    print(f"[CHATBOT] Intent detected: {intent}")
    return {"intent": intent}


def query_db_node(state: ChatbotState) -> dict:
    """Loads additional data from PostgreSQL when needed."""
    from database import get_documents_pg
    db_ctx = get_documents_pg(limit=50)
    print(f"[CHATBOT] Database queried: {len(db_ctx)} documents")
    return {"db_context": db_ctx}


def generate_response_node(state: ChatbotState) -> dict:
    """Generates the chatbot answer with an LLM (Groq → Gemini fallback)."""
    messages    = list(state.get("messages") or [])
    entities    = state.get("context_entities") or {}
    audit       = state.get("context_audit") or {}
    analyst     = state.get("context_analyst") or {}
    db_ctx      = state.get("db_context") or []

    context_block = _build_context_block(entities, audit, analyst, db_ctx)
    system_content = SYSTEM_PROMPT
    if context_block:
        system_content += f"\n\n=== CONTEXTE DU DOCUMENT EN COURS ===\n{context_block}"

    llm_messages = [SystemMessage(content=system_content)] + messages

    # ── Groq ─────────────────────────────────────────────────────────────────
    groq_key = os.getenv("GROQ_API_KEY")
    reply    = None

    if groq_key:
        for model in [CHATBOT_MODEL, CHATBOT_MODEL_ALT]:
            try:
                from langchain_openai import ChatOpenAI
                llm = ChatOpenAI(
                    model       = model,
                    api_key     = groq_key,
                    base_url    = GROQ_BASE_URL,
                    temperature = 0.4,
                    max_tokens  = 1024,
                )
                reply = llm.invoke(llm_messages).content.strip()
                print(f"[CHATBOT] Answer from {model} ({len(reply)} chars)")
                break
            except Exception as e:
                print(f"[CHATBOT] {model} → {str(e)[:80]}")
                continue

    # ── Fallback Gemini ───────────────────────────────────────────────────────
    if not reply:
        google_key = os.getenv("GOOGLE_API_KEY")
        if google_key:
            for gem_model in ["gemini-2.0-flash", "gemini-1.5-flash"]:
                try:
                    from langchain_google_genai import ChatGoogleGenerativeAI
                    llm = ChatGoogleGenerativeAI(
                        model          = gem_model,
                        google_api_key = google_key,
                        temperature    = 0.4,
                        max_tokens     = 1024,
                    )
                    reply = llm.invoke(llm_messages).content.strip()
                    print(f"[CHATBOT] Answer from {gem_model} (Gemini fallback)")
                    break
                except Exception as e:
                    print(f"[CHATBOT] {gem_model} → {str(e)[:80]}")
                    continue

    if not reply:
        reply = ("Sorry, I cannot answer right now — "
                 "no LLM is available (check the API keys in .env).")

    return {
        "messages": [AIMessage(content=reply)],
        "response": reply,
    }


# ── Routage ───────────────────────────────────────────────────────────────────

def route_intent(state: ChatbotState) -> Literal["query_db", "generate_response"]:
    return "query_db" if state.get("intent") == "base_donnees" else "generate_response"


# ── Graphe ────────────────────────────────────────────────────────────────────

def build_chatbot_graph():
    builder = StateGraph(ChatbotState)

    builder.add_node("understand_intent",  understand_intent_node)
    builder.add_node("query_db",           query_db_node)
    builder.add_node("generate_response",  generate_response_node)

    builder.add_edge(START, "understand_intent")
    builder.add_conditional_edges(
        "understand_intent",
        route_intent,
        {"query_db": "query_db", "generate_response": "generate_response"},
    )
    builder.add_edge("query_db",          "generate_response")
    builder.add_edge("generate_response", END)

    return builder.compile()


chatbot_graph = build_chatbot_graph()
