# Agents backend — LangGraph multi-agent pipeline

FastAPI service (port 8002) that runs four LangGraph agents on top of the fields extracted by the fine-tuned GLM-OCR
models. It completes the extraction, audits the document deterministically, analyses it against the history stored
in PostgreSQL and answers questions about it.

```
POST /analyse
   │
   ├─▶ Agent 1 — Extractor   (OCR / native PDF + LLM + vision model)   → complete_entities
   ├─▶ Agent 2 — Auditor     (pure Python, no LLM)                     → audit_report, status_validite
   ├─▶ Agent 3 — Analyst     (statistics + LLM comment)                → analyst_report, alert_level
   └─▶ PostgreSQL            (documents, factures, traites)

POST /chat ─▶ Agent 4 — Chatbot (document context + database queries)
```

## Agent 1 — Extractor ([`agents/extractor/`](agents/extractor/))

`detect_type → extract_native | extract_vision → extract_entities → extract_visual → merge`

| Node | What it does |
|---|---|
| `detect_type` | Native PDF, scanned PDF or image |
| `extract_native` | Text and tables of native PDFs with pdfplumber |
| `extract_vision` | OCR with OCR.space; vision-LLM fallback |
| `extract_entities` | 30+ complementary fields with an LLM: items (quantity, unit price, line total), VAT, FODEC tax, stamp duty, amount in words, contact details, payment terms; for bills of exchange: amount in words, RIB, place of issue, endorsements |
| `extract_visual` | Vision model: stamps, signatures, bank guarantee, handwritten notes, document condition, logo |
| `merge` | Merges the three sources (vision preferred for stamps, signatures and item tables) and normalises amounts: thousands separators, decimal commas, Tunisian millimes (e.g. `1 320,600` → 1320.600) |

LLM chain with automatic fallback: Groq (Qwen3-32B, then Llama 3.1 8B on HTTP 413) → Hugging Face Inference → Gemini
→ OpenAI (last resort). Vision: Groq Llama 4 Scout → Gemini. The prompts are written in French on purpose: the
documents are French/Arabic and the prompts quote the exact labels printed on them.

## Agent 2 — Auditor ([`agents/auditor/`](agents/auditor/))

Fully deterministic (no LLM): the same input always gives the same verdict.

```
prepare ─┬─ invoice ─▶ arithmetic ─▶ lettres ──────────────────┐
         └─ bill     ─▶ montant_traite ─▶ echeance ─▶ rib ─────┤
                                                               ▼
                                     doublon ─▶ gouvernance ─▶ verdict ─▶ notification
```

| Check | Rule | Tolerance |
|---|---|---|
| `arithmetic` | quantity × unit price × (1 − discount) = line total, per item | 0.005 TND (5 millimes) |
| `lettres` | amount written in French words (parsed) = numeric net amount payable | 0.5 TND |
| `montant_traite` | amount in words = amount in figures (bills of exchange) | 0.5 TND |
| `echeance` | due date present and not passed | — |
| `rib` | bank identifier has exactly 20 digits (Tunisian format) | — |
| `doublon` | same document number already stored in PostgreSQL | — |
| `gouvernance` | signature and/or stamp present | — |

Final status (first matching rule wins) — the codes are part of the API and are kept in French:

| Invoices | Bills of exchange |
|---|---|
| `DOUBLON` → `SIGNATURE_MANQUANTE` → `ERREUR_CALCUL` → `ERREUR_MONTANT_LETTRES` → `VALIDÉ` | `DOUBLON` → `SIGNATURE_MANQUANTE` → `ERREUR_MONTANT_LETTRES` → `ECHEANCE_DEPASSEE` → `ERREUR_RIB` → `VALIDÉ` |

`notification` sends an e-mail when a due date is close or passed, when the amount is far above the history of the
same document type, or when a new document has a high amount (thresholds in `.env`). A daily summary is sent at 8:00.

## Agent 3 — Analyst ([`agents/analyst/`](agents/analyst/))

`load_history → compute_stats → detect_anomalies → generate_insights → verdict`

Loads the last 500 documents, computes supplier and overall statistics, flags anomalies (first document of a
supplier, amount 30 % or 60 % away from the supplier average, amount 3× above the overall average) and asks an LLM
for a short comment. Overall level: `NORMAL`, `ATTENTION` or `ALERTE`.

## Agent 4 — Chatbot ([`agents/chatbot/`](agents/chatbot/))

`understand_intent → query_db → generate_response`

Uses the current document (entities, audit, analysis) as context and queries PostgreSQL when the question is about
the history. LLM: Groq, Gemini as fallback.

## API

| Route | Description |
|---|---|
| `POST /analyse` | Full pipeline on an uploaded file (`file`, optional `base_entities` from GLM-OCR) |
| `POST /audit` | Agent 2 only, on a corrected JSON (human-in-the-loop) |
| `POST /analyst` | Agent 3 only, on a corrected JSON |
| `POST /chat` | Agent 4 |
| `POST /save` | Saves the (corrected) entities |
| `GET /pg/documents`, `GET /pg/documents/{id}` | History and details |
| `DELETE /documents/{type}/{number}`, `DELETE /admin/clear-documents`, `POST /admin/daily-report` | Administration (admin JWT) |
| `POST /token`, `GET /health` | JWT and health check |

## Running

```bash
cd assistant
python -m venv venv && source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                                  # API keys, DATABASE_URL, JWT_SECRET, alert settings
uvicorn api.main:app --host 0.0.0.0 --port 8002 --reload
```

The tables are created automatically at start-up (`database/connection.py`). LangGraph Studio can display the four
graphs (`langgraph dev`, configuration in `langgraph.json`), and `../visualize_graphs.py` renders them as PNG files
in [`graphs_output/`](../graphs_output/).

## Files

```
assistant/
├── api/main.py            FastAPI application and routes
├── agents/
│   ├── extractor/         graph.py, tools.py (OCR, LLM and vision tools)
│   ├── auditor/           graph.py, checks.py, auditor.py, notifier.py, daily_reporter.py
│   ├── analyst/           graph.py, checks.py
│   └── chatbot/           graph.py
├── database/              connection.py (PostgreSQL pool and schema), repository.py (CRUD)
├── state.py               shared TypedDict states of the four agents
├── langgraph.json         LangGraph Studio configuration
└── requirements.txt
```
