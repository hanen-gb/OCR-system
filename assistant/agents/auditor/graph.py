"""
Sous-graphe LangGraph — Agent 2 : L'Auditeur

Sequential flow:
    START → prepare
              ↓
           arithmetic   ← QTE × PU ≈ Total_HT par ligne
              ↓
            tva          ← Σ TVA lignes ≈ montant_tva global
              ↓
            net          ← excl. VAT + VAT + stamp duty ≈ net amount payable
              ↓
           lettres       ← Layer 3: net_a_payer_lettres vs numeric net_a_payer
              ↓
           doublon       ← PostgreSQL: number already stored?
              ↓
          gouvernance    ← Signatures, tampons, aval
              ↓
           verdict       ← Status final
              ↓
        notification     ← E-mail if amount > threshold or due date close
              ↓
             END
"""

import re

from langgraph.graph import StateGraph, START, END

from state import AuditorState
from agents.auditor.checks import (
    check_arithmetic_lines,
    validate_tva_globale,
    check_net_a_payer,
    check_governance,
    check_net_lettres,
    check_montant_traite,
    check_echeance_traite,
    check_rib_traite,
)
from database import check_doublon_pg, get_documents_pg
from agents.auditor.notifier import check_alert_conditions, send_alert_email, ALERT_EMAIL_TO


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
                # Handles decimal commas and thousands spaces ("135,660" → 135.660)
                if isinstance(v, str):
                    v = re.sub(r"\s", "", v.strip())
                    # Point + 3 chiffres = millimes tunisiens → garder (135.660)
                    # Comma = decimal separator → convert to a dot
                    if "," in v and "." not in v:
                        v = v.replace(",", ".")
                    elif "," in v and "." in v:
                        v = v.replace(".", "").replace(",", ".")
                return float(v)
            except (TypeError, ValueError):
                pass
    return None


def _is_hallucinated(
    value: float | None,
    articles: list,
    montant_ht: float | None = None,
) -> bool:
    """
    Detects a monetary value hallucinated by the LLM.
    Trois cas :
      1. Repetitive number: 333333, 111111, 999999…
      2. Value > 10× the actual sum of the item lines
      3. Valeur > 5× montant_ht global (si disponible)
    """
    if value is None:
        return False
    # Case 1 — repeated digits
    s = str(int(abs(value)))
    if len(s) >= 4 and len(set(s)) == 1:
        return True
    # Case 2 — outlier compared with the actual items
    total_lignes = sum(
        float(a["total_ht_ligne"])
        for a in articles
        if a.get("total_ht_ligne") is not None
    )
    if total_lignes > 0 and value > total_lignes * 10:
        return True
    # Case 3 — outlier vs overall montant_ht (service invoices without items)
    if montant_ht is not None and montant_ht > 0 and value > montant_ht * 5:
        return True
    return False


# ── Nœuds ─────────────────────────────────────────────────────────────────────

