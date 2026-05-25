"""
Fonctions de détection d'anomalies et calcul statistique — Agent 3 : L'Analyste
"""

from typing import Optional, List


SEUIL_DEVIATION_ATTENTION = 0.30   # 30 % d'écart → ATTENTION
SEUIL_DEVIATION_ALERTE    = 0.60   # 60 % d'écart → ALERTE
SEUIL_MONTANT_ELEVE       = 3.0    # 3× la moyenne globale


def compute_supplier_stats(historique: List[dict], fournisseur: Optional[str]) -> dict:
    """Statistiques historiques pour un fournisseur donné."""
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
    """Statistiques globales sur l'ensemble des documents enregistrés."""
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
    """Détecte les anomalies financières et comportementales."""
    anomalies: List[dict] = []

    # ── Nouveau fournisseur ───────────────────────────────────────────────────
    if fournisseur and stats_fournisseur.get("nb_documents", 0) == 0:
        anomalies.append({
            "type"   : "NOUVEAU_FOURNISSEUR",
            "niveau" : "ATTENTION",
            "message": f"Premier document enregistré pour « {fournisseur} »",
        })

    # ── Montant déviant vs moyenne fournisseur ───────────────────────────────
    if montant_actuel and stats_fournisseur.get("montant_moyen"):
        moyenne  = stats_fournisseur["montant_moyen"]
        ecart_r  = abs(montant_actuel - moyenne) / moyenne
        if ecart_r >= SEUIL_DEVIATION_ALERTE:
            direction = "supérieur" if montant_actuel > moyenne else "inférieur"
            anomalies.append({
                "type"          : "MONTANT_ANORMAL",
                "niveau"        : "ALERTE",
                "message"       : f"Montant {direction} de {ecart_r:.0%} à la moyenne fournisseur ({moyenne:.3f} DT)",
                "montant_actuel": montant_actuel,
                "montant_moyen" : moyenne,
                "ecart_pct"     : round(ecart_r * 100, 1),
            })
        elif ecart_r >= SEUIL_DEVIATION_ATTENTION:
            direction = "supérieur" if montant_actuel > moyenne else "inférieur"
            anomalies.append({
                "type"          : "MONTANT_INHABITUEL",
                "niveau"        : "ATTENTION",
                "message"       : f"Montant {direction} de {ecart_r:.0%} à la moyenne fournisseur ({moyenne:.3f} DT)",
                "montant_actuel": montant_actuel,
                "montant_moyen" : moyenne,
                "ecart_pct"     : round(ecart_r * 100, 1),
            })

    # ── Montant très élevé vs moyenne globale ────────────────────────────────
    if montant_actuel and stats_globales.get("montant_moyen_global"):
        moy_g = stats_globales["montant_moyen_global"]
        if montant_actuel > moy_g * SEUIL_MONTANT_ELEVE:
            anomalies.append({
                "type"   : "MONTANT_ELEVE",
                "niveau" : "ATTENTION",
                "message": f"Montant {SEUIL_MONTANT_ELEVE:.0f}× supérieur à la moyenne globale ({moy_g:.3f} DT)",
            })

    return anomalies
