# Agent 1 — L'Extracteur

> Dernière mise à jour : Juin 2026 — v4.4  
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

**Post-traitements automatiques dans `merge_node` (v4.3) :**

| # | Post-traitement | Description |
|---|----------------|-------------|
| 1 | **Correction devise — EUR** | Regex `\bEUR\b` / `€` / `\bSIRET\b` dans OCR → `EUR` — **sans** `CENTIMES` (Tunisie : "CENTIMES" = millimes, pas EUR) |
| 2 | **Correction devise — DT** | Si "Montant (DT)" / `TND` / `(TND)` / "بالدينار" → `DT` ; fallback depuis `net_a_payer_lettres` (priorité basse) |
| 3 | **Validation `timbre_fiscal`** | Si valeur > 50 DT après normalisation → rejeté (`null`) |
| 4 | **Validation `numero_facture`** | Si contient > 4 mots ou mots d'adresse → rejeté ou corrigé par regex |
| 5 | **GPS dans adresses** | Pattern `XX.XXXX,YY.YYYY` détecté → champ adresse mis à `null` |
| 6 | **`_normalize_amount()` — 5 cas** *(v4.3)* | Remplace `_restore_millimes`. Gère : espaces milliers, virgule+point européen, double point tunisien, virgule seule, entier sans décimal par ancrage sur `net_a_payer` |

**`_normalize_amount(val, field, net_ref, allow_int_fix)` — algorithme (v4.3) :**

| Étape | Entrée | Règle | Exemple |
|-------|--------|-------|---------|
| Norm. string | `"1 320.600"` | Supprimer espaces/nbsp | `"1320.600"` |
| Norm. string | `"1.320,600"` | Virgule+point → point=milliers | `1320.600` |
| Norm. string | `"1.320.600"` | Double point → dernier = décimal | `1320.600` |
| Norm. string | `"1320,600"` | Virgule seule → décimal | `1320.600` |
| Règle A | `4498800` | Entier ≥ 10 000 → ÷ 1000 | `4498.800` |
| Règle B | `1000` (timbre) | `timbre_fiscal` > 30 DT → ÷ 1000 | `1.000` |
| Règle C | `4750` (TVA) | Entier > `net_ref` (30.75) → ÷ 1000 | `4.750` |
| Warning | `> 100 000` DT | Log warning, valeur conservée | — |

**Ordre d'application dans `merge_node` :**
1. `net_a_payer` en premier (ancre de plausibilité)
2. `montant_tva`, `montant_ht`, `fodec`, `net_htva` avec `net_ref`
3. `timbre_fiscal` toujours avec `allow_int_fix=True` (indépendant de la taille du doc)
4. Champs articles (`prix_unitaire_ht`, `total_ht_ligne`) avec `net_ref`

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
  remise_pct_ligne (v3.0),           ← % remise par ligne (ex: 10 pour 10%)
  tva_rate_ligne, total_ht_ligne
  numero_facture (v3.0),
  montant_ht, remise_globale,
  montant_ht_ar (v4.0),              ← Total HT Après Remise
  fodec (v4.0),                      ← Taxe FODEC 1% (≠ remise)
  net_htva (v4.0),                   ← Base de calcul TVA (= montant_ht_ar + fodec)
  montant_tva, tva_rate, remise_globale,
  timbre_fiscal, net_a_payer (v3.0 — valeur numérique), net_a_payer_lettres

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

## Règles du prompt (v4.2 — 20 règles)