def prepare_node(state: AuditorState) -> dict:
    """Resolves doc_type, doc_number, supplier and total amount from the entities."""
    entities = state.get("complete_entities") or {}
    base     = state.get("base_entities") or {}

    doc_type = _str(entities, "_document_type") or "facture"
    is_traite = "lettre" in doc_type or "change" in doc_type

    if is_traite:
        doc_number  = (_str(base, "NUMERO_TRAITE", "num_lettre")   or _str(entities, "NUMERO_TRAITE", "num_lettre"))
        fournisseur = (_str(base, "TIREUR", "tireur")               or _str(entities, "TIREUR", "tireur"))
        montant_ttc = (_num(base, "MONTANT", "montant")             or _num(entities, "MONTANT", "montant"))
        date_doc    = (_str(base, "DATE_ECHEANCE", "date_echeance") or _str(entities, "date_echeance"))
    else:
        # Accepts UPPER-CASE keys (GLM editedMap) AND lower-case keys (Agent 1)
        doc_number  = (_str(base, "NUMERO_FACTURE", "num_facture")  or _str(entities, "num_facture", "numero_facture"))
        fournisseur = None
        if isinstance(base.get("FOURNISSEUR"), dict):
            fournisseur = base["FOURNISSEUR"].get("nom")
        elif isinstance(base.get("fournisseur"), dict):
            fournisseur = base["fournisseur"].get("nom")
        fournisseur = (fournisseur or _str(base, "FOURNISSEUR", "fournisseur")
                       or _str(entities, "fournisseur"))
        montant_ttc = (_num(base, "MONTANT_TTC", "montant_ttc")     or _num(entities, "net_a_payer"))
        date_doc    = (_str(base, "DATE_FACTURE", "date_facture")    or _str(entities, "date_facture"))

    # Reject hallucinated values (333333, value >> items or >> amount excl. VAT)
    articles_prepare = entities.get("articles") or []
    montant_ht_prepare = _num(entities, "montant_ht")
    if _is_hallucinated(montant_ttc, articles_prepare, montant_ht_prepare):
        print(f"[AUDITOR] Hallucinated value detected ({montant_ttc}) → ignored, montant_ttc=null")
        montant_ttc = None

    print(f"[AUDITEUR] type={doc_type} | num={doc_number} | ttc={montant_ttc}")
    return {
        "doc_type"   : doc_type,
        "doc_number" : doc_number,
        "fournisseur": fournisseur,
        "montant_ttc": montant_ttc,
        "date_doc"   : date_doc,
    }


def route_by_doc_type(state: AuditorState) -> str:
    """Conditional routing: bill of exchange → simplified path, invoice → full arithmetic path."""
    doc_type = state.get("doc_type") or ""
    if "lettre" in doc_type or "change" in doc_type or "traite" in doc_type:
        return "traite"
    return "facture"


def montant_traite_node(state: AuditorState) -> dict:
    """Cross-checks the amount in words against the numeric amount of a bill of exchange.
    Tries montant_en_lettres first, then notes_manuscrites when the first one
    is missing or gives an inconsistent result (degraded OCR, e.g. GENTS vs CENTS).
    """
    entities         = state.get("complete_entities") or {}
    montant_chiffres = state.get("montant_ttc")

    lettres_primary = entities.get("montant_en_lettres")
    lettres_fallback = entities.get("notes_manuscrites")

    result = check_montant_traite(montant_chiffres, lettres_primary)

    # If the primary result is ERREUR_MONTANT and a fallback exists, try notes_manuscrites
    if result.get("status") == "ERREUR_MONTANT" and lettres_fallback and lettres_fallback != lettres_primary:
        result_fb = check_montant_traite(montant_chiffres, lettres_fallback)
        if result_fb.get("status") == "OK":
            print(f"[AUDITOR/BILL] degraded montant_en_lettres → notes_manuscrites used")
            result = result_fb

    print(f"[AUDITOR/BILL] Amount in words: {result.get('status')}")
    return {"check_montant_traite": result}


def echeance_node(state: AuditorState) -> dict:
    """Checks the due date of the bill of exchange."""
    base     = state.get("base_entities") or {}
    entities = state.get("complete_entities") or {}
    date_ech = (_str(base, "DATE_ECHEANCE", "date_echeance") or _str(entities, "date_echeance"))
    result   = check_echeance_traite(date_ech)
    print(f"[AUDITOR/BILL] Due date: {result.get('status')} ({date_ech})")
    return {"check_echeance": result}


def rib_node(state: AuditorState) -> dict:
    """Checks that the bank RIB has exactly 20 digits (Tunisian standard)."""
    base     = state.get("base_entities") or {}
    entities = state.get("complete_entities") or {}
    rib      = (_str(base, "RIB", "rib") or _str(entities, "rib", "rib_tire"))
    result   = check_rib_traite(rib)
    print(f"[AUDITEUR/TRAITE] RIB : {result.get('status')} — {result.get('detail')}")
    return {"check_rib": result}


