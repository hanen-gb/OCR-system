# Agent 1 — L'Extracteur

> Dernière mise à jour : Mai 2026 — v2.0  
> Pipeline : OCR.space + Groq qwen3-32b (texte) + Groq llama-4-scout (vision)

---

## Rôle

L'Agent Extracteur est le **premier maillon** du pipeline multi-agent. Il reçoit un document commercial (image ou PDF) et produit un JSON structuré complet en 3 sections :

| Section | Contenu | Modèle |
|---|---|---|
| **I — Articles & Taxes** | Tableau des articles (QTE, PU, TVA), montants globaux, timbre | Groq qwen3-32b (texte) |
| **II — Visuel & Sécurité** | Tampons, signatures, aval bancaire, logo, état | Groq llama-4-scout (vision) |
| **III — Paiement & Logistique** | Mode règlement, coordonnées, matricules fiscaux, références | Groq qwen3-32b (texte) |

Il fonctionne **en complément** des modèles fine-tunés GLM qui extraient les entités de base :
- **Facture** : `fournisseur`, `client`, `num_facture`, `date_facture`, `montant_ttc`
- **Lettre de change** : `rib`, `tire`, `tireur`, `num_lettre`, `date_echeance`, `montant`, `domiciliation`

---

## Architecture du graphe LangGraph

```
START
  │
  ▼
detect_type              ← pdfplumber : pdf_native / pdf_scanned / image
  │
  ├── pdf_native  →  extract_native     ← pdfplumber (texte + tableaux structurés)
  │
  └── pdf_scanned →  extract_vision     ← OCR.space API (25 000 req/mois gratuit)
      image       →  extract_vision
                          │
                          ▼
                   extract_entities     ← Groq qwen3-32b : Sections I & III (JSON texte)
                          │
                          ▼
                   extract_visual       ← Groq llama-4-scout-17b : Section II + articles
                          │
                          ▼
                         merge          ← Fusion : visual > augmented > base
                          │
                          ▼
                          END
```

### Règle de fusion (`merge_node`)

```
complete = {**augmented_entities, **visual_fields, **base_entities}
```

