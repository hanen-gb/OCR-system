"""
Vérifications arithmétiques et de conformité — Agent 2 : L'Auditeur.

Toutes les fonctions sont pures (pas d'I/O, pas de LLM).
Tolérance : 0.005 DT (5 millimes) pour absorber les arrondis de millimes.
"""

import re as _re

TOLERANCE       = 0.005   # 5 millimes — tolérance pour vérifications arithmétiques
_LETTRES_TOL    = 0.5     # 500 millimes — tolérance cross-check lettres (millimes parfois omis)

# ── Couche 3 : parser français + cross-check lettres vs montant ───────────────

_FR_NUMBERS = {
    "ZERO": 0, "UN": 1, "UNE": 1, "DEUX": 2, "TROIS": 3, "QUATRE": 4,
    "CINQ": 5, "SIX": 6, "SEPT": 7, "HUIT": 8, "NEUF": 9,
    "DIX": 10, "ONZE": 11, "DOUZE": 12, "TREIZE": 13, "QUATORZE": 14,
    "QUINZE": 15, "SEIZE": 16,
    "VINGT": 20, "TRENTE": 30, "QUARANTE": 40, "CINQUANTE": 50, "SOIXANTE": 60,
    "CENT": 100, "CENTS": 100, "GENT": 100, "GENTS": 100,  # OCR : CENTS → GENTS
    "MILLE": 1000, "MILLION": 1000000,
    # Composites normalisés par regex avant tokenisation
    "DIX_SEPT": 17, "DIX_HUIT": 18, "DIX_NEUF": 19,
    "SOIXANTE_DIX": 70, "QUATRE_VINGT": 80, "QUATRE_VINGT_DIX": 90,
}


def _lettres_to_int(text: str) -> int | None:
    """
    Convertit un entier en lettres françaises en int.
    "MILLE TROIS CENT VINGT"        → 1320
    "SIX CENTS"                     → 600
    "DIX NEUF"                      → 19
    "CINQ CENT QUATRE VINGT DIX NEUF" → 599
    Retourne None si aucun token reconnu.
    """
    text = text.upper().strip()
    if not text:
        return 0

    # Normaliser les composites ambigus avant tokenisation
    text = _re.sub(r'QUATRE[\s\-]+VINGT[\s\-]+DIX', 'QUATRE_VINGT_DIX', text)
    text = _re.sub(r'QUATRE[\s\-]+VINGT',           'QUATRE_VINGT',     text)
    text = _re.sub(r'SOIXANTE[\s\-]+DIX',           'SOIXANTE_DIX',     text)
    text = _re.sub(r'\bDIX[\s\-]+NEUF\b',            'DIX_NEUF',         text)
    text = _re.sub(r'\bDIX[\s\-]+HUIT\b',            'DIX_HUIT',         text)
    text = _re.sub(r'\bDIX[\s\-]+SEPT\b',            'DIX_SEPT',         text)
    text = text.replace('-', ' ')
    # Supprimer "ET" de liaison (vingt ET un → vingt un)
    text = _re.sub(r'\bET\b', ' ', text)

    tokens = [t for t in text.split() if t in _FR_NUMBERS]
    if not tokens:
        return None

    total, current = 0, 0
    for tok in tokens:
        v = _FR_NUMBERS[tok]
        if v == 1000000:
            current = max(current, 1)
            total  += current * 1000000
            current = 0
        elif v == 1000:
            current = max(current, 1)
            total  += current * 1000
            current = 0
        elif v == 100:
            current = max(current, 1) * 100
        else:
            current += v

    return total + current


def parse_lettres_to_amount(text: str) -> float | None:
    """
    Parse le montant en toutes lettres (français) vers un float DT.

    Exemples :
      "MILLE TROIS CENT VINGT DINARS SIX CENTS MILLIMES"          → 1320.600
      "TRENTE DINARS ET SEPT CENT CINQUANTE MILLIMES"              → 30.750
      "DIX NEUF DINARS CINQ CENT QUATRE VINGT DIX NEUF MILLIMES"  → 19.599
      "DEUX CENT QUATRE VINGT QUATORZE DINARS"                     → 294.000

    Retourne None si le texte ne peut pas être parsé (OCR trop dégradé, typos).
    """
    if not text:
        return None

    upper = text.upper().strip()

    m_dinar = _re.search(r'\bDINARS?\b', upper)
    if not m_dinar:
        return None

    dinar_text = upper[:m_dinar.start()].strip()
    after      = upper[m_dinar.end():].strip()
    # Supprimer "ET" en début de partie millimes
    after = _re.sub(r'^\s*ET\b\s*', '', after).strip()

    m_mil = _re.search(r'\bMILLIMES?\b|\bCENTIMES?\b', after)
    millimes_text = after[:m_mil.start()].strip() if m_mil else ""

    dinars   = _lettres_to_int(dinar_text)
    millimes = _lettres_to_int(millimes_text) if millimes_text else 0

    if dinars is None:
        return None

    return round(dinars + (millimes or 0) / 1000, 3)