def arithmetic_node(state: AuditorState) -> dict:
    """Checks QTY × unit price excl. VAT ≈ line total excl. VAT for each item line."""
    articles = (state.get("complete_entities") or {}).get("articles") or []
    result   = check_arithmetic_lines(articles)
    nb_err   = sum(1 for r in result if r["status"] == "ERREUR")
    print(f"[AUDITOR] Arithmetic: {len(result)} lines, {nb_err} errors")
    return {"check_arithmetique": result}


def tva_node(state: AuditorState) -> dict:
    """Checks Σ line VAT ≈ overall montant_tva.
    Fallback 1 : si tva_rate_ligne absent → injecte tva_rate global.
    Fallback 2: if tva_rate is an outlier → recomputed from montant_tva / montant_ht.
    """
    entities    = state.get("complete_entities") or {}
    articles    = entities.get("articles") or []
    montant_tva = _num(entities, "montant_tva")

    # Compute montant_tva automatically when missing (missed by Agent 1)
    # Formula: amount excl. VAT × VAT rate — if the overall amount or the item sum and the rate are available
    if montant_tva is None and entities.get("tva_rate") is not None:
        ht_base = _num(entities, "montant_ht") or _num(entities, "montant_ht_ar") or _num(entities, "net_htva")
        if ht_base is None and articles:
            try:
                ht_base = round(sum(
                    float(a["total_ht_ligne"])
                    for a in articles if a.get("total_ht_ligne") is not None
                ), 3)
            except (TypeError, ValueError):
                pass
        if ht_base:
            try:
                t = float(str(entities["tva_rate"]).replace("%", "").strip())
                if t > 1: t /= 100
                montant_tva = round(ht_base * t, 3)
                print(f"[AUDITOR] montant_tva null → computed: {ht_base} × {t*100:.1f}% = {montant_tva}")
            except (ValueError, TypeError):
                pass

    # ×1000 bug detection (TND millimes read without the decimal separator, e.g. 3672 instead of 3.672)
    mht_ref = _num(entities, "montant_ht") or _num(entities, "montant_ht_ar") or _num(entities, "net_htva")
    if mht_ref is None and articles:
        try:
            s = round(sum(float(a["total_ht_ligne"]) for a in articles if a.get("total_ht_ligne") is not None), 3)
            if s > 0:
                mht_ref = s
        except (TypeError, ValueError):
            pass
    if montant_tva is not None and mht_ref is not None and mht_ref > 0:
        if montant_tva > mht_ref * 0.6:
            corrige = round(montant_tva / 1000, 3)
            if 0.03 * mht_ref <= corrige <= 0.35 * mht_ref:
                print(f"[AUDITOR] ×1000 bug detected: montant_tva {montant_tva} → {corrige}")
                montant_tva = corrige

    # Overall VAT rate check: if it is an outlier, recompute it from montant_tva/montant_ht
    taux_global_raw = entities.get("tva_rate")
    if taux_global_raw is not None:
        try:
            taux_val = float(str(taux_global_raw))
            TAUX_CONNUS = {7, 13, 19, 20, 25}
            if taux_val not in TAUX_CONNUS:
                # Try to recompute it from the overall amounts
                mht = _num(entities, "montant_ht") or _num(entities, "montant_ht_ar") or _num(entities, "net_htva")
                mtva = _num(entities, "montant_tva")
                if mht and mtva and mht > 0:
                    taux_recalc = round(mtva / mht * 100, 1)
                    # Round to the closest known rate
                    taux_corrige = min(TAUX_CONNUS, key=lambda t: abs(t - taux_recalc))
                    if abs(taux_recalc - taux_corrige) < 3:
                        print(f"[AUDITOR] outlier tva_rate ({taux_val}%) → corrected to {taux_corrige}% (recomputed={taux_recalc}%)")
                        taux_global_raw = str(taux_corrige)
        except (ValueError, TypeError):
            pass

    # Rate fallback: if tva_rate is missing but excl. VAT + VAT are available → implicit rate
    if taux_global_raw is None and montant_tva is not None and montant_tva > 0:
        mht_imp = _num(entities, "montant_ht") or _num(entities, "montant_ht_ar") or _num(entities, "net_htva")
        if mht_imp and mht_imp > 0:
            implied     = round(montant_tva / mht_imp * 100, 1)
            TAUX_CONNUS = {7, 13, 19, 20, 25}
            taux_proche = min(TAUX_CONNUS, key=lambda t: abs(t - implied))
            if abs(implied - taux_proche) < 3:
                taux_global_raw = str(taux_proche)
                print(f"[AUDITEUR] tva_rate absent → taux implicite {implied}% → {taux_proche}%")

    # Fallback: if no line has a VAT rate, inject the overall rate
    taux_ligne_absents = all(a.get("tva_rate_ligne") is None for a in articles)
    if taux_ligne_absents and articles and taux_global_raw is not None:
        taux_global = str(taux_global_raw).replace("%", "").strip()
        articles = [
            {**a, "tva_rate_ligne": taux_global}
            for a in articles
            if a.get("total_ht_ligne") is not None
        ]
        print(f"[AUDITOR] tva_rate_ligne missing → overall rate '{taux_global}%' injected on {len(articles)} line(s)")

    # Overall discount: spread proportionally over the lines before computing VAT
    remise_globale = _num(entities, "remise_globale")
    if remise_globale is not None and remise_globale < 0 and articles:
        try:
            total_lines = sum(
                float(a["total_ht_ligne"])
                for a in articles if a.get("total_ht_ligne") is not None
            )
            if total_lines > 0:
                remise_ratio = abs(remise_globale) / total_lines
                articles = [
                    {**a, "total_ht_ligne": round(float(a["total_ht_ligne"]) * (1 - remise_ratio), 3)}
                    for a in articles if a.get("total_ht_ligne") is not None
                ]
                print(f"[AUDITOR] Overall discount {remise_globale} → ratio {remise_ratio:.4f} spread over {len(articles)} line(s)")
        except (TypeError, ValueError):
            pass

    result = validate_tva_globale(articles, montant_tva)
    print(f"[AUDITOR] VAT: {result.get('status')} (difference={result.get('ecart')})")
    return {"check_tva": result}