- `visual_fields` (vision) **écrase** `augmented_entities` pour la Section II
- Pour les **articles** : si `visual_fields.articles` est non-vide → il remplace `augmented_entities.articles` (la vision lit les colonnes visuellement, plus fiable que l'OCR linéaire)
- `base_entities` (GLM fine-tuné) a la priorité finale sur les champs de base

---

## Fichiers

```
assistant/
├── state.py                             ← ExtractorState TypedDict
├── agents/
│   ├── __init__.py
│   ├── extractor/
│   │   ├── __init__.py                  ← Exports : extractor_graph
│   │   ├── tools.py                     ← 5 outils LangGraph
│   │   └── graph.py                     ← Graphe compilé
│   └── auditor/                         ← Agent 2 (Auditeur)
│       ├── __init__.py
│       ├── checks.py                    ← Vérifications arithmétiques
│       ├── db.py                        ← SQLite (déduplication)
│       └── auditor.py                   ← Orchestrateur Agent 2
├── api/
│   └── main.py                          ← FastAPI : /analyse /audit /documents
├── data/
│   └── documents.db                     ← Base SQLite (créée automatiquement)
├── .env                                 ← Clés API
├── requirements_agent1.txt
└── README_AGENT1_EXTRACTEUR.md
```

---

## Outils (Tools)

### Outil 1 — `detect_file_type`

Détecte automatiquement le type du fichier.

**Retourne :**
```json
{ "file_type": "pdf_native | pdf_scanned | image", "pages": 1, "extension": ".jpg" }
```

**Logique :**
- Extensions image → `image`
- PDF → pdfplumber vérifie les 2 premières pages (texte ≥ 50 chars → `pdf_native`, sinon `pdf_scanned`)

---

### Outil 2 — `extract_text_pdf_native`

Extrait le texte **et** les tableaux d'un PDF natif via pdfplumber.

**Retourne :** `str` — texte brut avec tableaux formatés `col1 | col2 | col3`

---

### Outil 3 — `extract_text_vision`

Extrait le texte d'une image ou PDF scanné.

**Chaîne de fallback :**

| Priorité | Service | Clé requise |
|---|---|---|
| 1 | OCR.space (REST API) | `OCR_SPACE_API_KEY` |
| 2 | Gemini SDK natif | `GOOGLE_API_KEY` |
| 3 | Groq llama-4-scout | `GROQ_API_KEY` |

**Paramètres OCR.space :** `OCREngine=2`, `isTable=true`, `language=fre`, `scale=true`

---

### Outil 4 — `extract_augmented_entities`

Extraction des entités textuelles via LLM (Sections I & III).

**Chaîne de fallback LLM :**

| Priorité | Modèle | Clé | Note |
|---|---|---|---|
| 1 | `qwen/qwen3-32b` | `GROQ_API_KEY` | Meilleur pour JSON structuré FR/AR |
| 2 | `Qwen/Qwen2.5-7B-Instruct` | `HF_API_KEY` | Fallback si Groq 429 |
| 3 | `gemini-1.5-flash-8b` | `GOOGLE_API_KEY` | Fallback si HF 429 |

**Bascule automatique sur 429 :** si Groq retourne "rate_limit" ou "429" → bascule sur HuggingFace sans interruption.

**Entités extraites — FACTURE (Sections I & III) :**
```
Section I — Articles & Taxes :
  articles[].designation, quantite, unite, prix_unitaire_ht,
  tva_rate_ligne, total_ht_ligne
  montant_ht, montant_tva, tva_rate, remise_globale,
  timbre_fiscal, net_a_payer_lettres

Section III — Paiement & Logistique :
  mode_reglement, date_echeance,
  email_fournisseur, telephone_fournisseur, adresse_fournisseur,
  matricule_fiscal_fournisseur,
  email_client, telephone_client, adresse_client,
  matricule_fiscal_client,
  reference_commande, reference_bon_livraison, devise
```

**Entités extraites — LETTRE DE CHANGE (Sections I & III) :**
```
Section I — Financier :
  montant_en_lettres, timbre_fiscal, devise

Section III — Logistique :
  lieu_creation, lieu_paiement, banque_domiciliataire,
  swift_bic, rib_tire, date_acceptance, date_presentation,
  endossements[], telephone/email tire & tireur,
  adresse_tire, adresse_tireur, reference_commande, mode_reglement
```

---

### Outil 5 — `extract_visual_fields`

Analyse visuelle directe via **Groq llama-4-scout-17b-16e-instruct** (Section II).

**Chaîne de fallback vision :**

| Priorité | Modèle | Clé |
|---|---|---|
| 1 | `meta-llama/llama-4-scout-17b-16e-instruct` | `GROQ_API_KEY` |
| 2 | `gemini-2.0-flash` | `GOOGLE_API_KEY` |
| 3 | `gemini-1.5-flash-8b` | `GOOGLE_API_KEY` |

**Pour une FACTURE** — détecte + extrait le tableau des articles visuellement :
```json
{
  "cachet_present": true,
  "signature_presente": false,
  "notes_manuscrites": null,
  "etat_document": "original",
  "logo_detecte": true,
  "logo_nom": "Sfax Clean",
  "articles": [
    {
      "designation": "BOITE 2M ENCAST MUR CREUX",
      "quantite": 8,
      "unite": null,
      "prix_unitaire_ht": 4.987,
      "tva_rate_ligne": "19%",
      "total_ht_ligne": 39.896
    }
  ]
}
```

**Pourquoi la vision pour les articles ?**
Le modèle texte (OCR linéaire) confond les colonnes QTE et P.U.H.T quand elles sont adjacentes.
Llama-4-scout **voit** visuellement les colonnes et lit chaque bande verticale indépendamment.
`max_tokens = 4096` pour les factures (12+ articles).

**Pour une LETTRE DE CHANGE** — détecte tampons, signatures, aval :
```json
{
  "cachet_present": true,
  "signature_tire": true,
  "signature_tireur": false,
  "aval_bancaire": true,
  "aval_details": "Attijari Bank — Agence Sfax",
  "banque_domiciliataire": "Attijari Bank, Agence Lac",
  "notes_manuscrites": "TRENTE CINQ MILLE DINARS",
  "etat_document": "original"
}
```
`max_tokens = 1024` pour les traites.

---

## État partagé — `ExtractorState`

```python
class ExtractorState(TypedDict):
    # ── Input ─────────────────────────────────────────────────
    file_path     : str
    document_type : Optional[str]   # "facture" | "lettre_de_change" | "auto"
    base_entities : Optional[dict]  # Entités du modèle GLM fine-tuné

    # ── Étape 1 : Détection ───────────────────────────────────
    file_type  : Optional[str]   # "pdf_native" | "pdf_scanned" | "image"
    file_pages : Optional[int]

    # ── Étape 2 : OCR ─────────────────────────────────────────
    raw_text : Optional[str]

    # ── Étape 3a : LLM texte (Sections I & III) ───────────────
    augmented_entities : Optional[dict]

    # ── Étape 3b : Vision (Section II + articles) ─────────────
    visual_fields : Optional[dict]

    # ── Output final ──────────────────────────────────────────
    complete_entities : Optional[dict]  # Fusion des 3 sources

    # ── LangGraph internal ────────────────────────────────────
    messages : Annotated[list[AnyMessage], add_messages]
```

---

## Règles du prompt (7 règles)

| Règle | Sujet | Exemple |
|---|---|---|
| **0** | Lecture seule — jamais de calcul | Champ absent → `null` |
| **1** | Fournisseur vs Client | `N° client` → CLIENT toujours ; RC/IF/ICE → fournisseur |
| **2** | Tableau des articles | QTE ≠ N° série/lot ; ne pas recalculer |
| **3** | Séparateur décimal | `33.529` = millimes → garder `33.529`, jamais `33529` |
| **4** | Montants globaux | Identifier par libellé exact (`Total HT`, `TVA 19%`, `Timbre`) |
| **5** | Devise | Lire depuis le document → `DT` / `DH` / `EUR` / null |
| **6** | Champs spéciaux | `net_a_payer_lettres` : copie MOT POUR MOT, devise exacte |
| **7** | Erreurs OCR | Corriger `0`↔`O`, `1`↔`l` dans les noms seulement |

---

## Configuration

### Variables d'environnement (`assistant/.env`)

```env
# ── LangSmith — Observabilité LangGraph ───────────────────────────────────────
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=lsv2_pt_...          # smith.langchain.com → API Keys
LANGCHAIN_PROJECT=OCR-PFE-GLM

# ── OCR (gratuit, 25 000 req/mois) ────────────────────────────────────────────
OCR_SPACE_API_KEY=K8...                # ocr.space/OCRAPI

# ── LLM Extraction + Vision (Groq — prioritaire) ─────────────────────────────
GROQ_API_KEY=gsk_...                  # console.groq.com → API Keys
                                       # Modèles : qwen3-32b (texte) + llama-4-scout (vision)

# ── Fallback LLM texte ────────────────────────────────────────────────────────
HF_API_KEY=hf_...                     # huggingface.co → Settings → Access Tokens
                                       # Modèle : Qwen/Qwen2.5-7B-Instruct

# ── Fallback Vision ───────────────────────────────────────────────────────────
GOOGLE_API_KEY=AIzaSy...              # aistudio.google.com → Get API Key
                                       # Modèle : gemini-2.0-flash
```

### Installation

```powershell
cd assistant
pip install -r requirements_agent1.txt
```

---

## Lancement

```
┌─────────────────────────────┐   ┌──────────────────────────────────────────┐
│  Terminal 1 — Frontend      │   │  Terminal 2 — Agents (Extracteur+Auditeur)│
│                             │   │                                            │
│  cd frontend                │   │  cd assistant                              │
│  npm run dev                │   │  uvicorn api.main:app \                    │
│                             │   │    --host 0.0.0.0 --port 8002 --reload     │
│  → http://localhost:3000    │   │  → http://localhost:8002                   │
└─────────────────────────────┘   └──────────────────────────────────────────┘
```

---

## API Endpoints

| Méthode | URL | Description |
|---|---|---|
| `GET` | `/health` | Vérifie que le serveur tourne |
| `POST` | `/analyse` | **Pipeline complet** : Agent 1 (extraction) + Agent 2 (audit) |
| `POST` | `/audit` | Agent 2 seul — audite un JSON existant |
| `GET` | `/documents` | Liste les documents enregistrés (déduplication) |
| `DELETE` | `/documents/{type}/{number}` | Supprime un document de la base |

### `POST /analyse` — Corps de la requête

```
Content-Type: multipart/form-data

file          : fichier image ou PDF
document_type : "facture" | "lettre_de_change" | "auto"   (défaut: "auto")
base_entities : JSON string des entités GLM                (défaut: "{}")
```

### `POST /analyse` — Réponse

```json
{
  "analyse_contextuelle": {
    "_document_type": "facture",
    "articles": [...],
    "montant_ht": 1980.992,
    "cachet_present": false,
    "logo_nom": "EXEMPLE TRAVAUX SARL",
    "mode_reglement": "Traite",
    "...": "..."
  },
  "audit": {
    "status_validite": "VALIDÉ",
    "check_arithmetique_lignes": [...],
    "validation_tva_globale": { "status": "OK", "ecart": 0.0 },
    "conformite_net_a_payer": { "status": "OK", "ecart": 0.0 },
    "gouvernance": { "status": "OK" },
    "alerte_doublon": { "status": "NOUVEAU" }
  },
  "file_type": "image",
  "status": "ok"
}
```

---

## Schéma JSON de sortie complet

### Facture

```json
{
  "_document_type": "facture",

  "articles": [
    {
      "designation"     : "BOITE 2M ENCAST MUR CREUX",
      "quantite"        : 8,
      "unite"           : null,
      "prix_unitaire_ht": 4.987,
      "tva_rate_ligne"  : "19%",
      "total_ht_ligne"  : 39.896
    }
  ],
  "montant_ht"         : 1980.992,
  "montant_tva"        : 376.388,
  "tva_rate"           : "19%",
  "remise_globale"     : null,
  "timbre_fiscal"      : 1.000,
  "net_a_payer_lettres": "DEUX MILLE TROIS CENT SOIXANTE DINARS",

  "cachet_present"     : false,
  "signature_presente" : true,
  "notes_manuscrites"  : null,
  "etat_document"      : "original",
  "logo_detecte"       : true,
  "logo_nom"           : "EXEMPLE TRAVAUX SARL",

  "mode_reglement"              : "Traite",
  "date_echeance"               : null,
  "email_fournisseur"           : "contact@exemple-travaux.tn",
  "telephone_fournisseur"       : "71 000 000",
  "adresse_fournisseur"         : "10 Rue Exemple, Tunis",
  "matricule_fiscal_fournisseur": "0000000",
  "email_client"                : null,
  "telephone_client"            : null,
  "adresse_client"              : null,
  "matricule_fiscal_client"     : null,
  "reference_commande"          : null,
  "reference_bon_livraison"     : null,
  "devise"                      : "DT"
}
```

### Lettre de change

```json
{
  "_document_type": "lettre_de_change",

  "montant_en_lettres" : "TRENTE CINQ MILLE DINARS",
  "timbre_fiscal"      : 1.000,
  "devise"             : "DT",

  "signature_tire"     : true,
  "signature_tireur"   : false,
  "cachet_present"     : true,
  "aval_bancaire"      : true,
  "aval_details"       : "Attijari Bank — Agence Sfax",
  "notes_manuscrites"  : "Trente cinq mille dinars",
  "etat_document"      : "original",

  "lieu_creation"         : "Tunis",
  "lieu_paiement"         : "Sfax",
  "banque_domiciliataire" : "Attijari Bank, Agence Lac",
  "swift_bic"             : null,
  "rib_tire"              : "10 006 0000123456789 10",
  "date_acceptance"       : null,
  "date_presentation"     : null,
  "endossements"          : [],
  "telephone_tire"        : null,
  "telephone_tireur"      : null,
  "email_tire"            : null,
  "email_tireur"          : null,
  "adresse_tire"          : null,
  "adresse_tireur"        : null,
  "reference_commande"    : null,
  "mode_reglement"        : null
}
```

---

## Intégration dans le workflow global

```
[Upload document]
       │
       ▼
[Modèle GLM fine-tuné]
  Facture → {fournisseur, client, num_facture, date, montant_ttc}
  Traite  → {tire, tireur, rib, num_lettre, date_echeance, montant}
       │
       │ base_entities
       ▼
[Agent 1 — Extracteur]  ← ce module
  Section I  : Articles & Taxes      (Groq qwen3-32b)
  Section II : Visuel & Sécurité     (Groq llama-4-scout Vision)
  Section III: Paiement & Logistique (Groq qwen3-32b)
       │
       │ complete_entities
       ▼
[Agent 2 — Auditeur]
  check_arithmetique_lignes
  validation_tva_globale
  conformite_net_a_payer
  gouvernance (signatures, tampons)
  alerte_doublon (SQLite)
  → status_validite : VALIDÉ | ERREUR_CALCUL | ERREUR_TVA | DOUBLON | ...
       │
       ▼
[Agent 3 — Analyste]    (à venir)
[Agent 4 — Chatbot]     (à venir)
```

---

## Observabilité — LangSmith

Chaque run est tracé automatiquement sur **[smith.langchain.com](https://smith.langchain.com)** sous le projet `OCR-PFE-GLM`.

Tu y vois pour chaque nœud du graphe :
- Input / Output exact
- Temps d'exécution
- Tokens consommés (LLM)
- Erreurs et retries

Variables requises dans `.env` :
```env
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=lsv2_pt_...
LANGCHAIN_PROJECT=OCR-PFE-GLM
```

---

## Dépendances Python

| Package | Version | Rôle |
|---|---|---|
| `langgraph` | ≥ 0.2.0 | Orchestration du graphe |
| `langchain-core` | ≥ 0.3.0 | Messages, tools |
| `langchain-openai` | ≥ 0.2.0 | Groq (qwen3-32b + llama-4-scout) |
| `langchain-google-genai` | ≥ 2.0.0 | Gemini fallback |
| `langsmith` | ≥ 0.1.0 | Observabilité (traces) |
| `openai` | ≥ 1.0.0 | Client Groq vision |
| `huggingface-hub` | ≥ 0.24.0 | Qwen2.5-7B-Instruct fallback |
| `google-generativeai` | ≥ 0.8.0 | SDK Gemini natif |
| `pdfplumber` | ≥ 0.11.0 | PDF natif (texte + tableaux) |
| `pdf2image` | ≥ 1.17.0 | PDF scanné → images |
| `Pillow` | ≥ 10.0.0 | Manipulation images |
| `requests` | ≥ 2.31.0 | OCR.space API REST |
| `fastapi` | ≥ 0.111.0 | Serveur local |
| `uvicorn` | ≥ 0.30.0 | ASGI server |
| `python-multipart` | ≥ 0.0.9 | Upload fichiers |
| `python-dotenv` | ≥ 1.0.0 | Variables d'environnement |
| `pydantic` | ≥ 2.0.0 | Validation des données |