def check_net_lettres(net_a_payer: float | None, net_a_payer_lettres: str | None) -> dict:
    """
    Couche 3 — compare net_a_payer numérique avec net_a_payer_lettres parsé.

    Le texte en toutes lettres est l'ancre de vérité : il ne souffre pas des
    ambiguïtés de séparateur décimal (point/virgule) qui causent des erreurs
    10× ou 1000× sur les montants numériques.

    Statuts : OK | ERREUR_MONTANT | INCOMPLET
    Tolérance : 500 millimes (les lettres omettent parfois les millimes).
    """
    if not net_a_payer_lettres:
        return {"status": "INCOMPLET", "detail": "net_a_payer_lettres absent"}

    valeur_lettres = parse_lettres_to_amount(net_a_payer_lettres)
    if valeur_lettres is None:
        return {
            "status": "INCOMPLET",
            "detail": f"Impossible de parser les lettres : '{net_a_payer_lettres[:80]}'",
        }

    if net_a_payer is None:
        return {
            "status"         : "INCOMPLET",
            "valeur_lettres" : valeur_lettres,
            "detail"         : "net_a_payer absent — impossible de comparer",
        }

    ecart = round(abs(valeur_lettres - net_a_payer), 3)
    ok    = ecart <= _LETTRES_TOL

    return {
        "valeur_lettres"  : valeur_lettres,
        "valeur_extraite" : net_a_payer,
        "ecart"           : ecart,
        "status"          : "OK" if ok else "ERREUR_MONTANT",
        "detail"          : (
            "Cohérence lettres/chiffres confirmée"
            if ok
            else (
                f"INCOHÉRENCE : lettres={valeur_lettres} DT "
                f"≠ extrait={net_a_payer} DT (écart={ecart} DT)"
            )
        ),
    }


def _parse_tva_rate(tva_str) -> float | None:
    """'19%' → 0.19 · '7%' → 0.07 · None/0/'exonéré' → 0.0
    Gère aussi les erreurs OCR : '2016' → 0.20, '1906' → 0.19
    """
    if tva_str is None:
        return 0.0
    s = str(tva_str).strip().replace("%", "").replace(",", ".").replace(" ", "")
    try:
        val = float(s)
        if 0.0 <= val <= 1.0:   # déjà en décimal ex: 0.19
            return val
        if 0.0 < val <= 100.0:  # pourcentage normal ex: 19, 20, 7
            return val / 100
        # val > 100 → erreur OCR (ex: "2016" lu au lieu de "20%")
        for known in [7, 13, 19, 20, 25]:
            if s.startswith(str(known)):
                print(f"[TVA] Correction OCR : '{tva_str}' → {known}%")
                return known / 100
        print(f"[TVA] Taux aberrant '{tva_str}' ignoré → 0%")
        return 0.0
    except ValueError:
        return 0.0