def net_node(state: AuditorState) -> dict:
    """Checks amount excl. VAT + VAT + stamp duty ≈ net_a_payer (incl. VAT)."""
    entities = state.get("complete_entities") or {}

    montant_ht = _num(entities, "montant_ht")

    # Fallback 1: montant_ht_ar (after discount) when montant_ht is missing
    if montant_ht is None:
        montant_ht = _num(entities, "montant_ht_ar")
        if montant_ht:
            print(f"[AUDITOR] montant_ht → from montant_ht_ar: {montant_ht}")

    # Fallback 2: sum of the items if still null
    if montant_ht is None:
        articles = entities.get("articles") or []
        try:
            total_lignes = sum(
                float(a["total_ht_ligne"])
                for a in articles
                if a.get("total_ht_ligne") is not None
            )
            if total_lignes > 0:
                montant_ht = round(total_lignes, 3)
                print(f"[AUDITOR] montant_ht → rebuilt from the items: {montant_ht}")
        except (TypeError, ValueError):
            pass

    # Fallback 3 (back-calculation): excl. VAT = incl. VAT − VAT − stamp duty — when everything else is null
    if montant_ht is None and state.get("montant_ttc") is not None:
        try:
            tva_rc    = _num(entities, "montant_tva") or 0
            timbre_rc = _num(entities, "timbre_fiscal") or 0
            fodec_rc  = _num(entities, "fodec") or 0
            retro     = round(float(state["montant_ttc"]) - tva_rc - timbre_rc - fodec_rc, 3)
            if retro > 0:
                montant_ht = retro
                print(f"[AUDITOR] montant_ht back-calculated: incl. VAT − VAT − stamp = {montant_ht}")
        except (TypeError, ValueError):
            pass

    # montant_tva: use the extracted value or compute it as amount excl. VAT × rate
    montant_tva_net = _num(entities, "montant_tva")
    if montant_tva_net is None and montant_ht is not None and entities.get("tva_rate") is not None:
        try:
            t = float(str(entities["tva_rate"]).replace("%", "").strip())
            if t > 1: t /= 100
            montant_tva_net = round(montant_ht * t, 3)
            print(f"[AUDITOR/net] montant_tva computed for check_net: {montant_tva_net}")
        except (ValueError, TypeError):
            pass

    # ×1000 bug detection: VAT cannot exceed 60% of the amount excl. VAT
    if montant_tva_net is not None and montant_ht is not None and montant_ht > 0:
        if montant_tva_net > montant_ht * 0.6:
            corrige = round(montant_tva_net / 1000, 3)
            if 0.03 * montant_ht <= corrige <= 0.35 * montant_ht:
                print(f"[AUDITOR/net] ×1000 bug detected: montant_tva {montant_tva_net} → {corrige}")
                montant_tva_net = corrige

    result = check_net_a_payer(
        montant_ht    = montant_ht,
        montant_tva   = montant_tva_net,
        timbre_fiscal = _num(entities, "timbre_fiscal"),
        net_extrait   = state.get("montant_ttc"),
        fodec         = _num(entities, "fodec"),
        net_htva      = _num(entities, "net_htva"),
    )
    print(f"[AUDITOR] Net payable: {result.get('status')} (difference={result.get('ecart')})")
    return {"check_net": result}


