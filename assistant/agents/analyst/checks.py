"""
Anomaly detection and statistics — Agent 3: the Analyst
"""

from typing import Optional, List


SEUIL_DEVIATION_ATTENTION = 0.30   # 30 % deviation → WARNING
SEUIL_DEVIATION_ALERTE    = 0.60   # 60 % deviation → ALERT
SEUIL_MONTANT_ELEVE       = 3.0    # 3× the overall average


def compute_supplier_stats(historique: List[dict], fournisseur: Optional[str]) -> dict:
    """Historical statistics for a given supplier."""
    if not fournisseur:
        return {
            "nb_documents": 0,
            "montant_moyen": None,
            "montant_total": None,
            "montants": [],
        }

    nom = fournisseur.strip().lower()
    docs = [d for d in historique if (d.get("fournisseur") or "").strip().lower() == nom]
    montants = [d["montant"] for d in docs if d.get("montant") is not None]

    return {
        "nb_documents" : len(docs),
        "montant_moyen": round(sum(montants) / len(montants), 3) if montants else None,
        "montant_total": round(sum(montants), 3) if montants else None,
        "montants"     : [round(m, 3) for m in montants],
    }


def compute_global_stats(historique: List[dict]) -> dict:
    """Overall statistics on all the stored documents."""
    montants     = [d["montant"] for d in historique if d.get("montant") is not None]
    fournisseurs = {(d.get("fournisseur") or "").strip().lower() for d in historique if d.get("fournisseur")}
    doc_types    = {}
    for d in historique:
        t = d.get("doc_type", "inconnu")
        doc_types[t] = doc_types.get(t, 0) + 1

    return {
        "nb_documents_total"  : len(historique),
        "nb_fournisseurs"     : len(fournisseurs),
        "montant_total_base"  : round(sum(montants), 3) if montants else 0,
        "montant_moyen_global": round(sum(montants) / len(montants), 3) if montants else None,
        "repartition_types"   : doc_types,
    }


def detect_anomalies(
    montant_actuel : Optional[float],
    fournisseur    : Optional[str],
    stats_fournisseur: dict,
    stats_globales : dict,
) -> List[dict]:
    """Detects financial and behavioural anomalies."""
    anomalies: List[dict] = []

    # ── New supplier ──────────────────────────────────────────────────────────
    if fournisseur and stats_fournisseur.get("nb_documents", 0) == 0:
        anomalies.append({
            "type"   : "NOUVEAU_FOURNISSEUR",
            "niveau" : "ATTENTION",
            "message": f"First document stored for “{fournisseur}”",
        })

    # ── Amount deviating from the supplier average ────────────────────────────
    # Requires ≥ 2 historical documents: a single document is not a reliable reference (avoids self-comparison)
    if (montant_actuel and stats_fournisseur.get("montant_moyen")
            and stats_fournisseur.get("nb_documents", 0) >= 2):
        moyenne  = stats_fournisseur["montant_moyen"]
        ecart_r  = abs(montant_actuel - moyenne) / moyenne
        if ecart_r >= SEUIL_DEVIATION_ALERTE:
            direction = "above" if montant_actuel > moyenne else "below"
            anomalies.append({
                "type"          : "MONTANT_ANORMAL",
                "niveau"        : "ALERTE",
                "message"       : f"Amount {ecart_r:.0%} {direction} the supplier average ({moyenne:.3f} TND)",
                "montant_actuel": montant_actuel,
                "montant_moyen" : moyenne,
                "ecart_pct"     : round(ecart_r * 100, 1),
            })
        elif ecart_r >= SEUIL_DEVIATION_ATTENTION:
            direction = "above" if montant_actuel > moyenne else "below"
            anomalies.append({
                "type"          : "MONTANT_INHABITUEL",
                "niveau"        : "ATTENTION",
                "message"       : f"Amount {ecart_r:.0%} {direction} the supplier average ({moyenne:.3f} TND)",
                "montant_actuel": montant_actuel,
                "montant_moyen" : moyenne,
                "ecart_pct"     : round(ecart_r * 100, 1),
            })

    # ── Very high amount compared with the overall average ───────────────────
    if montant_actuel and stats_globales.get("montant_moyen_global"):
        moy_g = stats_globales["montant_moyen_global"]
        if montant_actuel > moy_g * SEUIL_MONTANT_ELEVE:
            anomalies.append({
                "type"   : "MONTANT_ELEVE",
                "niveau" : "ATTENTION",
                "message": f"Amount {SEUIL_MONTANT_ELEVE:.0f}× above the overall average ({moy_g:.3f} TND)",
            })

    return anomalies
