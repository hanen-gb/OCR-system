"""
Vérifications arithmétiques et de conformité — Agent 2 : L'Auditeur.

Toutes les fonctions sont pures (pas d'I/O, pas de LLM).
Tolérance : 0.005 DT (5 millimes) pour absorber les arrondis de millimes.
"""

TOLERANCE = 0.005  # 5 millimes


def _parse_tva_rate(tva_str) -> float | None:
    """'19%' → 0.19 · '7%' → 0.07 · None/0/'exonéré' → 0.0"""
    if tva_str is None:
        return 0.0
    s = str(tva_str).strip().replace("%", "").replace(",", ".")
    try:
        return float(s) / 100
    except ValueError:
        return 0.0


def check_arithmetic_lines(articles: list) -> list:
    """
    Pour chaque article : vérifie si QTE × PU_HT ≈ Total_HT_ligne.
    Retourne une liste de résultats par ligne.
    """
    results = []
    for i, art in enumerate(articles or []):
        qte   = art.get("quantite")
        pu    = art.get("prix_unitaire_ht")
        total = art.get("total_ht_ligne")
        desig = art.get("designation", f"Ligne {i + 1}")[:60]

        if qte is None or pu is None or total is None:
            results.append({
                "ligne"      : i + 1,
                "designation": desig,
                "status"     : "INCOMPLET",
                "detail"     : "QTE, PU_HT ou Total_HT manquant",
            })
            continue

        try:
            calculated = round(float(qte) * float(pu), 3)
            ecart      = round(abs(calculated - float(total)), 3)
            ok         = ecart <= TOLERANCE
        except (TypeError, ValueError) as e:
            results.append({
                "ligne"      : i + 1,
                "designation": desig,
                "status"     : "ERREUR_TYPE",
                "detail"     : str(e),
            })
            continue

        results.append({
            "ligne"          : i + 1,
            "designation"    : desig,
            "qte"            : qte,
            "prix_unitaire_ht": pu,
            "total_extrait"  : total,
            "total_calcule"  : calculated,
            "ecart"          : ecart,
            "status"         : "OK" if ok else "ERREUR",
        })

    return results


def validate_tva_globale(articles: list, montant_tva_extrait) -> dict:
    """
    Somme des TVA par ligne (total_ht_ligne × taux_tva) vs montant_tva extrait.
    Retourne un dict avec statut et écart.
    """
    if montant_tva_extrait is None:
        return {"status": "INCOMPLET", "detail": "montant_tva absent du JSON"}

    tva_calculee = 0.0
    lignes_ignorees = 0

    for art in articles or []:
        total_ht = art.get("total_ht_ligne")
        tva_str  = art.get("tva_rate_ligne")

        if total_ht is None:
            lignes_ignorees += 1
            continue

        rate = _parse_tva_rate(tva_str)
        tva_calculee += float(total_ht) * rate

    tva_calculee = round(tva_calculee, 3)
    extrait      = round(float(montant_tva_extrait), 3)
    ecart        = round(abs(tva_calculee - extrait), 3)
    ok           = ecart <= TOLERANCE

    result = {
        "tva_extraite"   : extrait,
        "tva_calculee"   : tva_calculee,
        "ecart"          : ecart,
        "status"         : "OK" if ok else "ERREUR",
    }
    if lignes_ignorees:
        result["lignes_ignorees"] = lignes_ignorees
    return result


def check_net_a_payer(
    montant_ht,
    montant_tva,
    timbre_fiscal,
    net_extrait,
) -> dict:
    """
    Calcule : montant_ht + montant_tva + timbre_fiscal ≈ net_a_payer (TTC).
    """
    if net_extrait is None:
        return {"status": "INCOMPLET", "detail": "net_a_payer (montant_ttc) absent"}

    ht      = float(montant_ht     or 0)
    tva     = float(montant_tva    or 0)
    timbre  = float(timbre_fiscal  or 0)
    extrait = float(net_extrait)

    net_calcule = round(ht + tva + timbre, 3)
    ecart       = round(abs(net_calcule - extrait), 3)
    ok          = ecart <= TOLERANCE

    return {
        "montant_ht"    : ht,
        "montant_tva"   : tva,
        "timbre_fiscal" : timbre,
        "net_calcule"   : net_calcule,
        "net_extrait"   : extrait,
        "ecart"         : ecart,
        "status"        : "OK" if ok else "ERREUR",
    }


def check_governance(complete_entities: dict) -> dict:
    """
    Vérifie les champs de gouvernance (signatures, tampons) selon le type de document.
    Retourne un dict {champ: bool, status: "OK"|"MANQUANT"}.
    """
    doc_type = complete_entities.get("_document_type", "facture")

    if "lettre" in doc_type or "change" in doc_type:
        sig_tire    = bool(complete_entities.get("signature_tire"))
        sig_tireur  = bool(complete_entities.get("signature_tireur"))
        cachet      = bool(complete_entities.get("cachet_present"))
        aval        = complete_entities.get("aval_bancaire")

        manquants = []
        if not sig_tire:   manquants.append("signature_tire")
        if not sig_tireur: manquants.append("signature_tireur")
        if not cachet:     manquants.append("cachet_present")

        return {
            "signature_tire"   : sig_tire,
            "signature_tireur" : sig_tireur,
            "cachet_present"   : cachet,
            "aval_bancaire"    : aval,
            "champs_manquants" : manquants,
            "status"           : "OK" if not manquants else "MANQUANT",
        }
    else:
        signature = bool(complete_entities.get("signature_presente"))
        cachet    = bool(complete_entities.get("cachet_present"))

        manquants = []
        if not signature: manquants.append("signature_presente")

        return {
            "signature_presente": signature,
            "cachet_present"    : cachet,
            "champs_manquants"  : manquants,
            "status"            : "OK" if not manquants else "MANQUANT",
        }
