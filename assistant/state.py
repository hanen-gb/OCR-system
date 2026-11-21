from typing import TypedDict, Optional, Annotated, List

from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages


class ExtractorState(TypedDict):
    """
    Shared state of the Extractor Agent.

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
    # Entities already extracted by the fine-tuned model:
    #   Facture        → {fournisseur, client, num_facture, date_facture, montant_ttc}
    #   Bill of exchange → {rib, tire, tireur, num_lettre, date_echeance, montant, domiciliation}
    base_entities: Optional[dict]

    # ── Step 1: file type detection ────────────────────────────────────────────
    # "pdf_native" | "pdf_scanned" | "image"
    file_type: Optional[str]
    file_pages: Optional[int]

    # ── Step 2: raw text extraction ───────────────────────────────────────────
    raw_text: Optional[str]

    # ── Step 3a: augmented entities (OCR text → LLM) ─────────────────────────
    augmented_entities: Optional[dict]

    # ── Step 3b: visual fields (image → vision model) ────────────────────────
    # Section II: stamp, signature, handwritten notes, condition, logo
    visual_fields: Optional[dict]

    # ── Output final ──────────────────────────────────────────────────────────
    # Fusion : base_entities + augmented_entities + visual_fields
    complete_entities: Optional[dict]

    # ── LangGraph internal ────────────────────────────────────────────────────
    messages: Annotated[list[AnyMessage], add_messages]


class AuditorState(TypedDict):
    """
    Shared state of the Auditor Agent.

    Flux :
        complete_entities + base_entities
            → prepare       (resolves doc_type, doc_number)
            → arithmetic    (QTY × unit price ≈ line total, line by line)
            → tva           (Σ TVA lignes ≈ montant_tva global)
            → net           (HT + TVA + timbre ≈ net_a_payer)
            → doublon       (PostgreSQL: number already seen?)
            → gouvernance   (signatures, tampons)
            → verdict       (status_validite final)
            → audit_report
    """

    # ── Input ─────────────────────────────────────────────────────────────────
    complete_entities : dict
    base_entities     : Optional[dict]

    # ── Preparation ───────────────────────────────────────────────────────────
    doc_type    : Optional[str]    # "facture" | "lettre_de_change"
    doc_number  : Optional[str]    # num_facture or num_lettre
    fournisseur : Optional[str]
    montant_ttc : Optional[float]
    date_doc    : Optional[str]

    # ── Check results ──────────────────────────────────────────────────────────
    check_arithmetique   : Optional[List[dict]]
    check_tva            : Optional[dict]
    check_net            : Optional[dict]
    check_lettres        : Optional[dict]    # Layer 3: amount in words vs numeric amount
    check_doublon        : Optional[dict]
    check_gouvernance    : Optional[dict]
    # Traite-specific
    check_montant_traite : Optional[dict]   # Amount in words vs figures
    check_echeance       : Optional[dict]   # Due date present and valid
    check_rib            : Optional[dict]   # RIB bancaire — 20 chiffres requis

    # ── Output final ──────────────────────────────────────────────────────────
    status_validite     : Optional[str]    # VALIDÉ | ERREUR_CALCUL | ERREUR_TVA | DOUBLON | ... (status codes)
    audit_report        : Optional[dict]

    # ── Notification email (Agent 2 — notifier.py) ────────────────────────────
    notification_sent   : Optional[bool]   # True if the e-mail was sent successfully
    notification_alerts : Optional[List[str]]  # List of alert reasons


class AnalystState(TypedDict):
    """
    Shared state of the Analyst Agent.

    Flux :
        complete_entities + audit_report
            → load_history     (500 derniers docs PostgreSQL)
            → compute_stats    (stats fournisseur + globales)
            → detect_anomalies (deviating amount, new supplier, high amount)
            → generate_insights (LLM 3-4 phrases)
            → verdict          (alert_level + rapport final)
            → analyst_report
    """

    # ── Input ─────────────────────────────────────────────────────────────────
    complete_entities : dict
    audit_report      : Optional[dict]

    # ── Historical data ───────────────────────────────────────────────────────
    historique        : Optional[List[dict]]

    # ── Statistiques ──────────────────────────────────────────────────────────
    stats_fournisseur : Optional[dict]
    stats_globales    : Optional[dict]

    # ── Detected anomalies ────────────────────────────────────────────────────
    anomalies         : Optional[List[dict]]

    # ── Commentaire LLM ───────────────────────────────────────────────────────
    insights_text     : Optional[str]

    # ── Output final ──────────────────────────────────────────────────────────
    alert_level       : Optional[str]   # "NORMAL" | "ATTENTION" | "ALERTE"
    analyst_report    : Optional[dict]


class ChatbotState(TypedDict):
    """
    Shared state of the Chatbot Agent.

    Flux :
        messages + context_*
            → understand_intent
            → [query_db]          ← si intent = "base_donnees"
            → generate_response
    """

    # ── Conversation ─────────────────────────────────────────────────────────
    messages          : Annotated[list[AnyMessage], add_messages]

    # ── Injected context ─────────────────────────────────────────────────────
    context_entities  : Optional[dict]
    context_audit     : Optional[dict]
    context_analyst   : Optional[dict]
    db_context        : Optional[List[dict]]

    # ── Routing interne ───────────────────────────────────────────────────────
    intent            : Optional[str]   # "document" | "base_donnees"

    # ── Output ───────────────────────────────────────────────────────────────
    response          : Optional[str]
