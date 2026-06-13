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
           lettres       ← Couche 3 : net_a_payer_lettres vs net_a_payer numérique
              ↓
           doublon       ← SQLite : N° déjà vu en base ?
              ↓
          gouvernance    ← Signatures, tampons, aval
              ↓
           verdict       ← Status final
              ↓
        notification     ← Email si montant > seuil ou échéance proche
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
    check_net_lettres,
    check_montant_traite,
    check_echeance_traite,
)
from agents.auditor.db import check_doublon, register_document
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
                # Gère virgule décimale et espaces milliers ("135,660" → 135.660)
                if isinstance(v, str):
                    v = v.strip().replace(" ", "").replace(" ", "")
                    # Point + 3 chiffres = millimes tunisiens → garder (135.660)
                    # Virgule = séparateur décimal → convertir en point
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
    Détecte une valeur monétaire hallucinée par le LLM.
    Trois cas :
      1. Nombre répétitif : 333333, 111111, 999999…
      2. Valeur > 10× la somme réelle des lignes d'articles
      3. Valeur > 5× montant_ht global (si disponible)
    """
    if value is None:
        return False
    # Cas 1 — chiffres répétitifs
    s = str(int(abs(value)))
    if len(s) >= 4 and len(set(s)) == 1:
        return True
    # Cas 2 — aberration vs articles réels
    total_lignes = sum(
        float(a["total_ht_ligne"])
        for a in articles
        if a.get("total_ht_ligne") is not None
    )
    if total_lignes > 0 and value > total_lignes * 10:
        return True
    # Cas 3 — aberration vs montant_ht global (factures services sans articles)
    if montant_ht is not None and montant_ht > 0 and value > montant_ht * 5:
        return True
    return False


# ── Nœuds ─────────────────────────────────────────────────────────────────────

def prepare_node(state: AuditorState) -> dict:
    """Résout doc_type, doc_number, fournisseur, montant_ttc depuis les entités."""
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
        # Accepte les clés MAJUSCULES (GLM editedMap) ET minuscules (Agent 1)
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

    # Rejeter les valeurs hallucinées (333333, valeur >> articles ou >> montant_ht)
    articles_prepare = entities.get("articles") or []
    montant_ht_prepare = _num(entities, "montant_ht")
    if _is_hallucinated(montant_ttc, articles_prepare, montant_ht_prepare):
        print(f"[AUDITEUR] Valeur hallucinée détectée ({montant_ttc}) → ignorée, montant_ttc=null")
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
    """Routing conditionnel : traite → chemin simplifié, facture → chemin arithmétique complet."""
    doc_type = state.get("doc_type") or ""
    if "lettre" in doc_type or "change" in doc_type or "traite" in doc_type:
        return "traite"
    return "facture"


def montant_traite_node(state: AuditorState) -> dict:
    """Cross-check montant en lettres vs montant numérique pour une lettre de change."""
    entities = state.get("complete_entities") or {}
    montant_chiffres = state.get("montant_ttc")
    montant_lettres  = entities.get("montant_en_lettres") or entities.get("notes_manuscrites")
    result = check_montant_traite(montant_chiffres, montant_lettres)
    print(f"[AUDITEUR/TRAITE] Montant lettres : {result.get('status')}")
    return {"check_montant_traite": result}


def echeance_node(state: AuditorState) -> dict:
    """Vérifie la date d'échéance de la lettre de change."""
    base     = state.get("base_entities") or {}
    entities = state.get("complete_entities") or {}
    date_ech = (_str(base, "DATE_ECHEANCE", "date_echeance") or _str(entities, "date_echeance"))
    result   = check_echeance_traite(date_ech)
    print(f"[AUDITEUR/TRAITE] Échéance : {result.get('status')} ({date_ech})")
    return {"check_echeance": result}