def lettres_node(state: AuditorState) -> dict:
    """
    Layer 3 — cross-checks net_a_payer_lettres against the numeric net_a_payer.
    The amount in words is the anchor of truth (no decimal-separator ambiguity).
    A difference > 500 millimes signals a parsing error in Agent 1.
    """
    entities            = state.get("complete_entities") or {}
    net_a_payer         = _num(entities, "net_a_payer")
    net_a_payer_lettres = entities.get("net_a_payer_lettres")

    result = check_net_lettres(net_a_payer, net_a_payer_lettres)
    print(f"[AUDITOR] Amount in words: {result.get('status')} | difference={result.get('ecart')} TND")
    return {"check_lettres": result}


def doublon_node(state: AuditorState) -> dict:
    """Queries PostgreSQL to detect a duplicate."""
    result = check_doublon_pg(state.get("doc_type") or "facture", state.get("doc_number"))
    print(f"[AUDITEUR] Doublon : {result.get('status')} ({state.get('doc_number')})")
    return {"check_doublon": result}


def gouvernance_node(state: AuditorState) -> dict:
    """Checks the governance fields (signatures, stamps, bank guarantee)."""
    entities = state.get("complete_entities") or {}
    result   = check_governance(entities)
    print(f"[AUDITEUR] Gouvernance : {result.get('status')} — manquants={result.get('champs_manquants')}")
    return {"check_gouvernance": result}


