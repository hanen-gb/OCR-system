"""
Sous-graphe LangGraph — Agent 1 : L'Extracteur

Flux séquentiel :
    START → detect_type
      ├── pdf_native      → extract_native (pdfplumber)
      └── image/pdf_scanned → extract_vision (OCR.space)
                                    ↓
                            extract_entities  (LLM texte — Sections I & III)
                                    ↓
                            extract_visual    (Gemini Vision — Section II)
                                    ↓
                                  merge
                                    ↓
                                   END
"""

import json
from typing import Literal

from langgraph.graph import StateGraph, START, END

from state import ExtractorState
from agents.extractor.tools import (
    detect_file_type,
    extract_text_pdf_native,
    extract_text_vision,
    extract_augmented_entities,
    extract_visual_fields,
)


# ── Nodes ──────────────────────────────────────────────────────────────────────

def detect_type_node(state: ExtractorState) -> dict:
    result = detect_file_type.invoke({"file_path": state["file_path"]})
    print(f"[GRAPH] file_type détecté : {result.get('file_type')}")
    return {
        "file_type": result.get("file_type"),
        "file_pages": result.get("pages", 1),
    }


def extract_native_node(state: ExtractorState) -> dict:
    raw_text = extract_text_pdf_native.invoke({"file_path": state["file_path"]})
    print(f"[GRAPH] PDF natif — texte extrait ({len(raw_text)} chars)")
    return {"raw_text": raw_text}


def extract_vision_node(state: ExtractorState) -> dict:
    raw_text = extract_text_vision.invoke({"image_path": state["file_path"]})
    print(f"[GRAPH] OCR.space — texte extrait ({len(raw_text)} chars)")
    print(f"[GRAPH] Aperçu texte : {raw_text[:300]}\n")
    return {"raw_text": raw_text}


def extract_entities_node(state: ExtractorState) -> dict:
    """Sections I & III — Extraction texte via LLM (articles, taxes, coordonnées, logistique)."""
    base_entities = state.get("base_entities") or {}
    document_type = state.get("document_type") or "auto"
    raw_text      = state.get("raw_text") or ""

    augmented_json = extract_augmented_entities.invoke({
        "raw_text": raw_text,
        "base_entities_json": json.dumps(base_entities, ensure_ascii=False),
        "document_type": document_type,
    })

    print(f"[GRAPH] LLM réponse brute (500 chars) : {augmented_json[:500]}\n")

    try:
        augmented = json.loads(augmented_json)
    except Exception:
        augmented = {"error": augmented_json[:300]}

    print(f"[GRAPH] Entités texte : {list(augmented.keys())}")
    return {"augmented_entities": augmented}


def extract_visual_node(state: ExtractorState) -> dict:
    """Section II — Analyse visuelle via Gemini Vision (tampons, signatures, manuscrit, état)."""
    document_type = state.get("document_type") or "auto"

    # Si document_type est "auto", on le déduit depuis augmented_entities
    augmented = state.get("augmented_entities") or {}
    doc_type_detected = augmented.get("_document_type", document_type)

    visual_json = extract_visual_fields.invoke({
        "image_path": state["file_path"],
        "document_type": doc_type_detected,
    })

    try:
        visual = json.loads(visual_json)
    except Exception:
        visual = {}

    # Si erreur Gemini → ne pas polluer le résultat final
    if "error" in visual or "visual_error" in visual:
        print(f"[GRAPH] Vision en erreur : {visual}")
        return {"visual_fields": {}}

    print(f"[GRAPH] Champs visuels Gemini : {visual}")
    return {"visual_fields": visual}


def merge_node(state: ExtractorState) -> dict:
    """
    Fusionne les 3 sources avec priorité :
      visual_fields > augmented_entities > base_entities
    Vision est plus fiable pour : tampons, signatures, et tableau des articles (colonnes QTE/PU).
    """
    base      = state.get("base_entities") or {}
    augmented = state.get("augmented_entities") or {}
    visual    = state.get("visual_fields") or {}

    complete = {**augmented, **visual, **base}

    # Articles : préfère la vision (lit les colonnes visuellement) sauf si vide
    vision_articles = visual.get("articles")
    text_articles   = augmented.get("articles")
    if vision_articles:
        complete["articles"] = vision_articles
        print(f"[GRAPH] Articles → vision ({len(vision_articles)} lignes) — override texte")
    elif text_articles:
        complete["articles"] = text_articles
        print(f"[GRAPH] Articles → texte ({len(text_articles)} lignes) — vision vide")

    print(f"[GRAPH] Merge — texte:{len(augmented)} | visuel:{len(visual)} | base:{len(base)} → total:{len(complete)}")
    return {"complete_entities": complete}


# ── Routing ─────────────────────────────────────────────────────────────────────

def route_extraction(state: ExtractorState) -> Literal["extract_native", "extract_vision"]:
    if state.get("file_type") == "pdf_native":
        return "extract_native"
    return "extract_vision"


# ── Graph Builder ───────────────────────────────────────────────────────────────

def build_extractor_graph():
    builder = StateGraph(ExtractorState)

    builder.add_node("detect_type",      detect_type_node)
    builder.add_node("extract_native",   extract_native_node)
    builder.add_node("extract_vision",   extract_vision_node)
    builder.add_node("extract_entities", extract_entities_node)
    builder.add_node("extract_visual",   extract_visual_node)
    builder.add_node("merge",            merge_node)

    builder.add_edge(START, "detect_type")
    builder.add_conditional_edges(
        "detect_type",
        route_extraction,
        {"extract_native": "extract_native", "extract_vision": "extract_vision"},
    )

    # Flux séquentiel : OCR → LLM texte → Gemini Vision → merge
    builder.add_edge("extract_native",   "extract_entities")
    builder.add_edge("extract_vision",   "extract_entities")
    builder.add_edge("extract_entities", "extract_visual")
    builder.add_edge("extract_visual",   "merge")
    builder.add_edge("merge",            END)

    return builder.compile()


extractor_graph = build_extractor_graph()