def arithmetic_node(state: AuditorState) -> dict:
    """Vérifie QTE × PU_HT ≈ Total_HT pour chaque ligne d'article."""
    articles = (state.get("complete_entities") or {}).get("articles") or []
    result   = check_arithmetic_lines(articles)
    nb_err   = sum(1 for r in result if r["status"] == "ERREUR")
    print(f"[AUDITEUR] Arithmétique : {len(result)} lignes, {nb_err} erreurs")
    return {"check_arithmetique": result}


def tva_node(state: AuditorState) -> dict:
    """Vérifie Σ TVA lignes ≈ montant_tva global.
    Fallback 1 : si tva_rate_ligne absent → injecte tva_rate global.
    Fallback 2 : si tva_rate aberrant → recalcule depuis montant_tva / montant_ht.
    """
    entities    = state.get("complete_entities") or {}
    articles    = entities.get("articles") or []
    montant_tva = _num(entities, "montant_tva")

    # Calcul automatique de montant_tva si absent (Agent 1 l'a manqué)
    # Formule : HT × taux_tva — si HT global ou somme articles + taux disponibles
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
                print(f"[AUDITEUR] montant_tva null → calculé : {ht_base} × {t*100:.1f}% = {montant_tva}")
            except (ValueError, TypeError):
                pass

    # Validation du taux TVA global : si aberrant, recalculer depuis montant_tva/montant_ht
    taux_global_raw = entities.get("tva_rate")
    if taux_global_raw is not None:
        try:
            taux_val = float(str(taux_global_raw))
            TAUX_CONNUS = {7, 13, 19, 20, 25}
            if taux_val not in TAUX_CONNUS:
                # Tentative de recalcul depuis les montants globaux
                mht = _num(entities, "montant_ht") or _num(entities, "montant_ht_ar") or _num(entities, "net_htva")
                mtva = _num(entities, "montant_tva")
                if mht and mtva and mht > 0:
                    taux_recalc = round(mtva / mht * 100, 1)
                    # Arrondir au taux connu le plus proche
                    taux_corrige = min(TAUX_CONNUS, key=lambda t: abs(t - taux_recalc))
                    if abs(taux_recalc - taux_corrige) < 3:
                        print(f"[AUDITEUR] tva_rate aberrant ({taux_val}%) → corrigé à {taux_corrige}% (recalc={taux_recalc}%)")
                        taux_global_raw = str(taux_corrige)
        except (ValueError, TypeError):
            pass

    # Fallback : si aucune ligne n'a de taux TVA, injecter le taux global
    taux_ligne_absents = all(a.get("tva_rate_ligne") is None for a in articles)
    if taux_ligne_absents and articles and taux_global_raw is not None:
        taux_global = str(taux_global_raw).replace("%", "").strip()
        articles = [
            {**a, "tva_rate_ligne": taux_global}
            for a in articles
            if a.get("total_ht_ligne") is not None
        ]
        print(f"[AUDITEUR] tva_rate_ligne absent → taux global '{taux_global}%' injecté sur {len(articles)} ligne(s)")

    # Remise globale : distribuer proportionnellement sur les lignes avant calcul TVA
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
                print(f"[AUDITEUR] Remise globale {remise_globale} → ratio {remise_ratio:.4f} distribué sur {len(articles)} ligne(s)")
        except (TypeError, ValueError):
            pass

    result = validate_tva_globale(articles, montant_tva)
    print(f"[AUDITEUR] TVA : {result.get('status')} (écart={result.get('ecart')})")
    return {"check_tva": result}


