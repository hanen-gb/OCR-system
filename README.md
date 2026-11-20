# ODSINET — GLM Multi-Agent OCR System · Entity Extraction on Tunisian Business Documents

**Final-Year Project (PFE) 2026 · Goubaa Hanen · ENIG Gabès**

A complete system for automatically extracting key entities from Tunisian invoices and bills of exchange, built on a **multi-agent LangGraph architecture**, a **GLM-OCR model fine-tuned with LoRA**, and a professional React interface.

---

## Table of contents

- [Overall architecture](#overall-architecture)
- [React Frontend](#react-frontend)
  - [Technical stack](#frontend-technical-stack)
  - [File structure](#file-structure)
  - [Authentication](#authentication--authts--jwt-fastapi)
  - [Global contexts](#global-contexts)
  - [Pages](#pages)
  - [Shared components](#shared-components)
- [GLM-OCR Backend](#glm-ocr-backend--backendmainpy--port-7860)
  - [Model](#model)
  - [Inference pipeline](#inference-pipeline)
  - [GLM endpoints](#glm-ocr-endpoints)
- [Agents Backend](#agents-backend--assistantapimainpy--port-8002)
  - [Endpoint /analyse](#endpoint-analyse--main-pipeline)
  - [Agent 1 — The Extractor](#agent-1--the-extractor)
  - [Agent 2 — The Auditor](#agent-2--the-auditor)
  - [Agent 3 — The Analyst](#agent-3--the-analyst)
  - [Agent 4 — The Chatbot](#agent-4--the-chatbot)
- [Model performance](#model-performance)

---

## Overall architecture

```
Frontend (React/Vite)         :3000
         ↕  REST (multipart + JSON)
Agents Backend (FastAPI)      :8002   ← LangGraph orchestration (Agents 1, 2, 3, 4)
         ↕  REST (image → JSON)
GLM-OCR Backend (FastAPI)     :7860   ← Vision-Language model inference
```

```
┌──────────────────────────────────────────────────────────────────────┐
│                          ODSINET PIPELINE                             │
└──────────────────────────────────────────────────────────────────────┘

  [Invoice / Bill of exchange]
              │
              ▼
  ┌───────────────────────┐
  │   React Frontend      │  localhost:3000
  │   File upload         │
  └──────────┬────────────┘
             │ POST /predict (image)
             ▼
  ┌───────────────────────────────┐
  │  GLM-OCR Backend · :7860      │
  │  Model Goubaa/glmocr-factures │
  │  → 5 base entities (JSON)     │
  └──────────┬────────────────────┘
             │ POST /analyse (file + base_entities)
             ▼
  ┌───────────────────────────────────────────────────────────┐
  │  Agents Backend · :8002                                   │
  │                                                           │
  │  Agent 1 (Extractor) → 30+ enriched entities              │
  │       ↓                                                   │
  │  Agent 2 (Auditor)   → audit report + verdict              │
  │       ↓                                                   │
  │  Agent 3 (Analyst)   → anomalies + AI insights              │
  │       ↓                                                   │
  │  Agent 4 (Chatbot)   → conversational replies               │
  └──────────┬────────────────────────────────────────────────┘
             │ JSON { analyse_contextuelle, audit, analyse }
             ▼
  ┌───────────────────────┐
  │   React Frontend      │  Results display
  │   HITL + AI Chatbot   │  Manual correction
  └───────────────────────┘
```

---

## REACT FRONTEND

### Frontend technical stack

| Tool | Role |
|---|---|
| React 18 + TypeScript | UI framework |
| Vite 5 | Bundler / dev server |
| React Router v6 | SPA routing |
| shadcn/ui | Primitive components (Button, Dialog, Input, Tabs, Table…) |
| Tailwind CSS | CSS utilities |
| framer-motion | Smooth animations (sidebar, transitions, cards) |
| lucide-react | Icons |
| Recharts | Charts (AreaChart, PieChart) |
| TanStack Query | HTTP request cache |

---

### File structure

```
frontend/src/
├── App.tsx                     ← Main router + global providers
├── main.tsx                    ← Vite entry point
├── lib/
│   ├── auth.ts                 ← Multi-user auth (localStorage)
│   ├── api.ts                  ← REST calls to both backends
│   └── i18n.ts                 ← FR / EN translations
├── contexts/
│   ├── AppContext.tsx           ← Global dark/light theme + language
│   └── ChatbotContext.tsx       ← Floating AI chatbot state
├── components/
│   ├── AppLayout.tsx            ← Sidebar + topbar + overall layout
│   ├── ChatbotWidget.tsx        ← Floating chatbot widget (bottom right)
│   └── ui/                     ← 40+ shadcn/ui components
└── pages/
    ├── LoginPage.tsx            ← Login / sign-up page
    ├── Dashboard.tsx            ← Real-time analytics dashboard
    ├── UploadPage.tsx           ← Analysis page (main page)
    ├── DocumentsPage.tsx        ← Document history
    ├── CalendarPage.tsx         ← Due-date calendar view
    ├── ProfilePage.tsx          ← User profile + photo import
    └── SettingsPage.tsx         ← Settings (theme, language, admin users)
```

---

### Authentication — auth.ts + JWT FastAPI

A two-layer system:

**Layer 1 — Identity (localStorage, `auth.ts`)**: stores profiles, verifies passwords, manages sessions. No network calls.

**Layer 2 — API authorization (JWT, FastAPI)**: after a successful login, the frontend calls `POST /token` on FastAPI. The agent returns a signed HS256 JWT `{sub: username, role}`. This token is stored in `localStorage["odsinet_agent_token"]` and sent with every agent request via `Authorization: Bearer <token>`. The `DELETE /documents/{type}/{number}` endpoint verifies the token and rejects with 403 if `role != "admin"`.

**JWT flow at login:**
```
1. login(username, password)  →  localStorage  (session)
2. fetchToken(username, role) →  POST /token   (FastAPI)
3. JWT stored in localStorage["odsinet_agent_token"]
4. analyseDocument()          →  Authorization: Bearer <jwt>
5. deleteDocument()           →  Authorization: Bearer <jwt>  [admin only]
```

**Optional environment variable** (`assistant/.env`):
```env
JWT_SECRET=your-production-secret
```

**Concrete role separation**:

| Action | user | admin |
|---|---|---|
| Upload + analyze | ✅ | ✅ |
| Correct entities (HITL) | ✅ | ✅ |
| Chatbot, history, export | ✅ | ✅ |
| View all accounts (SettingsPage) | ❌ (hidden in UI) | ✅ |
| Delete a user | ❌ | ✅ (except admin) |
| `DELETE /documents/{type}/{n}` | ❌ (403 FastAPI) | ✅ (JWT verified) |

> **For a production deployment**: add JWT expiry (`exp`), a refresh token, and an `owner_username` column in PostgreSQL (already present) to filter documents per user at the SQL level.

A multi-user system whose identity store is **entirely client-side** (localStorage). No authentication backend for profiles.

**`UserProfile` interface**:
```typescript
{
  username: string;
  password: string;
  displayName: string;
  email: string;
  role: "admin" | "user";
  avatarColor: string;
  photo?: string;      // base64 data-URL (profile photo import)
  bio: string;
  createdAt: string;
  lang: "fr" | "en";
  theme: "dark" | "light";
}
```

**Exported functions**:

| Function | Description |
|---|---|
| `login(username, password)` | Verifies credentials, writes the session to localStorage |
| `logout()` | Removes the current session |
| `getSession()` | Reads the logged-in user's profile |
| `isAuthenticated()` | Boolean used for route protection |
| `register(username, password, displayName, email)` | Creates a new account (role "user") |
| `updateProfile(username, updates)` | Updates displayName, email, bio, photo, avatarColor |
| `changePassword(username, current, new)` | Verifies the old password before changing it |
| `deleteUser(username)` | Forbidden on "admin" |
| `getAllUsers()` | Merges stored users with the defaults |
| `getHistoryKey(username)` | Per-user localStorage history key |

**localStorage keys**:
- `odsinet_users` → JSON array of all profiles
- `odsinet_session` → the logged-in user's profile
- `odsinet_history_<username>` → analysis history isolated per user

---

### Global contexts

**AppContext** (`contexts/AppContext.tsx`):
- Manages `theme: "dark" | "light"` persisted in `odsinet_theme`
- Manages `lang: "fr" | "en"` persisted in `odsinet_lang`
- Applies the `.light` class on `<html>` for Tailwind
- Exposes `t(key: TranslationKey)`: FR/EN translation function

**ChatbotContext** (`contexts/ChatbotContext.tsx`):
- Manages the open/closed state of the floating chatbot widget
- Shares the current document context (entities, audit, analysis) between `UploadPage` and `ChatbotWidget`

---

### Pages

#### App.tsx — Router & Protected Routes

`ProtectedRoute` redirects to `/login` if `isAuthenticated()` returns false, otherwise wraps the page in `<AppLayout>`.

Declared routes:

| Route | Page | Protection |
|---|---|---|
| `/login` | LoginPage | Public |
| `/` | Dashboard | Protected |
| `/upload` | UploadPage | Protected |
| `/documents` | DocumentsPage | Protected |
| `/calendar` | CalendarPage | Protected |
| `/profile` | ProfilePage | Protected |
| `/settings` | SettingsPage | Protected |
| `*` | NotFound | — |

---

#### AppLayout — Sidebar & Navigation

Wraps every protected page. Structure:

**Desktop sidebar** (animated, collapsible, 252px ↔ 60px via framer-motion):
- Two sections: "Main" (Dashboard, Analyze, History, Calendar) and "System" (Profile, Settings)
- Animated active-page indicator (`layoutId="active-nav"`)
- Theme + language toggles at the bottom
- Avatar + displayName + email + Logout button at the bottom of the sidebar

**Mobile sidebar**: an animated drawer (`x: -280 → 0`) with a semi-transparent black overlay (`bg-black/50`), closed on overlay click or link click.

**Topbar** (h-14): mobile hamburger + "Backend Active" badge with a pulsing green dot (`animate-pulse`).

**ChatbotWidget** mounted as a global overlay on every page.

**Avatar component**: shows the imported photo (base64) with priority, otherwise colored initials.

---

#### Dashboard

Displays analytics computed **in real time from the logged-in user's localStorage history**.

**6 KPI cards**:
- Total documents analyzed
- Unique suppliers (deduplicated by normalized name)
- Unique customers
- Completion rate (a document with ≥ 4 extracted entities counts as complete)
- Average inference time (in seconds)
- Date and name of the last analyzed document

**2 Recharts charts**:
- Gradient `AreaChart`: inference time of the last 10 documents
- Donut `PieChart`: detection rate per entity (CLIENT, FOURNISSEUR, NUMERO_FACTURE, DATE_FACTURE, MONTANT_TTC)

**History table**: last 6 documents with all their extracted entities.

---

#### UploadPage — Main analysis page

Orchestrates the entire analysis pipeline.

**Analysis flow**:
1. Drop or select a file (JPG, PNG, PDF)
2. `POST :7860/predict` → GLM-OCR → 5 base entities
3. `POST :8002/analyse` (multipart + `base_entities` JSON) → Agent 1 + 2 + 3
4. Results display: enriched entities, audit report with verdict, analyst report with alert level
5. **HITL (Human-in-the-Loop)**: manual correction of entities by the user
6. "Re-audit" button → `POST :8002/audit` with the corrected entities
7. Saved to the user's localStorage history

---

#### DocumentsPage

Full analysis history from the user's localStorage. Shows file name, date, extracted entities, and audit status. Allows deleting individual entries.

---

#### CalendarPage

Calendar view of documents. Places invoices and bills of exchange on their dates (invoice date or due date). Visualizes upcoming due dates.

---

#### ProfilePage

Profile-editing form: photo (base64 import), displayName, email, bio. Password change with verification of the old one. Saved via `updateProfile()` and `changePassword()` from `auth.ts`.

---

#### SettingsPage

3 sections:
1. **Appearance**: Dark / Light toggle with Sun/Moon buttons
2. **Language**: French / English
3. **User management** *(admin only)*: lists all users with avatar/photo, role, a "protected" badge for admin, a red delete button for others

---

### Shared components

#### ChatbotWidget

Floating widget in the bottom-right corner, visible on every page. Once a document has been analyzed, it automatically injects context into every message:
- Enriched extracted entities
- Audit report (verdict + check details)
- Analyst report (alert level + insights)

Calls `POST :8002/chat` with the conversation history + context. Displays Agent 4's replies (Groq llama-3.3-70b).

---

---

## GLM-OCR BACKEND — `backend/main.py` · Port 7860

### Role

The first backend, dedicated to **Vision-Language GLM-OCR model inference** fine-tuned on Tunisian business documents. Extracts 5 base entities from an image.

### Model

| Parameter | Value |
|---|---|
| Published model | `Goubaa/glmocr-factures` |
| Base | `zai-org/GLM-OCR` (ZhipuAI) |
| Fine-tuning | LoRA merged on Tunisian invoices |
| Local source | `backend/model/glm_model/` (if present) |
| Loading | Singleton via FastAPI `lifespan` (loaded once at startup) |
| Device | CUDA float16 if GPU available, otherwise CPU float32 |
| Max new tokens | 256 |
| Max image size | 1024px (longest side, LANCZOS resize) |

**Extracted entities (5)**:

| Entity | Description | Example |
|---|---|---|
| `CLIENT` | Customer name | `IEEE TUNISIA SECTION` |
| `FOURNISSEUR` | Supplier name | `STE ZRELLI DE COMMERCE` |
| `NUMERO_FACTURE` | Invoice number | `509-2022` |
| `DATE_FACTURE` | Date (DD/MM/YYYY format) | `06/04/2022` |
| `MONTANT_TTC` | Total amount incl. tax | `40.470` |

### Inference pipeline

`run_glm(pil_image)` function:
1. Convert image → RGB
2. Resize if > 1024px (longest side, LANCZOS)
3. Build the message using GLM's chat template:
   ```python
   [{"role": "user", "content": [{"type": "image", ...}, {"type": "text", "text": PROMPT}]}]
   ```
4. Fixed prompt for extracting the 5 entities (identical to the one used during training)
5. `model.generate()` with `max_new_tokens=256`, `do_sample=False`
6. Decode only the generated tokens (not the prompt)
7. `parse_glm_output()`: regex `\{[^{}]*\}` to extract the raw JSON
8. Fallback: `N/A` for every entity if parsing fails

### GLM-OCR endpoints

| Route | Method | Description |
|---|---|---|
| `POST /predict` | POST | `multipart/form-data` image → `{entities, full_text, timing}` |
| `GET /health` | GET | `{status, models_ready, model, device, source}` |
| `GET /labels` | GET | `{labels: [...5 entities...], count: 5}` |

**`/predict` response format**:
```json
{
  "entities": [
    {"label": "CLIENT",         "text": "STEG",     "box": null, "words": []},
    {"label": "FOURNISSEUR",    "text": "SOTUVER",  "box": null, "words": []},
    {"label": "NUMERO_FACTURE", "text": "FA-2024-001", "box": null, "words": []},
    {"label": "DATE_FACTURE",   "text": "15/03/2024", "box": null, "words": []},
    {"label": "MONTANT_TTC",    "text": "1250.750", "box": null, "words": []}
  ],
  "full_text": "{ \"CLIENT\": \"STEG\", ... }",
  "timing": {"inference_ms": 1240, "total_ms": 1380}
}
```

> `box: null` — GLM-OCR does not provide spatial coordinates (a known limitation compared to LayoutXLM).

---

---

## AGENTS BACKEND — `assistant/api/main.py` · Port 8002

### Role

The second backend, dedicated to **orchestrating the 4 LangGraph agents**. Receives the document file + GLM entities, runs the Agent1 → Agent2 → Agent3 chain, and exposes the Agent4 chatbot.

### Endpoints

| Route | Method | Agents | Description |
|---|---|---|---|
| `POST /analyse` | POST | 1 + 2 + 3 | Full pipeline: extraction + audit + behavioral analysis |
| `POST /audit` | POST | 2 only | Re-audit an entity JSON (after HITL correction) |
| `POST /chat` | POST | 4 | Contextual chatbot with conversation history |
| `GET /documents` | GET | — | Lists documents stored in SQLite |
| `DELETE /documents/{type}/{number}` | DELETE | — | Deletes a document (cancels a duplicate detection) |
| `GET /health` | GET | — | `{status: "ok", agents: [...], version: "3.0"}` |

---

### Endpoint `/analyse` — Main pipeline

**Parameters** (multipart/form-data):
- `file`: image (JPG/PNG/BMP/TIFF) or PDF
- `document_type`: `"facture"` | `"lettre_de_change"` | `"auto"` (default)
- `base_entities`: JSON string of the GLM entities (optional)

**Execution sequence**:
```
1. extractor_graph.invoke(file_path, document_type, base_entities)
      → complete_entities (30+ enriched fields)

2. auditor_graph.invoke(complete_entities, base_entities)
      → audit_report {verdict, checks, anomalies}

3. analyst_graph.invoke(complete_entities, audit_report)
      → analyst_report {alert_level, stats, insights}
```

**Response**:
```json
{
  "analyse_contextuelle": { "...30+ entities..." },
  "audit": {
    "status_validite": "VALIDATED | CALCULATION_ERROR | DUPLICATE | MISSING_SIGNATURE | ...",
    "checks": { "arithmetique": [...], "tva": {...}, "net_a_payer": {...}, "gouvernance": {...} }
  },
  "analyse": {
    "alert_level": "NORMAL | ATTENTION | ALERT",
    "anomalies": [...],
    "insights": "LLM-generated analysis text..."
  },
  "file_type": "image | pdf_native | pdf_scanned",
  "status": "ok"
}
```

---

### Agent 1 — The Extractor

**File**: `assistant/agents/extractor/graph.py` + `assistant/agents/extractor/tools.py`

**State** (`ExtractorState`): `file_path`, `document_type`, `base_entities`, `file_type`, `native_text`, `vision_text`, `augmented_entities`, `visual_fields`, `complete_entities`, `messages`

**LangGraph graph — 6 nodes**:

```
detect_type
    │
    └─ route_extraction()
            ├─ "native"  → extract_native (pdfplumber)
            └─ "vision"  → extract_vision (OCR.space → Gemini → Groq)
                    │
              extract_entities (text LLM: 30+ entities)
                    │
              extract_visual (vision LLM: signatures, stamps)
                    │
                merge_node (merge + 6 post-processing steps)
```

**5 tools** (`@tool`):

| Tool | Line | Description |
|---|---|---|
| `detect_file_type()` | l.261 | pdfplumber → `pdf_native` / `pdf_scanned` / `image` |
| `extract_text_pdf_native()` | l.306 | pdfplumber: raw text + tables |
| `extract_text_vision()` | l.346 | OCR.space → Gemini 2.0-flash → Groq llama-4-scout-17b |
| `extract_augmented_entities()` | l.879 | Groq qwen3-32b → HF Qwen2.5-7B → Gemini 1.5-flash |
| `extract_visual_fields()` | l.661 | Groq llama-4-scout-17b → Gemini 2.0-flash |

**Text LLM chain** (`_call_llm()` l.49):
- Groq `qwen3-32b` (primary, ultra-fast)
- HuggingFace `Qwen2.5-7B-Instruct` (text fallback)
- Google `Gemini 1.5-flash` (last resort)

**Prompt**: 17 business rules — FR/AR bilingual detection, 3-decimal DT amount format, Tunisian tax ID format, FODEC (Tunisian development levy), 0.600 DT fiscal stamp duty, distinguishing a bill of exchange (traite) from an invoice.

**6 post-processing steps in `merge_node`**:
- GPS-in-amount detection (`DD.MM.YYYY` pattern mistaken for an amount)
- Millime restoration (3-decimal DT)
- EUR → flagged for conversion
- Fiscal stamp duty validation (Tunisian standard: 0.600 DT)
- Date format normalization → `DD/MM/YYYY`
- Tax ID normalization → `XXXXXXXXX/A/X/XXX`

---

### Agent 2 — The Auditor

**File**: `assistant/agents/auditor/graph.py` + `assistant/agents/auditor/checks.py`

**LangGraph graph — 7 sequential nodes**:

| Node | Line | Function |
|---|---|---|
| `prepare_node` | l.98 | Normalizes str→float types, initializes the state |
| `arithmetic_node` | l.137 | `check_arithmetic_lines()`: QTY × unit price × (1-discount%) ≈ line total excl. tax |
| `tva_node` | l.146 | `validate_tva_globale()`: Σ(amount excl. tax × VAT rate) ≈ VAT amount |
| `net_node` | l.230 | `check_net_a_payer()`: base excl. tax + VAT + stamp duty ≈ net payable |
| `doublon_node` | l.293 | `check_doublon()` SQLite check on `(doc_type, doc_number)` |
| `gouvernance_node` | l.300 | `check_governance()`: signatures + stamps |
| `verdict_node` | l.308 | Aggregates every check, determines the final verdict |

**Arithmetic tolerance**: 0.005 DT (5 millimes) to absorb rounding.

**`_parse_tva_rate()` specifics** (l.11): handles OCR errors — `"2016"` → 20%, `"1906"` → 19%, values > 100 auto-corrected.

**Verdict priority**:
```
DUPLICATE > MISSING_SIGNATURE > CALCULATION_ERROR > VAT_ERROR > NET_PAYABLE_ERROR > VALIDATED
```

**`check_net_a_payer()`** — base-excl.-tax priority:
1. Extracted `net_htva` (net excl. tax, already including discount + FODEC)
2. `montant_ht + fodec` (if `net_htva` is absent)
3. `montant_ht` alone (if there's no FODEC)

**Governance check by document type**:
- **Invoice**: `signature_presente` (signature present) + `cachet_present` (stamp present)
- **Bill of exchange**: `signature_tire` (drawee signature) + `signature_tireur` (drawer signature) + `cachet_present` + `aval_bancaire` (bank guarantee, optional)

---

### Agent 3 — The Analyst

**File**: `assistant/agents/analyst/graph.py` + `assistant/agents/analyst/checks.py`

**LangGraph graph — 5 nodes**:

| Node | Line | Function |
|---|---|---|
| `load_history` | l.61 | `list_documents(500)` SQLite → history of the last 500 documents |
| `compute_stats` | l.68 | `compute_supplier_stats()` + `compute_global_stats()` |
| `detect_anomalies` | l.86 | Compares the current amount against the supplier's and the global history |
| `generate_insights` | l.107 | Generates the analysis text via Groq qwen3-32b |
| `verdict` | l.162 | Computes the overall alert level |

**Anomaly detection thresholds**:

| Condition | Level |
|---|---|
| First document from this supplier | ATTENTION |
| Amount deviates ≥ 30% from the supplier's average | ATTENTION |
| Amount deviates ≥ 60% from the supplier's average | ALERT |
| Amount > 3× the global average | ATTENTION |

---

### Agent 4 — The Chatbot

**File**: `assistant/agents/chatbot/graph.py`

**LangGraph graph — 3 nodes**:

| Node | Line | Function |
|---|---|---|
| `understand_intent` | l.106 | Keyword-based classification (entities / audit / analysis / general) |
| `query_db` | l.120 | Enrichment from SQLite when relevant |
| `generate_response` | l.128 | LLM response generation with injected context |

**`_build_context_block()`** (l.56): injects the current document's extracted entities + audit report + analyst report into the system prompt.

**Chatbot LLM chain**:
- Groq `llama-3.3-70b` (primary)
- Groq `llama3-groq-70b-8192` (fallback)
- Google `Gemini 2.0-flash` (last resort)

---

---

## Model performance

| Task | Metric | Value |
|---|---|---|
| Information extraction (fine-tuned GLM-OCR) | Field-level F1 (macro, 5 fields, 801 test invoices) | 97.40% |
| Information extraction (fine-tuned GLM-OCR) | Exact match (all 5 fields correct) | 89.89% |
| Document classification (MobileNetV2) | Accuracy | 99.69% |
| Invoice dataset | Documents | 4,004 invoices (194 real, 2,910 augmented, 900 synthetic), split 80/20 before augmentation |
| Fine-tuning | Method | LoRA merged — zai-org/GLM-OCR |

---

## Full technical stack

### GLM-OCR Backend

| Tool | Version | Role |
|---|---|---|
| FastAPI | 0.115+ | REST API |
| PyTorch | 2.4.1 | GPU/CPU inference |
| Transformers (HuggingFace) | git HEAD | GLM-OCR |
| Pillow | — | Image processing |
| Python | 3.11 | Runtime |

### Agents Backend

| Tool | Version | Role |
|---|---|---|
| FastAPI | 0.135+ | REST API |
| LangGraph | — | Agent orchestration |
| LangChain | — | LLM abstractions |
| pdfplumber | — | Native PDF extraction |
| SQLite3 | stdlib | Deduplication + history |
| Groq SDK | — | qwen3-32b, llama-4-scout, llama-3.3 |
| Google GenerativeAI | — | Gemini 2.0-flash, 1.5-flash |
| HuggingFace Hub | — | Qwen2.5-7B-Instruct |
| LangSmith | — | Observability |
| Python | 3.11 | Runtime |

### Frontend

| Tool | Version | Role |
|---|---|---|
| React | 18 | UI |
| Vite | 5 | Bundler |
| TypeScript | 5 | Typing |
| Tailwind CSS | 3 | Utility styles |
| shadcn/ui | — | Primitive components |
| framer-motion | 11 | Animations |
| Recharts | 2 | Analytics charts |
| React Router | 6 | SPA routing |
| TanStack Query | 5 | HTTP request cache |
| lucide-react | — | Icons |

---

*ODSINET — Final-Year Project (PFE) 2026 · Goubaa Hanen · National School of Engineers of Gabès (ENIG)*