def verdict_node(state: AuditorState) -> dict:
    """Computes the final status and stores the document if it is new."""
    doublon     = state.get("check_doublon") or {}
    gouvernance = state.get("check_gouvernance") or {}
    entities    = state.get("complete_entities") or {}
    doc_type    = state.get("doc_type") or ""
    is_traite   = "lettre" in doc_type or "change" in doc_type or "traite" in doc_type

    # Note: the document is persisted in PostgreSQL by
    # save_document() (assistant/api/main.py), called right after this graph.

    # ── Bill of exchange path ───────────────────────────────────────────────────
    if is_traite:
        montant_traite = state.get("check_montant_traite") or {}
        echeance       = state.get("check_echeance") or {}
        rib            = state.get("check_rib") or {}

        if doublon.get("status") == "DOUBLON":
            status = "DOUBLON"
        elif gouvernance.get("status") == "MANQUANT":
            status = "SIGNATURE_MANQUANTE"
        elif montant_traite.get("status") == "ERREUR_MONTANT":
            status = "ERREUR_MONTANT_LETTRES"
        elif echeance.get("status") == "DEPASSEE":
            status = "ECHEANCE_DEPASSEE"
        elif rib.get("status") == "ERREUR_RIB":
            status = "ERREUR_RIB"
        else:
            status = "VALIDÉ"

        rapport = {
            "status_validite"     : status,
            "doc_type"            : doc_type,
            "doc_number"          : state.get("doc_number"),
            "fournisseur"         : state.get("fournisseur"),  # = tireur
            "check_montant_traite": montant_traite,
            "check_echeance"      : echeance,
            "check_rib"           : rib,
            "gouvernance"         : gouvernance,
            "alerte_doublon"      : doublon,
        }
        print(f"[AUDITEUR/TRAITE] Verdict : {status}")
        return {"status_validite": status, "audit_report": rapport}

    # ── Invoice path ─────────────────────────────────────────────────────────────
    arithmetique = state.get("check_arithmetique") or []
    lettres      = state.get("check_lettres") or {}
    articles     = entities.get("articles") or []

    nb_erreurs_calcul = sum(1 for r in arithmetique if r.get("status") == "ERREUR")

    MOTS_SERVICES = {
        "total", "hors taxes", "abonnement", "forfait", "consommation",
        "redevance", "location", "loyer", "prestation", "service",
        "facture", "montant", "sous-total", "subtotal",
    }
    articles_sont_services = (
        all(a.get("quantite") is None and a.get("prix_unitaire_ht") is None for a in articles)
        or (len(articles) > 0 and all(
            any(mot in (a.get("designation") or "").lower() for mot in MOTS_SERVICES)
            for a in articles
        ))
    )
    est_facture_electronique = (
        entities.get("logo_detecte") is True
        and entities.get("etat_document") == "original"
        and articles_sont_services
    )
    cachet_present = bool(entities.get("cachet_present"))

    if doublon.get("status") == "DOUBLON":
        status = "DOUBLON"
    elif (gouvernance.get("status") == "MANQUANT"
          and not est_facture_electronique
          and not cachet_present):
        status = "SIGNATURE_MANQUANTE"
    elif nb_erreurs_calcul > 0:
        status = "ERREUR_CALCUL"
    elif lettres.get("status") == "ERREUR_MONTANT":
        status = "ERREUR_MONTANT_LETTRES"
    else:
        status = "VALIDÉ"

    document_incomplet = (
        _num(entities, "montant_ht")  is None and
        _num(entities, "montant_tva") is None and
        state.get("montant_ttc")      is None and
        len(articles) > 0
    )
    if document_incomplet:
        print("[AUDITOR] Document possibly truncated — totals block missing")

    rapport = {
        "status_validite"           : status,
        "document_incomplet"        : document_incomplet,
        "doc_type"                  : doc_type,
        "doc_number"                : state.get("doc_number"),
        "fournisseur"               : state.get("fournisseur"),
        "nb_articles"               : len(articles),
        "nb_erreurs_calcul"         : nb_erreurs_calcul,
        "nb_lignes_incompletes"     : sum(1 for r in arithmetique if r.get("status") == "INCOMPLET"),
        "check_arithmetique_lignes" : arithmetique,
        "check_lettres_vs_net"      : lettres,
        "gouvernance"               : gouvernance,
        "alerte_doublon"            : doublon,
    }

    print(f"[AUDITEUR] Verdict final : {status}")
    return {"status_validite": status, "audit_report": rapport}