def net_node(state: AuditorState) -> dict:
    """Vérifie HT + TVA + Timbre ≈ net_a_payer (TTC)."""
    entities = state.get("complete_entities") or {}

    montant_ht = _num(entities, "montant_ht")

    # Fallback 1 : montant_ht_ar (après remise) si montant_ht absent
    if montant_ht is None:
        montant_ht = _num(entities, "montant_ht_ar")
        if montant_ht:
            print(f"[AUDITEUR] montant_ht → depuis montant_ht_ar : {montant_ht}")

    # Fallback 2 : somme des articles si toujours null
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
                print(f"[AUDITEUR] montant_ht → reconstitué depuis articles : {montant_ht}")
        except (TypeError, ValueError):
            pass

    # Fallback 3 (rétro-calcul) : HT = TTC - TVA - Timbre — quand tout le reste est null
    if montant_ht is None and state.get("montant_ttc") is not None:
        try:
            tva_rc    = _num(entities, "montant_tva") or 0
            timbre_rc = _num(entities, "timbre_fiscal") or 0
            fodec_rc  = _num(entities, "fodec") or 0
            retro     = round(float(state["montant_ttc"]) - tva_rc - timbre_rc - fodec_rc, 3)
            if retro > 0:
                montant_ht = retro
                print(f"[AUDITEUR] montant_ht rétro-calculé : TTC-TVA-Timbre = {montant_ht}")
        except (TypeError, ValueError):
            pass

    # montant_tva : utiliser la valeur extraite ou la calculer depuis HT × taux
    montant_tva_net = _num(entities, "montant_tva")
    if montant_tva_net is None and montant_ht is not None and entities.get("tva_rate") is not None:
        try:
            t = float(str(entities["tva_rate"]).replace("%", "").strip())
            if t > 1: t /= 100
            montant_tva_net = round(montant_ht * t, 3)
            print(f"[AUDITEUR/net] montant_tva calculé pour check_net : {montant_tva_net}")
        except (ValueError, TypeError):
            pass

    result = check_net_a_payer(
        montant_ht    = montant_ht,
        montant_tva   = montant_tva_net,
        timbre_fiscal = _num(entities, "timbre_fiscal"),
        net_extrait   = state.get("montant_ttc"),
        fodec         = _num(entities, "fodec"),
        net_htva      = _num(entities, "net_htva"),
    )
    print(f"[AUDITEUR] Net à payer : {result.get('status')} (écart={result.get('ecart')})")
    return {"check_net": result}


def lettres_node(state: AuditorState) -> dict:
    """
    Couche 3 — cross-check net_a_payer_lettres vs net_a_payer numérique.
    Le texte en lettres est l'ancre de vérité (pas d'ambiguïté de séparateur décimal).
    Un écart > 500 millimes signale une erreur de parsing dans Agent 1.
    """
    entities            = state.get("complete_entities") or {}
    net_a_payer         = _num(entities, "net_a_payer")
    net_a_payer_lettres = entities.get("net_a_payer_lettres")

    result = check_net_lettres(net_a_payer, net_a_payer_lettres)
    print(f"[AUDITEUR] Lettres : {result.get('status')} | écart={result.get('ecart')} DT")
    return {"check_lettres": result}


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
    entities    = state.get("complete_entities") or {}
    doc_type    = state.get("doc_type") or ""
    is_traite   = "lettre" in doc_type or "change" in doc_type or "traite" in doc_type

    # Enregistrement commun
    def _register_if_new():
        if doublon.get("status") == "NOUVEAU" and state.get("doc_number"):
            register_document(
                doc_type    = doc_type or "facture",
                doc_number  = state["doc_number"],
                fournisseur = state.get("fournisseur"),
                montant     = state.get("montant_ttc"),
                date_doc    = state.get("date_doc"),
            )

    # ── Chemin traite ──────────────────────────────────────────────────────────
    if is_traite:
        montant_traite = state.get("check_montant_traite") or {}
        echeance       = state.get("check_echeance") or {}

        if doublon.get("status") == "DOUBLON":
            status = "DOUBLON"
        elif gouvernance.get("status") == "MANQUANT":
            status = "SIGNATURE_MANQUANTE"
        elif montant_traite.get("status") == "ERREUR_MONTANT":
            status = "ERREUR_MONTANT_LETTRES"
        elif echeance.get("status") == "DEPASSEE":
            status = "ECHEANCE_DEPASSEE"
        else:
            status = "VALIDÉ"

        _register_if_new()
        rapport = {
            "status_validite"    : status,
            "doc_type"           : doc_type,
            "doc_number"         : state.get("doc_number"),
            "fournisseur"        : state.get("fournisseur"),  # = tireur
            "check_montant_traite": montant_traite,
            "check_echeance"     : echeance,
            "gouvernance"        : gouvernance,
            "alerte_doublon"     : doublon,
        }
        print(f"[AUDITEUR/TRAITE] Verdict : {status}")
        return {"status_validite": status, "audit_report": rapport}

    # ── Chemin facture ─────────────────────────────────────────────────────────
    arithmetique = state.get("check_arithmetique") or []
    tva          = state.get("check_tva") or {}
    net          = state.get("check_net") or {}
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
    elif tva.get("status") == "ERREUR":
        status = "ERREUR_TVA"
    elif net.get("status") == "ERREUR":
        status = "ERREUR_NET_A_PAYER"
    elif lettres.get("status") == "ERREUR_MONTANT":
        status = "ERREUR_MONTANT_LETTRES"
    else:
        status = "VALIDÉ"

    _register_if_new()

    document_incomplet = (
        _num(entities, "montant_ht")  is None and
        _num(entities, "montant_tva") is None and
        state.get("montant_ttc")      is None and
        len(articles) > 0
    )
    if document_incomplet:
        print("[AUDITEUR] Document potentiellement tronqué — bloc totaux absent")

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
        "validation_tva_globale"    : tva,
        "conformite_net_a_payer"    : net,
        "check_lettres_vs_net"      : lettres,
        "gouvernance"               : gouvernance,
        "alerte_doublon"            : doublon,
    }

    print(f"[AUDITEUR] Verdict final : {status}")
    return {"status_validite": status, "audit_report": rapport}