def check_arithmetic_lines(articles: list) -> list:
    """
    Pour chaque article : vérifie QTE × PU_HT × (1 - remise%) ≈ Total_HT_ligne.
    Prend en compte la remise par ligne si présente (colonne %RM / Remise).
    Tolérance : 0.005 DT (5 millimes).
    """
    results = []
    for i, art in enumerate(articles or []):
        qte    = art.get("quantite")
        pu     = art.get("prix_unitaire_ht")
        total  = art.get("total_ht_ligne")
        remise = art.get("remise_pct_ligne")   # % remise (ex: 10 pour 10%)
        desig  = art.get("designation", f"Ligne {i + 1}")[:60]

        if qte is None or pu is None or total is None:
            results.append({
                "ligne"      : i + 1,
                "designation": desig,
                "status"     : "INCOMPLET",
                "detail"     : "QTE, PU_HT ou Total_HT manquant",
            })
            continue

        try:
            remise_rate = float(remise) / 100 if remise is not None else 0.0
            calculated  = round(float(qte) * float(pu) * (1 - remise_rate), 3)
            ecart       = round(abs(calculated - float(total)), 3)
            ok          = ecart <= TOLERANCE

            # Correction per-mille (unité MIL) : QTE / 1000 × PU ≈ Total
            if not ok:
                unite = str(art.get("unite", "") or "").upper().strip()
                if unite in ("MIL", "M") or (float(total) > 0 and calculated > float(total) * 500):
                    calculated_mil = round(float(qte) / 1000 * float(pu) * (1 - remise_rate), 3)
                    ecart_mil      = round(abs(calculated_mil - float(total)), 3)
                    if ecart_mil <= TOLERANCE:
                        calculated = calculated_mil
                        ecart      = ecart_mil
                        ok         = True
        except (TypeError, ValueError) as e:
            results.append({
                "ligne"      : i + 1,
                "designation": desig,
                "status"     : "ERREUR_TYPE",
                "detail"     : str(e),
            })
            continue

        results.append({
            "ligne"           : i + 1,
            "designation"     : desig,
            "qte"             : qte,
            "prix_unitaire_ht": pu,
            "remise_pct"      : remise,
            "total_extrait"   : total,
            "total_calcule"   : calculated,
            "ecart"           : ecart,
            "status"          : "OK" if ok else "ERREUR",
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
    fodec=None,
    net_htva=None,
) -> dict:
    """
    Calcule : base_htva + TVA + Timbre ≈ net_a_payer.

    base_htva est déterminé par priorité :
      1. net_htva extrait (NET H.TVA / NET HT — déjà inclut FODEC et remise)
      2. montant_ht + fodec (si net_htva absent)
      3. montant_ht seul (si pas de FODEC)

    Gère les spécificités tunisiennes : FODEC, remises, timbre.
    """
    if net_extrait is None:
        return {"status": "INCOMPLET", "detail": "net_a_payer (montant_ttc) absent"}

    tva    = float(montant_tva   or 0)
    timbre = float(timbre_fiscal or 0)

    # Priorité 1 : net_htva direct (inclut déjà remise + FODEC)
    if net_htva is not None:
        base = float(net_htva)
        base_label = "net_htva"
    # Priorité 2 : montant_ht + fodec
    elif montant_ht is not None:
        base = float(montant_ht) + float(fodec or 0)
        base_label = "montant_ht + fodec"
    else:
        base = 0.0
        base_label = "inconnu"

    extrait     = float(net_extrait)
    net_calcule = round(base + tva + timbre, 3)
    ecart       = round(abs(net_calcule - extrait), 3)
    ok          = ecart <= TOLERANCE

    return {
        "base_htva"     : base,
        "base_label"    : base_label,
        "montant_tva"   : tva,
        "timbre_fiscal" : timbre,
        "fodec"         : float(fodec) if fodec is not None else None,
        "net_calcule"   : net_calcule,
        "net_extrait"   : extrait,
        "ecart"         : ecart,
        "status"        : "OK" if ok else "ERREUR",
    }


def check_montant_traite(montant_chiffres: float | None, montant_lettres_text: str | None) -> dict:
    """Cross-check montant numérique vs montant en lettres pour une lettre de change."""
    if not montant_lettres_text:
        return {"status": "INCOMPLET", "detail": "montant_en_lettres absent"}

    valeur_lettres = parse_lettres_to_amount(montant_lettres_text)
    if valeur_lettres is None:
        return {"status": "INCOMPLET", "detail": f"Impossible de parser : '{montant_lettres_text[:80]}'"}

    if montant_chiffres is None:
        return {"status": "INCOMPLET", "valeur_lettres": valeur_lettres, "detail": "montant numérique absent"}

    ecart = round(abs(valeur_lettres - montant_chiffres), 3)
    ok    = ecart <= _LETTRES_TOL
    return {
        "valeur_lettres" : valeur_lettres,
        "valeur_chiffres": montant_chiffres,
        "ecart"          : ecart,
        "status"         : "OK" if ok else "ERREUR_MONTANT",
        "detail"         : ("Cohérence lettres/chiffres confirmée"
                            if ok else
                            f"Incohérence : lettres={valeur_lettres} ≠ chiffres={montant_chiffres} (écart={ecart} DT)"),
    }


def check_echeance_traite(date_echeance_str: str | None) -> dict:
    """Vérifie que la date d'échéance est présente et non dépassée."""
    from datetime import datetime, date
    if not date_echeance_str:
        return {"status": "INCOMPLET", "detail": "date_echeance absente"}

    for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d", "%d/%m/%y", "%d.%m.%Y"):
        try:
            d     = datetime.strptime(date_echeance_str.strip(), fmt).date()
            today = date.today()
            delta = (d - today).days
            if delta < 0:
                return {"status": "DEPASSEE", "date": str(d), "jours_depassement": abs(delta),
                        "detail": f"Échéance dépassée de {abs(delta)} jour(s)"}
            elif delta <= 7:
                return {"status": "PROCHE",   "date": str(d), "jours_restants": delta,
                        "detail": f"Échéance dans {delta} jour(s)"}
            else:
                return {"status": "OK",       "date": str(d), "jours_restants": delta,
                        "detail": "Échéance valide"}
        except ValueError:
            continue

    return {"status": "INCOMPLET", "detail": f"Format date non reconnu : '{date_echeance_str}'"}


def check_rib_traite(rib: str | None) -> dict:
    """
    Vérifie que le RIB bancaire de la lettre de change contient exactement 20 chiffres.
    Format tunisien : 2 (banque) + 3 (agence) + 13 (compte) + 2 (clé) = 20 chiffres.
    """
    if not rib:
        return {"status": "INCOMPLET", "detail": "RIB absent"}

    digits = _re.sub(r'\D', '', str(rib))
    if len(digits) == 20:
        return {
            "status" : "OK",
            "rib"    : rib,
            "detail" : f"RIB valide — 20 chiffres",
        }
    return {
        "status"      : "ERREUR_RIB",
        "rib"         : rib,
        "nb_chiffres" : len(digits),
        "detail"      : f"RIB invalide — {len(digits)} chiffre(s) détecté(s), attendu 20",
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
        # Cachet seul est suffisant (factures tunisiennes) : MANQUANT seulement si les DEUX sont absents
        if not signature and not cachet:
            manquants.append("signature_presente")

        return {
            "signature_presente": signature,
            "cachet_present"    : cachet,
            "champs_manquants"  : manquants,
            "status"            : "OK" if not manquants else "MANQUANT",
        }
