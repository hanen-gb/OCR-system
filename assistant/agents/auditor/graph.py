"""
Sous-graphe LangGraph — Agent 2 : L'Auditeur

Flux séquentiel :
    START → prepare
              ↓
           arithmetic   ← QTE × PU ≈ Total_HT par ligne
              ↓
            tva          ← Σ TVA lignes ≈ montant_tva global
              ↓
            net          ← HT + TVA + Timbre ≈ Net à payer
              ↓
           doublon       ← SQLite : N° déjà vu en base ?
              ↓
          gouvernance    ← Signatures, tampons, aval
              ↓
           verdict       ← Status final
              ↓
             END
"""

from langgraph.graph import StateGraph, START, END

from state import AuditorState
from agents.auditor.checks import (
    check_arithmetic_lines,
    validate_tva_globale,
    check_net_a_payer,
    check_governance,
)
from agents.auditor.db import check_doublon, register_document


# ── Helpers ───────────────────────────────────────────────────────────────────

def _str(d: dict, *keys) -> str | None:
    for k in keys:
        v = d.get(k)
        if v is not None and str(v).strip():
            return str(v).strip()
    return None


def _num(d: dict, *keys) -> float | None:
    for k in keys:
        v = d.get(k)
        if v is not None:
            try:
                return float(v)
            except (TypeError, ValueError):
                pass
    return None


# ── Nœuds ─────────────────────────────────────────────────────────────────────

def prepare_node(state: AuditorState) -> dict:
    """Résout doc_type, doc_number, fournisseur, montant_ttc depuis les entités."""
    entities = state.get("complete_entities") or {}
    base     = state.get("base_entities") or {}

    doc_type = _str(entities, "_document_type") or "facture"
    is_traite = "lettre" in doc_type or "change" in doc_type

    if is_traite:
        doc_number  = _str(base, "num_lettre")  or _str(entities, "num_lettre")
        fournisseur = _str(base, "tireur")       or _str(entities, "tireur")
        montant_ttc = _num(base, "montant")      or _num(entities, "montant")
        date_doc    = _str(base, "date_echeance")
    else:
        doc_number  = _str(base, "num_facture")  or _str(entities, "num_facture")
        fournisseur = None
        if isinstance(base.get("fournisseur"), dict):
            fournisseur = base["fournisseur"].get("nom")
        fournisseur = fournisseur or _str(base, "fournisseur") or _str(entities, "fournisseur")
        montant_ttc = _num(base, "montant_ttc")  or _num(entities, "net_a_payer")
        date_doc    = _str(base, "date_facture")

    print(f"[AUDITEUR] type={doc_type} | num={doc_number} | ttc={montant_ttc}")
    return {
        "doc_type"   : doc_type,
        "doc_number" : doc_number,
        "fournisseur": fournisseur,
        "montant_ttc": montant_ttc,
        "date_doc"   : date_doc,
    }


def arithmetic_node(state: AuditorState) -> dict:
    """Vérifie QTE × PU_HT ≈ Total_HT pour chaque ligne d'article."""
    articles = (state.get("complete_entities") or {}).get("articles") or []
    result   = check_arithmetic_lines(articles)
    nb_err   = sum(1 for r in result if r["status"] == "ERREUR")
    print(f"[AUDITEUR] Arithmétique : {len(result)} lignes, {nb_err} erreurs")
    return {"check_arithmetique": result}


def tva_node(state: AuditorState) -> dict:
    """Vérifie Σ TVA lignes ≈ montant_tva global."""
    entities    = state.get("complete_entities") or {}
    articles    = entities.get("articles") or []
    montant_tva = _num(entities, "montant_tva")
    result      = validate_tva_globale(articles, montant_tva)
    print(f"[AUDITEUR] TVA : {result.get('status')} (écart={result.get('ecart')})")
    return {"check_tva": result}


def net_node(state: AuditorState) -> dict:
    """Vérifie HT + TVA + Timbre ≈ net_a_payer (TTC)."""
    entities = state.get("complete_entities") or {}
    result   = check_net_a_payer(
        montant_ht    = _num(entities, "montant_ht"),
        montant_tva   = _num(entities, "montant_tva"),
        timbre_fiscal = _num(entities, "timbre_fiscal"),
        net_extrait   = state.get("montant_ttc"),
    )
    print(f"[AUDITEUR] Net à payer : {result.get('status')} (écart={result.get('ecart')})")
    return {"check_net": result}