def notification_node(state: AuditorState) -> dict:
    """
    Vérifie les conditions d'alerte et envoie un email si nécessaire.

    Conditions déclenchantes :
      1. Montant TTC > ALERT_THRESHOLD_DT  (défaut 5 000 DT)
      2. Date d'échéance dans ≤ ALERT_DEADLINE_DAYS jours (défaut 7) ou dépassée
    """
    entities    = state.get("complete_entities") or {}
    base        = state.get("base_entities") or {}
    montant_ttc = state.get("montant_ttc")
    doc_type    = state.get("doc_type")
    is_traite   = "lettre" in (doc_type or "")

    # Récupère la date d'échéance selon le type de document
    if is_traite:
        date_echeance = state.get("date_doc")  # prepare_node l'a mis depuis base_entities
    else:
        date_echeance = (
            _str(entities, "date_echeance")
            or _str(base, "date_echeance")
        )

    alerts = check_alert_conditions(montant_ttc, date_echeance)

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
        print("[NOTIFIER] Aucune condition d'alerte déclenchée")

    # Enrichit audit_report avec le résultat de la notification
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
    # Facture path
    builder.add_node("arithmetic",     arithmetic_node)
    builder.add_node("tva",            tva_node)
    builder.add_node("net",            net_node)
    builder.add_node("lettres",        lettres_node)
    # Traite path
    builder.add_node("montant_traite", montant_traite_node)
    builder.add_node("echeance",       echeance_node)
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
    builder.add_edge("arithmetic",     "tva")
    builder.add_edge("tva",            "net")
    builder.add_edge("net",            "lettres")
    builder.add_edge("lettres",        "doublon")
    # Traite path
    builder.add_edge("montant_traite", "echeance")
    builder.add_edge("echeance",       "doublon")
    # Common
    builder.add_edge("doublon",        "gouvernance")
    builder.add_edge("gouvernance",    "verdict")
    builder.add_edge("verdict",        "notification")
    builder.add_edge("notification",   END)

    return builder.compile()


auditor_graph = build_auditor_graph()
