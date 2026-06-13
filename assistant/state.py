from typing import TypedDict, Optional, Annotated, List

from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages


class ExtractorState(TypedDict):
    """
    État partagé de l'Agent Extracteur.

    Flux :
        file_path + document_type + base_entities
            → detect_type
            → extract_text (pdf_native OU vision)
            → extract_augmented_entities
            → merge
            → complete_entities
    """

    # ── Input ──────────────────────────────────────────────────────────────────
    file_path: str
    # "facture" | "lettre_de_change"
    document_type: Optional[str]
    # Entités déjà extraites par le modèle fine-tuné :
    #   Facture        → {fournisseur, client, num_facture, date_facture, montant_ttc}
    #   Lettre change  → {rib, tire, tireur, num_lettre, date_echeance, montant, domiciliation}
    base_entities: Optional[dict]

    # ── Étape 1 : Détection du type de fichier ─────────────────────────────────
    # "pdf_native" | "pdf_scanned" | "image"
    file_type: Optional[str]
    file_pages: Optional[int]

    # ── Étape 2 : Extraction du texte brut ────────────────────────────────────
    raw_text: Optional[str]

    # ── Étape 3a : Entités augmentées (texte OCR → LLM) ──────────────────────
    augmented_entities: Optional[dict]

    # ── Étape 3b : Champs visuels (image → Gemini Vision) ────────────────────
    # Section II : cachet, signature, notes manuscrites, état, logo
    visual_fields: Optional[dict]

    # ── Output final ──────────────────────────────────────────────────────────
    # Fusion : base_entities + augmented_entities + visual_fields
    complete_entities: Optional[dict]

    # ── LangGraph internal ────────────────────────────────────────────────────
    messages: Annotated[list[AnyMessage], add_messages]


class AuditorState(TypedDict):
    """
    État partagé de l'Agent Auditeur.

    Flux :
        complete_entities + base_entities
            → prepare       (résolution doc_type, doc_number)
            → arithmetic    (QTE × PU ≈ total_ht ligne par ligne)
            → tva           (Σ TVA lignes ≈ montant_tva global)
            → net           (HT + TVA + timbre ≈ net_a_payer)
            → doublon       (SQLite : N° déjà vu ?)
            → gouvernance   (signatures, tampons)
            → verdict       (status_validite final)
            → audit_report
    """

    # ── Input ─────────────────────────────────────────────────────────────────
    complete_entities : dict
    base_entities     : Optional[dict]

    # ── Préparation ───────────────────────────────────────────────────────────
    doc_type    : Optional[str]    # "facture" | "lettre_de_change"
    doc_number  : Optional[str]    # num_facture ou num_lettre
    fournisseur : Optional[str]
    montant_ttc : Optional[float]
    date_doc    : Optional[str]

    # ── Résultats des checks ───────────────────────────────────────────────────
    check_arithmetique   : Optional[List[dict]]
    check_tva            : Optional[dict]
    check_net            : Optional[dict]
    check_lettres        : Optional[dict]    # Couche 3 : cross-check lettres vs montant numérique
    check_doublon        : Optional[dict]
    check_gouvernance    : Optional[dict]
    # Traite-specific
    check_montant_traite : Optional[dict]   # Montant lettres vs chiffres
    check_echeance       : Optional[dict]   # Date d'échéance présente et valide

    # ── Output final ──────────────────────────────────────────────────────────
    status_validite     : Optional[str]    # VALIDÉ | ERREUR_CALCUL | ERREUR_TVA | DOUBLON | ...
    audit_report        : Optional[dict]

    # ── Notification email (Agent 2 — notifier.py) ────────────────────────────
    notification_sent   : Optional[bool]   # True si email envoyé avec succès
    notification_alerts : Optional[List[str]]  # Liste des raisons d'alerte


class AnalystState(TypedDict):
    """
    État partagé de l'Agent Analyste.

    Flux :
        complete_entities + audit_report
            → load_history     (500 derniers docs SQLite)
            → compute_stats    (stats fournisseur + globales)
            → detect_anomalies (montant déviant, nouveau fournisseur, montant élevé)
            → generate_insights (LLM 3-4 phrases)
            → verdict          (alert_level + rapport final)
            → analyst_report
    """

    # ── Input ─────────────────────────────────────────────────────────────────
    complete_entities : dict
    audit_report      : Optional[dict]

    # ── Données historiques ───────────────────────────────────────────────────
    historique        : Optional[List[dict]]

    # ── Statistiques ──────────────────────────────────────────────────────────
    stats_fournisseur : Optional[dict]
    stats_globales    : Optional[dict]

    # ── Anomalies détectées ───────────────────────────────────────────────────
    anomalies         : Optional[List[dict]]

    # ── Commentaire LLM ───────────────────────────────────────────────────────
    insights_text     : Optional[str]

    # ── Output final ──────────────────────────────────────────────────────────
    alert_level       : Optional[str]   # "NORMAL" | "ATTENTION" | "ALERTE"
    analyst_report    : Optional[dict]


class ChatbotState(TypedDict):
    """
    État partagé de l'Agent Chatbot.

    Flux :
        messages + context_*
            → understand_intent
            → [query_db]          ← si intent = "base_donnees"
            → generate_response
    """

    # ── Conversation ─────────────────────────────────────────────────────────
    messages          : Annotated[list[AnyMessage], add_messages]

    # ── Contexte injecté ─────────────────────────────────────────────────────
    context_entities  : Optional[dict]
    context_audit     : Optional[dict]
    context_analyst   : Optional[dict]
    db_context        : Optional[List[dict]]

    # ── Routing interne ───────────────────────────────────────────────────────
    intent            : Optional[str]   # "document" | "base_donnees"

    # ── Output ───────────────────────────────────────────────────────────────
    response          : Optional[str]