def doublon_node(state: AuditorState) -> dict:
    """Consulte la base SQLite pour détecter un doublon."""
    result = check_doublon(state.get("doc_type") or "facture", state.get("doc_number"))
    print(f"[AUDITEUR] Doublon : {result.get('status')} ({state.get('doc_number')})")
    return {"check_doublon": result}


def gouvernance_node(state: AuditorState) -> dict:
    """Vérifie les champs de gouvernance (signatures, tampons, aval)."""
    entities = state.get("complete_entities") or {}
    result   = check_governance(entities)
    print(f"[AUDITEUR] Gouvernance : {result.get('status')} — manquants={result.get('champs_manquants')}")
    return {"check_gouvernance": result}


def verdict_node(state: AuditorState) -> dict:
    """Calcule le statut final et enregistre le document si nouveau."""
    doublon     = state.get("check_doublon") or {}
    gouvernance = state.get("check_gouvernance") or {}
    arithmetique= state.get("check_arithmetique") or []
    tva         = state.get("check_tva") or {}
    net         = state.get("check_net") or {}

    nb_erreurs_calcul = sum(1 for r in arithmetique if r.get("status") == "ERREUR")

    if doublon.get("status") == "DOUBLON":
        status = "DOUBLON"
    elif gouvernance.get("status") == "MANQUANT":
        status = "SIGNATURE_MANQUANTE"
    elif nb_erreurs_calcul > 0:
        status = "ERREUR_CALCUL"
    elif tva.get("status") == "ERREUR":
        status = "ERREUR_TVA"
    elif net.get("status") == "ERREUR":
        status = "ERREUR_NET_A_PAYER"
    else:
        status = "VALIDÉ"

    # Enregistre en base si nouveau document
    if doublon.get("status") == "NOUVEAU" and state.get("doc_number"):
        register_document(
            doc_type    = state.get("doc_type") or "facture",
            doc_number  = state["doc_number"],
            fournisseur = state.get("fournisseur"),
            montant     = state.get("montant_ttc"),
            date_doc    = state.get("date_doc"),
        )

    articles = (state.get("complete_entities") or {}).get("articles") or []

    rapport = {
        "status_validite"           : status,
        "doc_type"                  : state.get("doc_type"),
        "doc_number"                : state.get("doc_number"),
        "fournisseur"               : state.get("fournisseur"),
        "nb_articles"               : len(articles),
        "nb_erreurs_calcul"         : nb_erreurs_calcul,
        "nb_lignes_incompletes"     : sum(1 for r in arithmetique if r.get("status") == "INCOMPLET"),
        "check_arithmetique_lignes" : arithmetique,
        "validation_tva_globale"    : tva,
        "conformite_net_a_payer"    : net,
        "gouvernance"               : gouvernance,
        "alerte_doublon"            : doublon,
    }

    print(f"[AUDITEUR] Verdict final : {status}")
    return {"status_validite": status, "audit_report": rapport}


# ── Graphe ────────────────────────────────────────────────────────────────────

def build_auditor_graph():
    builder = StateGraph(AuditorState)

    builder.add_node("prepare",     prepare_node)
    builder.add_node("arithmetic",  arithmetic_node)
    builder.add_node("tva",         tva_node)
    builder.add_node("net",         net_node)
    builder.add_node("doublon",     doublon_node)
    builder.add_node("gouvernance", gouvernance_node)
    builder.add_node("verdict",     verdict_node)

    builder.add_edge(START,        "prepare")
    builder.add_edge("prepare",    "arithmetic")
    builder.add_edge("arithmetic", "tva")
    builder.add_edge("tva",        "net")
    builder.add_edge("net",        "doublon")
    builder.add_edge("doublon",    "gouvernance")
    builder.add_edge("gouvernance","verdict")
    builder.add_edge("verdict",    END)

    return builder.compile()


auditor_graph = build_auditor_graph()
