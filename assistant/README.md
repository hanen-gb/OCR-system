# OCR Multi-Agent Pipeline — Backend

Système multi-agents LangGraph pour l'extraction, l'audit et l'analyse de documents financiers tunisiens (**factures** et **lettres de change**).

> PFE 2025 · Goubaa Hanen · ENIG Gabès · ODSInet

---

## Architecture du pipeline

```
Document (image / PDF)
        │
        ▼
┌───────────────┐
│  Agent 1      │  Extraction contextuelle
│  Extracteur   │  OCR.space → Qwen3-32b (Groq) → Gemini
└──────┬────────┘
       │ entités JSON
       ▼
┌───────────────┐
│  Agent 2      │  Audit & Validation
│  Auditeur     │  Règles métier + SQLite doublon + PostgreSQL
└──────┬────────┘
       │ rapport d'audit
       ▼
┌───────────────┐
│  Agent 3      │  Analyse comportementale
│  Analyste     │  Statistiques historiques + anomalies + LLM insights
└──────┬────────┘
       │
       ▼
┌───────────────┐
│  Agent 4      │  Chatbot
│  Chatbot      │  Questions/réponses sur le document en langage naturel
└───────────────┘
```

---

## Structure du projet

```
assistant/
├── api/
│   └── main.py                  # FastAPI — endpoints REST
├── agents/
│   ├── extractor/
│   │   ├── graph.py             # LangGraph Agent 1
│   │   └── tools.py             # OCR, LLM texte, LLM vision
│   ├── auditor/
│   │   ├── graph.py             # LangGraph Agent 2
│   │   ├── checks.py            # Règles métier (arithmétique, lettres, RIB…)
│   │   └── daily_reporter.py    # Rapport consolidé quotidien (email 08h00)
│   │   ├── db.py                # SQLite détection doublons
│   │   └── notifier.py          # Alertes email Gmail SMTP
│   ├── analyst/
│   │   ├── graph.py             # LangGraph Agent 3
│   │   └── checks.py            # Statistiques + détection anomalies
│   └── chatbot/
│       └── graph.py             # LangGraph Agent 4
├── database/
│   ├── connection.py            # Pool PostgreSQL (psycopg2)
│   └── repository.py            # CRUD — documents, factures, traites
├── state.py                     # TypedDict partagés (ExtractorState, AuditorState…)
├── main.py                      # Point d'entrée uvicorn
└── .env                         # Clés API (ne pas committer)
```

---

## Agent 1 — Extracteur

Extrait les entités structurées depuis une image ou un PDF.

**Flux :**
1. `detect_file_type` — PDF natif / PDF scanné / image
2. `extract_text_pdf_native` (pdfplumber) **ou** `extract_text_vision` (OCR.space)
3. `extract_augmented_entities` — LLM texte → JSON structuré
4. `extract_visual_fields` — LLM vision → signature, cachet, aval, notes manuscrites
5. `merge` — fusion de toutes les sources

**Entités extraites — Facture :**

| Champ | Description |
|-------|-------------|
| `fournisseur` | Nom du fournisseur |
| `client` | Nom du client |
| `numero_facture` | N° de facture |
| `date_facture` | Date (JJ/MM/AAAA) |
| `net_a_payer` | Montant net à payer |
| `montant_ht` | Montant hors taxe |
| `montant_tva` | Montant TVA |
| `timbre_fiscal` | Timbre fiscal |
| `net_a_payer_lettres` | Montant en toutes lettres |
| `signature`, `cachet_present` | Champs visuels |

**Entités extraites — Lettre de change :**

| Champ | Description |
|-------|-------------|
| `tireur` | Émetteur de la traite |
| `tire` | Destinataire |
| `rib` | RIB bancaire (20 chiffres) |
| `domiciliation` | Banque domiciliataire |
| `montant` | Montant en chiffres |
| `montant_en_lettres` | Montant en toutes lettres |
| `date_echeance` | Date d'échéance |
| `numero_traite` | N° de la traite |
| `signature_tire`, `signature_tireur`, `aval_bancaire` | Champs visuels |

**Chaîne LLM (fallback automatique) :**
```
Groq qwen3-32b (prompt tronqué ≤ 40k chars)
  → Groq llama-3.3-70b-versatile
  → HuggingFace compte 1 (HF_API_KEY)
  → HuggingFace compte 2 (HF_API_KEY_2)
  → Gemini 2.0-flash / 1.5-flash / 1.5-pro
```

---

## Agent 2 — Auditeur

Valide le document selon des règles métier strictes.

**Checks — Facture :**

| Check | Description |
|-------|-------------|
| Arithmétique lignes | QTE × PU_HT ≈ TOTAL_HT par ligne |
| Cohérence lettres/chiffres | Montant en lettres ≈ net_a_payer numérique |
| Doublon | N° déjà présent en base SQLite |
| Gouvernance | Cachet ou signature présent(s) |

**Checks — Lettre de change :**

| Check | Description |
|-------|-------------|
| Montant lettres | Montant lettres ≈ montant chiffres |
| Échéance | Date valide, non dépassée, non proche |
| RIB | Exactement 20 chiffres (format tunisien) |
| Gouvernance | Signature tire + tireur + aval |
| Doublon | N° traite déjà en SQLite |

**Statuts possibles :** `VALIDÉ` · `ERREUR_CALCUL` · `ERREUR_MONTANT_LETTRES` · `ERREUR_RIB` · `DOUBLON` · `SIGNATURE_MANQUANTE`

