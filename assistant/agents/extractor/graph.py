"""
Sous-graphe LangGraph — Agent 1 : L'Extracteur

Sequential flow:
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
import re as _re
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
    print(f"[GRAPH] file_type detected: {result.get('file_type')}")
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
    print(f"[GRAPH] Text preview: {raw_text[:300]}\n")
    return {"raw_text": raw_text}


def extract_entities_node(state: ExtractorState) -> dict:
    """Sections I & III — text extraction with an LLM (items, taxes, contact details, logistics)."""
    base_entities = state.get("base_entities") or {}
    document_type = state.get("document_type") or "auto"
    raw_text      = state.get("raw_text") or ""

    augmented_json = extract_augmented_entities.invoke({
        "raw_text": raw_text,
        "base_entities_json": json.dumps(base_entities, ensure_ascii=False),
        "document_type": document_type,
    })

    print(f"[GRAPH] Raw LLM answer (500 chars): {augmented_json[:500]}\n")

    try:
        augmented = json.loads(augmented_json)
    except Exception:
        augmented = {"error": augmented_json[:300]}

    print(f"[GRAPH] Text entities: {list(augmented.keys())}")
    return {"augmented_entities": augmented}


def extract_visual_node(state: ExtractorState) -> dict:
    """Section II — visual analysis with a vision model (stamps, signatures, handwriting, condition)."""
    document_type = state.get("document_type") or "auto"

    # If document_type is "auto", infer it from augmented_entities
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

    # On a vision-model error → do not pollute the final result
    if "error" in visual or "visual_error" in visual:
        print(f"[GRAPH] Vision error: {visual}")
        return {"visual_fields": {}}

    print(f"[GRAPH] Visual fields: {visual}")
    return {"visual_fields": visual}


def merge_node(state: ExtractorState) -> dict:
    """
    Merges the 3 sources with this priority:
      visual_fields > augmented_entities > base_entities
    Vision is more reliable for: stamps, signatures and the item table (QTY/unit price columns).
    """
    base      = state.get("base_entities") or {}
    augmented = state.get("augmented_entities") or {}
    visual    = state.get("visual_fields") or {}

    complete = {**augmented, **visual, **base}

    # Items: prefer vision (reads the columns visually) unless empty
    vision_articles = visual.get("articles")
    text_articles   = augmented.get("articles")
    if vision_articles:
        complete["articles"] = vision_articles
        print(f"[GRAPH] Items → vision ({len(vision_articles)} lines) — overrides text")
    elif text_articles:
        complete["articles"] = text_articles
        print(f"[GRAPH] Items → text ({len(text_articles)} lines) — vision empty")

    # ── Layer 2: smart amount normalisation (parse_amount) ───────────────────────────
    # Handles 6 frequent confusion cases in Tunisian documents:
    #   1. Thousands spaces + decimal dot    : "1 320.600" → 1320.600
    #   2. European comma + dot format       : "1.320,600" → 1320.600
    #   3. US/mixed decimal-dot format       : "4,498.800" → 4498.800
    #   4. Double point tunisien             : "1.320.600" → 1320.600
    #   5. Comma alone as decimal separator  : "1320,600"  → 1320.600
    #   6. Integer without decimals (OCR)    :  4750       → 4.750
    # IMPORTANT — had_decimal :
    #   If the original string already contains a separator (comma or dot),
    #   the amount has EXPLICIT decimals (e.g. "20 754,000" = 20,754 TND).
    #   It is NEVER divided by 1000 in that case, even if the value is >= 10,000.
    #   Division by 1000 only applies to PURE integers (no separator).
    def _normalize_amount(val, field: str = "", net_ref: float | None = None,
                          allow_int_fix: bool = True) -> float | None:
        if val is None:
            return None

        had_decimal = False

        if not isinstance(val, (int, float)):
            s = str(val).strip()
            for sp in (' ', ' ', ' ', ' ', ' '):
                s = s.replace(sp, '')
            had_decimal = (',' in s) or ('.' in s)
            if ',' in s and '.' in s:
                # The RIGHT-most separator is the decimal one, the other one is the thousands separator.
                # "1.320,600" (EU, virgule decimale) vs "4,498.800" (US/mixte, point decimal)
                if s.rfind(',') > s.rfind('.'):
                    s = s.replace('.', '').replace(',', '.'  )
                else:
                    s = s.replace(',', ''  )
            elif ',' in s:
                s = s.replace(',', '.'  )
            elif s.count('.') == 2:
                idx = s.rfind('.'  )
                s = s[:idx].replace('.', '') + '.'  + s[idx+1:]
            try:
                f = float(s)
            except (ValueError, TypeError):
                return None
        else:
            f = float(val)

        if not allow_int_fix:
            return round(f, 3)

        is_int = (not had_decimal) and (f > 0) and (f == round(f))

        if field == "timbre_fiscal" and is_int and 30 < f < 50000:
            restored = round(f / 1000, 3)
            print(f"[PARSER] timbre_fiscal: {int(f)} > 30 DT -> {restored} (div1000)")
            return restored

        if is_int:
            candidate = round(f / 1000, 3)
            should_divide = False
            if net_ref is not None and net_ref > 0:
                if f > net_ref and 0 < candidate <= net_ref * 1.1:
                    should_divide = True
            else:
                if f >= 100000:
                    should_divide = True
            if should_divide:
                print(f"[PARSER] {field}: {int(f)} -> {candidate}")
                return candidate

        if f > 100000:
            print(f"[PARSER] Warning {field}: value {f} > 100,000 TND")

        return round(f, 3)

    lettres = (complete.get("net_a_payer_lettres") or "").upper()
    grandes_valeurs = any(m in lettres for m in ["MILLION", "MILLIARD"])
    allow_div1000 = not grandes_valeurs

    # 1. net_a_payer first → used as the anchor for the dependent fields
    if complete.get("net_a_payer") is not None:
        complete["net_a_payer"] = _normalize_amount(
            complete["net_a_payer"], "net_a_payer", allow_int_fix=allow_div1000
        )
    net_ref = complete.get("net_a_payer")

    # ×1000 correction for net_a_payer: "24.000 DT" read as the integer 24000
    # Condition: the amount in words does not contain "MILLE/MILLIER" AND the value is an integer ≥ 1000
    if (net_ref is not None and net_ref >= 1000 and net_ref == round(net_ref)
            and lettres
            and not any(m in lettres for m in ["MILLE", "MILLIER", "THOUSAND", "ألف"])):
        corrected = round(net_ref / 1000, 3)
        if corrected < 100000:
            print(f"[PARSER] net_a_payer ×1000 corrected: {net_ref} → {corrected} (words='{lettres[:60]}')")
            complete["net_a_payer"] = corrected
            net_ref = corrected

    # 2. Dependent amounts, using net_ref as a plausibility anchor
    for field in ("montant_tva", "montant_ht", "fodec", "net_htva"):
        if complete.get(field) is not None:
            complete[field] = _normalize_amount(
                complete[field], field, net_ref=net_ref, allow_int_fix=allow_div1000
            )

    # 3. timbre_fiscal: always with int_fix=True (max 2 TND, independent of the document size)
    if complete.get("timbre_fiscal") is not None:
        complete["timbre_fiscal"] = _normalize_amount(
            complete["timbre_fiscal"], "timbre_fiscal", allow_int_fix=True
        )

    # 4. Item fields (prix_unitaire_ht, total_ht_ligne)
    articles_list = complete.get("articles") or []
    for art in articles_list:
        for f_art in ("prix_unitaire_ht", "total_ht_ligne"):
            if art.get(f_art) is not None:
                art[f_art] = _normalize_amount(
                    art[f_art], f_art, net_ref=net_ref, allow_int_fix=allow_div1000
                )
    if articles_list:
        complete["articles"] = articles_list

    # ── GPS coordinates detected in the address fields ───────────────────────────
    # Some telecom operators print the subscriber's GPS coordinates
    GPS_PATTERN = _re.compile(r'^-?\d{1,3}\.\d{4,}[,;]\s*-?\d{1,3}\.\d{4,}')
    for addr_field in ("adresse_client", "adresse_fournisseur"):
        val = complete.get(addr_field)
        if val and isinstance(val, str) and GPS_PATTERN.match(val.strip()):
            print(f"[GRAPH] {addr_field}: GPS coordinates detected → rejected")
            complete[addr_field] = None

    # ── timbre_fiscal check: fallback — if still > 50 TND after normalisation ──
    timbre = complete.get("timbre_fiscal")
    if timbre is not None:
        try:
            if float(timbre) > 50:
                print(f"[GRAPH] timbre_fiscal aberrant ({timbre} DT) → null")
                complete["timbre_fiscal"] = None
        except (ValueError, TypeError):
            pass

    # ── Clean textual "null" values (the LLM writes "null" instead of JSON null) ──
    # The LLM sometimes returns the string "null" instead of an absent value.
    for key in list(complete.keys()):
        if complete[key] == "null" or complete[key] == "None":
            complete[key] = None

    # ── numero_facture check: reject it if it is an address or a long text ─
    num = complete.get("numero_facture")
    if num and isinstance(num, str):
        num_stripped = num.strip()
        mots = num_stripped.split()
        # More than 4 words or address words → probably an error
        MOTS_ADRESSE = {"rue", "avenue", "av", "bd", "imm", "im", "sibo", "zone", "zi",
                        "poudriere", "quartier", "km", "bp", "route", "sfax", "tunis",
                        "sousse", "el", "ben", "sidi"}
        est_adresse = len(mots) > 4 or any(m.lower() in MOTS_ADRESSE for m in mots)
        if est_adresse:
            # Look for a real invoice number inside the string
            match = _re.search(r'\b[A-Z0-9]{6,20}\b', num_stripped.replace(" ", ""))
            if match:
                complete["numero_facture"] = match.group()
                print(f"[GRAPH] numero_facture corrected: '{num}' → '{match.group()}'")
            else:
                complete["numero_facture"] = None
                print(f"[GRAPH] numero_facture rejected (address): '{num}'")

    # ── Automatic currency correction from net_a_payer_lettres ──────────────────
    # The LLM sometimes hallucinates "DT" even on invoices in euros.
    # The net_a_payer_lettres field contains the actual currency written in words.
    lettres = (complete.get("net_a_payer_lettres") or "").upper()
    raw_text = (state.get("raw_text") or "").upper()

    # Priority 1a: explicit EUR/USD/DH in the OCR text (overrides everything)
    # Uses the \b regex boundary to avoid false positives ("CAPTEUR" contains "EUR" as a substring)
    # NOTE : \bCENTIMES?\b intentionnellement ABSENT — en Tunisie "CENTIMES" = millimes (usage
    #        French usage), not a EUR currency indication; it would cause false positives.
    EUR_PATTERNS = [r'\bEUR\b', r'€', r'\bEUROS?\b', r'\bSIRET\b', r'\bTVA INTRA\b',
                    r'RCS DE PARIS']
    if any(_re.search(p, raw_text) for p in EUR_PATTERNS):
        complete["devise"] = "EUR"
    elif any(w in raw_text for w in ["USD", "DOLLAR", " $ "]):
        complete["devise"] = "USD"
    elif any(w in raw_text for w in ["MAD", "DIRHAM", "DH "]):
        complete["devise"] = "DH"
    # Priority 1b: explicit DT/TND in the Tunisian OCR text
    elif any(w in raw_text for w in ["MONTANT (DT)", "EN DT TTC", "بالدينار",
                                      "المبلغ بالدينار", "DT TTC", "EN DT)", " TND",
                                      "TND\n", "(TND)", "EN TND"]):
        complete["devise"] = "DT"
    # Priority 2: currency from net_a_payer_lettres (fallback — less reliable)
    elif lettres:
        if any(w in lettres for w in ["EURO", "EUR"]):
            complete["devise"] = "EUR"
        elif any(w in lettres for w in ["DOLLAR", "USD"]):
            complete["devise"] = "USD"
        elif any(w in lettres for w in ["DIRHAM", "MAD"]):
            complete["devise"] = "DH"
        elif any(w in lettres for w in ["DINAR", "TND"]):
            complete["devise"] = "DT"

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

    # Sequential flow: OCR → text LLM → vision model → merge
    builder.add_edge("extract_native",   "extract_entities")
    builder.add_edge("extract_vision",   "extract_entities")
    builder.add_edge("extract_entities", "extract_visual")
    builder.add_edge("extract_visual",   "merge")
    builder.add_edge("merge",            END)

    return builder.compile()


extractor_graph = build_extractor_graph()