| Règle | Sujet | Détail |
|---|---|---|
| **0** | Lecture seule + Anti-hallucination montants | Champ absent → `null` ; bloc totaux absent → `net_a_payer=null` ; chiffres répétitifs (333333) → `null` |
| **0bis** | Documents bilingues FR/AR | L'arabe est une traduction du français — lire uniquement la version française pour les valeurs numériques |
| **0ter** | `numero_facture` format | Code alphanumérique compact qui SUIT le libellé (ex: `A/155200`, `FT-230600`, `1729/900000`) — ❌ jamais copier le libellé `"Facture N°"` lui-même |
| **0qua** | Anti-hallucination articles | Pas de tableau réel → `articles=[]` ; notes manuscrites ≠ articles ; article unique = résumé global → `articles=[]` |
| **1** | Fournisseur vs Client | Bloc GAUCHE = fournisseur ; encadré/DROITE = client ; `N° client` → CLIENT uniquement |
| **1bis** | Layout français | Fournisseur haut-gauche sans bordure ; client dans rectangle à droite |
| **2** | Tableau des articles (colonnes HT) | QTE ≠ N° série/lot ; ne pas recalculer `total_ht` ; colonnes indépendantes |
| **2bis** | Colonnes "PU TTC" | Si colonne est "PU TTC" → `prix_unitaire_ht=null`, `total_ht_ligne=null` ; extraire HT depuis pied de facture |
| **3** | Séparateur décimal simple | `33.529` = millimes DT → garder ; `4.750` → `4.750` ✅ (JAMAIS `4750`) ; virgule = décimal → convertir en point |
| **3bis** | Double-point tunisien (X.XXX.XXX) | `2.345.000` → `2345.000` DT (premier point = milliers, deuxième = millimes) |
| **3ter** | Espace milliers + point millimes | `1 109.244` → `1109.244` ✅ — JAMAIS supprimer le point décimal quand un espace précède |
| **3qua** | Cohérence montants | `montant_tva` doit toujours être < `net_a_payer` — si non, erreur de lecture → revoir CAS A |
| **4** | Montants globaux | Identifier par libellé exact (`Total HT`, `TVA XX%`, `Timbre`) ; `montant_ht_ar` = après remise ; `fodec` = taxe 1%, jamais une remise ; `net_htva` = base TVA |
| **4bis** | Synonymes timbre fiscal | Libellés valides : `"Droit de timbre"`, `"Droit de timbre sur facture"`, `"Timbre fiscal"`, `"TIMBRE FISCAL LOI..."` → valeur = `timbre_fiscal` ; `"1.000"` = `1.000 DT` (CAS A), jamais `1000` |
| **5** | Devise priorité absolue | Si "Montant (DT)" / "بالدينار" visible → `devise="DT"` obligatoirement ; jamais USD par défaut |
| **5bis** | Factures de services (télécom/énergie) | `articles=[]` ; extraire récapitulatif dans les champs globaux (`montant_ht`, `montant_tva`, etc.) |
| **5ter** | Bilingue FR/AR | Lire uniquement le français ; ne pas mélanger texte arabe dans les champs JSON |
| **6** | Champs spéciaux | `net_a_payer_lettres` : copie MOT POUR MOT ; `mode_reglement` : un seul mode ou null si liste de choix |
| **6bis** | Matricule Fiscal tunisien | Format `XXXXXXXL/L/L/000` (ex: `1234567A/M/000`) ; RC (`B XXXXXXXXX`) ≠ MF ; libellés : "MF:", "M.F:" |
| **6ter** | Adresses | Postal uniquement — jamais de coordonnées GPS, jamais de données d'articles |
| **7** | Timbre fiscal | Valeur max 50 DT en Tunisie — si > 50 DT → null (confusion avec TTC) |
| **8** | Erreurs OCR | Corriger `0`↔`O`, `1`↔`l` dans les noms seulement — jamais sur les montants |

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

---

## Historique des versions

### v4.4 — Juin 2026
- **`had_decimal` dans `_normalize_amount`** : Correction du bug F6 — si la chaîne d'origine contient déjà un séparateur décimal (virgule ou point), le montant est fourni avec décimales **explicites** et ne doit jamais être divisé par 1000 (`"20 754,000"` → `20754.0` ✓, plus `20.754` ✗)
- **Règles A+C fusionnées** : La division par 1000 n'est appliquée qu'aux entiers **purs** (aucun séparateur dans la chaîne), avec `net_ref` comme ancre de plausibilité pour les valeurs < 100 000
- **`EUR_PATTERNS`** : Suppression de `\bCENTIMES?\b` — en Tunisie "CENTIMES" désigne des millimes (usage FR hérité), pas la devise EUR ; causait `devise=EUR` sur les factures TND
- **Détection TND** : Ajout de `TND`, `(TND)`, `EN TND` dans les patterns de détection DT
- **Nettoyage `"null"` textuels** : Le LLM écrit parfois la chaîne `"null"` — convertie en `None` Python avant tout traitement
- **`CAS A-quater`** dans les deux prompts : Format `"X YYY,ZZZ"` (espace milliers + virgule décimale) → `XYYY.ZZZ` — exemple : `"20 754,000"` → `20754.000`

### v4.3 — Juin 2026
- **`_normalize_amount()`** : Remplace `_restore_millimes` dans `merge_node`. Gère 5 cas de confusion : espaces milliers, format européen virgule+point, double point tunisien, virgule seule, entier sans décimal (Règle C : `montant_tva=4750, net_a_payer=30.75` → `4.750`)
- **Articles normalisés** : `_normalize_amount` appliqué aussi à `prix_unitaire_ht` et `total_ht_ligne` (résout `PU=1109244 → 1109.244` pour F1)
- **`timbre_fiscal` Règle B** : Entier > 30 DT → ÷ 1000 (au lieu de → `null`) — `1000 → 1.000 DT`

### v4.2 — Juin 2026
- **Règle 3ter** : Nouveau cas `CAS A-ter` — espace milliers + point millimes : `"1 109.244"` → `1109.244` (évite la perte du point décimal)
- **Règle 3qua** : Vérification de cohérence `montant_tva < net_a_payer` — détecte les erreurs de lecture millimes
- **Règle 3 renforcée** : Exemples explicites `4.750 → 4.750` et `2.969 → 2.969` — jamais écrire `4750` ou `2969`
- **Règle 4bis** : Ajout des synonymes complets du timbre fiscal : `"Droit de timbre"` (seul), `"TIMBRE FISCAL LOI..."` (texte légal long)
- **Règle 0ter renforcée** : Interdit explicitement de copier le libellé `"Facture N°"` comme valeur — exemples ajoutés (`A/155200`, `FT-230600`, `1729/900000`)

### v4.1 — Juin 2026
- **`merge_node`** : Post-traitements automatiques (correction devise EUR, validation timbre, restauration millimes)
- **Prompt** : 17 règles d'extraction

### v4.0 — Juin 2026
- Pipeline complet OCR.space + Groq qwen3-32b (texte) + Groq llama-4-scout (vision)
- Sections I (Articles), II (Visuel), III (Paiement) structurées
- Support FODEC, `montant_ht_ar`, `net_htva`