**Notifications email (Gmail SMTP)** :
- Alerte immédiate si échéance dépassée ou dans ≤ 2 jours (`ALERT_DEADLINE_DAYS`, défaut : 2)
- Alerte immédiate si montant TTC > `ALERT_MONTANT_RATIO` × moyenne du même type en base (défaut : 3×)
- **Rapport consolidé quotidien** automatique chaque matin à **08h00** — récap 24h + stats globales
- Endpoint manuel : `POST /admin/daily-report` pour déclencher le rapport sans attendre 8h

**Tableau des checks auditeur :**

| # | Check | Données requises | Déclenchement |
|---|-------|-----------------|---------------|
| 1 | Arithmétique lignes | QTE × PU = total_ligne | À chaque traitement |
| 2 | Cohérence lettres/chiffres | net_a_payer + net_a_payer_lettres | À chaque traitement |
| 3 | Détection doublons | num_facture + fournisseur (SQLite) | À chaque traitement |
| 4 | Gouvernance | cachet + signature + aval (traites) | À chaque traitement |
| 5 | Validation RIB | RIB 20 chiffres (traites) | À chaque traitement |
| 6 | Alerte montant élevé | montant_ttc vs historique même type | Email immédiat |
| 7 | Alerte échéance proche/dépassée | date_echeance ≤ J+2 ou passée | Email immédiat |
| 8 | Rapport consolidé BDD | Tous documents SQLite | Email quotidien 08h00 |

---

## Agent 3 — Analyste

Analyse comportementale basée sur l'historique SQLite.

- Statistiques fournisseur (nb docs, montant moyen, total)
- Statistiques globales (tous documents)
- Détection d'anomalies (montant déviant, nouveau fournisseur, montant élevé)
- Insights LLM (3-4 phrases de synthèse)
- Niveaux : `NORMAL` · `ATTENTION` · `ALERTE`

---

## Agent 4 — Chatbot

Répond à des questions en langage naturel sur le document analysé.

- Contexte injecté : entités + rapport d'audit + rapport analyste
- Intent routing : `document` ou `base_donnees`
- Si `base_donnees` : requête SQLite historique avant réponse
- Modèle LLM : même chaîne de fallback que Agent 1

---

## Base de données

### SQLite — Détection de doublons
- Fichier : `data/documents.db`
- Table : `documents` (doc_type, doc_number, fournisseur, montant, date_doc)
- Unique index sur `(doc_type, doc_number)`

### PostgreSQL — Historique complet
- Variable : `DATABASE_URL=postgresql://...@localhost:5432/ocr_pfe`
- Tables : `documents`, `factures`, `traites`
- Colonne `processing_time_s` : durée du pipeline en secondes
- Service Windows : `postgresql-x64-16` (démarrage automatique)

---

## API REST (port 8002)

| Méthode | Endpoint | Description |
|---------|----------|-------------|
| `GET` | `/health` | État du serveur |
| `POST` | `/token` | Authentification JWT |
| `POST` | `/analyse` | Pipeline complet (Agents 1+2+3) |
| `POST` | `/chat` | Agent 4 chatbot |
| `POST` | `/save` | Sauvegarde manuelle PostgreSQL |
| `GET` | `/pg/documents` | Historique PostgreSQL |
| `GET` | `/pg/documents/{id}` | Détail d'un document |
| `GET` | `/documents` | Liste SQLite (doublons) |
| `DELETE` | `/documents/{type}/{num}` | Supprimer un doublon SQLite |
| `DELETE` | `/admin/clear-sqlite` | Vider toute la table SQLite (admin) |
| `POST` | `/admin/daily-report` | Déclencher le rapport quotidien manuellement (admin) |

---

## Installation

### Prérequis
- Python 3.11+
- PostgreSQL 16 (service `postgresql-x64-16`)
- Clés API (voir `.env`)

### Installation

```bash
cd assistant
python -m venv venv
venv\Scripts\activate          # Windows
pip install -r requirements.txt
```

### Fichier `.env`

```env
# LangSmith (observabilité)
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=lsv2_...
LANGCHAIN_PROJECT=OCR-PFE-GLM

# OCR (ocr.space — 25 000 req/mois gratuit)
OCR_SPACE_API_KEY=K...

# LLM — chaîne de fallback
GROQ_API_KEY=gsk_...
HF_API_KEY=hf_...           # Compte HF 1
HF_API_KEY_2=hf_...         # Compte HF 2 (rotation automatique)
GOOGLE_API_KEY=AIza...

# PostgreSQL
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/ocr_pfe

# Notifications email
GMAIL_SENDER=...@gmail.com
GMAIL_APP_PASSWORD=xxxx xxxx xxxx xxxx
ALERT_EMAIL_TO=...@gmail.com
ALERT_THRESHOLD_DT=5000
ALERT_DEADLINE_DAYS=2
ALERT_MONTANT_RATIO=3.0
```

### Démarrage

```bash
cd assistant
uvicorn api.main:app --host 0.0.0.0 --port 8002 --reload
```

---

## Technologies

| Technologie | Version | Rôle |
|------------|---------|------|
| FastAPI | 0.115 | API REST |
| LangGraph | 0.2 | Orchestration agents |
| LangChain | 0.3 | Abstraction LLM |
| psycopg2 | 2.9 | PostgreSQL |
| SQLite3 | stdlib | Détection doublons |
| google-generativeai | 0.8 | Gemini Vision |
| huggingface-hub | 0.26 | HF Inference API |
| pdfplumber | 0.11 | Extraction PDF natif |
| pdf2image | 1.17 | PDF scanné → images |
| Pillow | 10 | Traitement images |
