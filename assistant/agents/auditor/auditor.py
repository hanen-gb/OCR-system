"""
Agent 2 : L'Auditeur (Gouvernance & Conformité)

Reçoit le JSON complet de l'Agent 1 (complete_entities) + les entités de base du GLM,
et produit un rapport d'audit avec 5 vérifications :

  1. check_arithmetique_lignes  — QTE × PU_HT ≈ Total_HT par ligne
  2. validation_tva_globale     — Somme TVA lignes ≈ montant_tva extrait
  3. conformite_net_a_payer     — HT + TVA + Timbre ≈ Net à payer (TTC)
  4. alerte_doublon             — N° déjà vu en base PostgreSQL ?
  5. gouvernance                — Signature / Tampon présents ?

  → status_validite : "VALIDÉ" | "DOUBLON" | "SIGNATURE_MANQUANTE" |
                       "ERREUR_CALCUL" | "ERREUR_TVA" | "ERREUR_NET_A_PAYER"
"""

from agents.auditor.checks import (
    check_arithmetic_lines,
    validate_tva_globale,
    check_net_a_payer,
    check_governance,
)
from database import check_doublon_pg


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_str(d: dict, *keys) -> str | None:
    """Cherche la première clé non-nulle dans le dict."""
    for k in keys:
        v = d.get(k)
        if v is not None and str(v).strip():
            return str(v).strip()
    return None


def _get_num(d: dict, *keys) -> float | None:
    for k in keys:
        v = d.get(k)
        if v is not None:
            try:
                return float(v)
            except (TypeError, ValueError):
                pass
    return None


# ── Fonction principale ───────────────────────────────────────────────────────

def audit_document(
    complete_entities: dict,
    base_entities    : dict | None = None,
) -> dict:
    """
    Audite un document commercial.

    Paramètres :
      complete_entities : sortie de l'Agent 1 (merge de base + augmented + visual)
      base_entities     : entités extraites par le modèle GLM fine-tuné
                          (num_facture, montant_ttc, etc.) — peut être {} ou None

    Retourne un dict d'audit complet.
    """
    base     = base_entities or {}
    entities = complete_entities or {}

    doc_type = _get_str(entities, "_document_type") or "facture"
    is_traite = "lettre" in doc_type or "change" in doc_type

    # ── Résolution des champs clés selon le type de document ─────────────────
    if is_traite:
        doc_number  = _get_str(base, "num_lettre") or _get_str(entities, "num_lettre")
        fournisseur = _get_str(base, "tireur")      or _get_str(entities, "tireur")
        montant_ttc = _get_num(base, "montant")     or _get_num(entities, "montant")
        date_doc    = _get_str(base, "date_echeance")
    else:
        doc_number  = _get_str(base, "num_facture") or _get_str(entities, "num_facture")
        fournisseur = None
        if isinstance(base.get("fournisseur"), dict):
            fournisseur = base["fournisseur"].get("nom")
        fournisseur = fournisseur or _get_str(base, "fournisseur") or _get_str(entities, "fournisseur")
        montant_ttc = _get_num(base, "montant_ttc") or _get_num(entities, "net_a_payer")
        date_doc    = _get_str(base, "date_facture")

    articles     = entities.get("articles") or []
    montant_ht   = _get_num(entities, "montant_ht")
    montant_tva  = _get_num(entities, "montant_tva")
    timbre       = _get_num(entities, "timbre_fiscal")

    # ── 1. Détection de doublon ───────────────────────────────────────────────
    alerte_doublon = check_doublon_pg(doc_type, doc_number)

    # ── 2. Vérification arithmétique ligne par ligne ──────────────────────────
    check_lignes    = check_arithmetic_lines(articles)
    nb_erreurs      = sum(1 for c in check_lignes if c["status"] == "ERREUR")
    nb_incomplets   = sum(1 for c in check_lignes if c["status"] == "INCOMPLET")

    # ── 3. Validation TVA globale ─────────────────────────────────────────────
    validation_tva = validate_tva_globale(articles, montant_tva)

    # ── 4. Conformité Net à Payer ─────────────────────────────────────────────
    conformite_net = check_net_a_payer(montant_ht, montant_tva, timbre, montant_ttc)

    # ── 5. Gouvernance (signatures, tampons) ──────────────────────────────────
    gouvernance = check_governance(entities)

    # ── Statut final (priorité décroissante) ─────────────────────────────────
    if alerte_doublon["status"] == "DOUBLON":
        status = "DOUBLON"
    elif gouvernance["status"] == "MANQUANT" and not is_traite:
        # Pour les factures : signature manquante = avertissement, pas bloquant
        status = "SIGNATURE_MANQUANTE"
    elif gouvernance["status"] == "MANQUANT" and is_traite:
        # Pour les traites : signature manquante = bloquant
        status = "SIGNATURE_MANQUANTE"
    elif nb_erreurs > 0:
        status = "ERREUR_CALCUL"
    elif validation_tva.get("status") == "ERREUR":
        status = "ERREUR_TVA"
    elif conformite_net.get("status") == "ERREUR":
        status = "ERREUR_NET_A_PAYER"
    else:
        status = "VALIDÉ"

    # NB : l'enregistrement persistant se fait dans PostgreSQL via save_document()
    # (assistant/api/main.py), appelé après l'audit.

    # ── Rapport final ─────────────────────────────────────────────────────────
    return {
        "status_validite"           : status,
        "check_arithmetique_lignes" : check_lignes,
        "nb_articles"               : len(articles),
        "nb_erreurs_calcul"         : nb_erreurs,
        "nb_lignes_incompletes"     : nb_incomplets,
        "validation_tva_globale"    : validation_tva,
        "conformite_net_a_payer"    : conformite_net,
        "gouvernance"               : gouvernance,
        "alerte_doublon"            : alerte_doublon,
        "doc_type"                  : doc_type,
        "doc_number"                : doc_number,
        "fournisseur"               : fournisseur,
    }
