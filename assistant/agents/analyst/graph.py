"""
Sous-graphe LangGraph — Agent 3 : L'Analyste

Flux séquentiel :
    START → load_history
              ↓
           compute_stats   ← Stats historiques (fournisseur + global)
              ↓
         detect_anomalies  ← Montant déviant, nouveau fournisseur, montant élevé
              ↓
         generate_insights ← LLM : commentaire analytique 3-4 phrases
              ↓
            verdict         ← Niveau alerte global + rapport final
              ↓
             END
"""

import json
import os

from langgraph.graph import StateGraph, START, END

from state import AnalystState
from agents.auditor.db import list_documents
from agents.analyst.checks import (
    compute_supplier_stats,
    compute_global_stats,
    detect_anomalies,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _resolve_fournisseur(audit: dict, entities: dict) -> str | None:
    f = audit.get("fournisseur") or entities.get("fournisseur")
    if isinstance(f, dict):
        f = f.get("nom")
    return str(f).strip() if f else None


def _resolve_montant(audit: dict, entities: dict) -> float | None:
    for src in (audit, entities):
        for k in ("montant_ttc", "net_a_payer", "montant", "montant_total"):
            v = src.get(k)
            if v is not None:
                try:
                    return float(v)
                except (TypeError, ValueError):
                    pass
    return None


# ── Nœuds ─────────────────────────────────────────────────────────────────────

def load_history_node(state: AnalystState) -> dict:
    """Charge les 500 derniers documents depuis SQLite."""
    historique = list_documents(limit=500)
    print(f"[ANALYSTE] Historique chargé : {len(historique)} documents")
    return {"historique": historique}


def compute_stats_node(state: AnalystState) -> dict:
    """Calcule les statistiques par fournisseur et globales."""
    historique  = state.get("historique") or []
    audit       = state.get("audit_report") or {}
    entities    = state.get("complete_entities") or {}
    fournisseur = _resolve_fournisseur(audit, entities)

    stats_f = compute_supplier_stats(historique, fournisseur)
    stats_g = compute_global_stats(historique)

    print(f"[ANALYSTE] Stats '{fournisseur}' : {stats_f['nb_documents']} docs, "
          f"moy={stats_f['montant_moyen']} DT")
    return {
        "stats_fournisseur": stats_f,
        "stats_globales"   : stats_g,
    }


def detect_anomalies_node(state: AnalystState) -> dict:
    """Détecte les anomalies du document courant."""
    audit    = state.get("audit_report") or {}
    entities = state.get("complete_entities") or {}

    montant     = _resolve_montant(audit, entities)
    fournisseur = _resolve_fournisseur(audit, entities)

    anomalies = detect_anomalies(
        montant_actuel    = montant,
        fournisseur       = fournisseur,
        stats_fournisseur = state.get("stats_fournisseur") or {},
        stats_globales    = state.get("stats_globales") or {},
    )

    nb_a = sum(1 for a in anomalies if a.get("niveau") == "ALERTE")
    nb_w = sum(1 for a in anomalies if a.get("niveau") == "ATTENTION")
    print(f"[ANALYSTE] Anomalies : {nb_a} ALERTE, {nb_w} ATTENTION")
    return {"anomalies": anomalies}


def generate_insights_node(state: AnalystState) -> dict:
    """Génère un commentaire analytique via LLM (Groq → HF → Gemini)."""
    audit     = state.get("audit_report") or {}
    anomalies = state.get("anomalies") or []
    stats_f   = state.get("stats_fournisseur") or {}
    stats_g   = state.get("stats_globales") or {}
    entities  = state.get("complete_entities") or {}

    fournisseur = _resolve_fournisseur(audit, entities) or "inconnu"
    doc_number  = audit.get("doc_number", "N/A")
    doc_type    = audit.get("doc_type", "document")
    status      = audit.get("status_validite", "—")
    montant     = _resolve_montant(audit, entities)

    contexte = (
        f"Type : {doc_type} | N° : {doc_number} | Fournisseur : {fournisseur}\n"
        f"Montant TTC : {montant} DT | Statut audit : {status}\n"
        f"Historique fournisseur : {stats_f.get('nb_documents', 0)} documents, "
        f"moyenne {stats_f.get('montant_moyen')} DT, total {stats_f.get('montant_total')} DT\n"
        f"Base globale : {stats_g.get('nb_documents_total', 0)} documents, "
        f"{stats_g.get('nb_fournisseurs', 0)} fournisseurs\n"
        f"Anomalies : {json.dumps(anomalies, ensure_ascii=False)}"
    )

    prompt = f"""Tu es un analyste financier spécialisé en documents commerciaux tunisiens.

Voici le contexte d'un document traité par le système OCR multi-agent :
{contexte}

Rédige un commentaire analytique professionnel en 3-4 phrases maximum :
- Évalue la conformité du document et l'historique du fournisseur
- Signale les points d'attention ou alertes détectés
- Donne une recommandation concrète (valider, investiguer, rejeter)
- Sois factuel, concis, sans répéter les chiffres déjà affichés

Commentaire :"""

    try:
        from agents.extractor.tools import _call_llm
        insights = _call_llm(prompt).strip()[:1000]
    except Exception as e:
        insights = f"Analyse indisponible — {str(e)[:120]}"

    print(f"[ANALYSTE] Insights : {insights[:80]}…")
    return {"insights_text": insights}


def verdict_node(state: AnalystState) -> dict:
    """Compile le rapport final et détermine le niveau d'alerte global."""
    anomalies = state.get("anomalies") or []

    if any(a.get("niveau") == "ALERTE" for a in anomalies):
        alert_level = "ALERTE"
    elif any(a.get("niveau") == "ATTENTION" for a in anomalies):
        alert_level = "ATTENTION"
    else:
        alert_level = "NORMAL"

    rapport = {
        "alert_level"      : alert_level,
        "nb_anomalies"     : len(anomalies),
        "anomalies"        : anomalies,
        "stats_fournisseur": state.get("stats_fournisseur"),
        "stats_globales"   : state.get("stats_globales"),
        "insights"         : state.get("insights_text"),
    }

    print(f"[ANALYSTE] Verdict final : {alert_level} ({len(anomalies)} anomalie(s))")
    return {"alert_level": alert_level, "analyst_report": rapport}


# ── Graphe ────────────────────────────────────────────────────────────────────

def build_analyst_graph():
    builder = StateGraph(AnalystState)

    builder.add_node("load_history",      load_history_node)
    builder.add_node("compute_stats",     compute_stats_node)
    builder.add_node("detect_anomalies",  detect_anomalies_node)
    builder.add_node("generate_insights", generate_insights_node)
    builder.add_node("verdict",           verdict_node)

    builder.add_edge(START,              "load_history")
    builder.add_edge("load_history",     "compute_stats")
    builder.add_edge("compute_stats",    "detect_anomalies")
    builder.add_edge("detect_anomalies", "generate_insights")
    builder.add_edge("generate_insights","verdict")
    builder.add_edge("verdict",          END)

    return builder.compile()


analyst_graph = build_analyst_graph()