def notification_node(state: AuditorState) -> dict:
    """
    Checks the alert conditions and sends an e-mail if needed.

    Trigger conditions:
      1. Total amount incl. VAT > ALERT_THRESHOLD_DT  (default 5,000 TND)
      2. Due date within ≤ ALERT_DEADLINE_DAYS days (default 7) or already passed
      3. New document AND total amount incl. VAT > ALERT_NOUVEAU_MONTANT_DT (default 4,000 TND)
    """
    entities    = state.get("complete_entities") or {}
    base        = state.get("base_entities") or {}
    montant_ttc = state.get("montant_ttc")
    doc_type    = state.get("doc_type")
    is_traite   = "lettre" in (doc_type or "")
    is_nouveau  = (state.get("check_doublon") or {}).get("status") == "NOUVEAU"

    # Get the due date according to the document type
    if is_traite:
        date_echeance = state.get("date_doc")  # set by prepare_node from base_entities
    else:
        date_echeance = (
            _str(entities, "date_echeance")
            or _str(base, "date_echeance")
        )

    # Load the PostgreSQL history to compare the amount with the average of the same type
    try:
        historique = get_documents_pg(limit=500)
    except Exception:
        historique = []

    alerts = check_alert_conditions(
        montant_ttc   = montant_ttc,
        date_echeance = date_echeance,
        doc_type      = doc_type,
        historique    = historique,
        is_nouveau    = is_nouveau,
    )

    sent = False
    if alerts:
        sent = send_alert_email(
            alerts          = alerts,
            doc_type        = doc_type,
            doc_number      = state.get("doc_number"),
            fournisseur     = state.get("fournisseur"),
            montant_ttc     = montant_ttc,
            date_echeance   = date_echeance,
            status_validite = state.get("status_validite"),
        )
    else:
        print("[NOTIFIER] No alert condition triggered")

    # Add the notification result to audit_report
    rapport = state.get("audit_report") or {}
    rapport["notification"] = {
        "alerted"   : bool(alerts),
        "sent"      : sent,
        "alerts"    : alerts,
        "recipient" : ALERT_EMAIL_TO if sent else None,
    }

    return {
        "notification_sent"   : sent,
        "notification_alerts" : alerts,
        "audit_report"        : rapport,
    }


# ── Graphe ────────────────────────────────────────────────────────────────────

def build_auditor_graph():
    builder = StateGraph(AuditorState)

    builder.add_node("prepare",        prepare_node)
    # Invoice path: arithmetic → amount in words (VAT and Net checks removed from the pipeline)
    builder.add_node("arithmetic",     arithmetic_node)
    builder.add_node("lettres",        lettres_node)
    # Traite path
    builder.add_node("montant_traite", montant_traite_node)
    builder.add_node("echeance",       echeance_node)
    builder.add_node("rib",            rib_node)
    # Common
    builder.add_node("doublon",        doublon_node)
    builder.add_node("gouvernance",    gouvernance_node)
    builder.add_node("verdict",        verdict_node)
    builder.add_node("notification",   notification_node)

    builder.add_edge(START, "prepare")
    builder.add_conditional_edges("prepare", route_by_doc_type, {
        "facture": "arithmetic",
        "traite" : "montant_traite",
    })
    # Facture path
    builder.add_edge("arithmetic",     "lettres")
    builder.add_edge("lettres",        "doublon")
    # Traite path
    builder.add_edge("montant_traite", "echeance")
    builder.add_edge("echeance",       "rib")
    builder.add_edge("rib",            "doublon")
    # Common
    builder.add_edge("doublon",        "gouvernance")
    builder.add_edge("gouvernance",    "verdict")
    builder.add_edge("verdict",        "notification")
    builder.add_edge("notification",   END)

    return builder.compile()


auditor_graph = build_auditor_graph()
