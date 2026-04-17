# ODSINET — Système OCR GLM · Extraction d'entités sur factures

**PFE 2026 · Goubaa Hanen · ENIG Gabès**

Système complet d'extraction automatique d'entités clés à partir d'images de factures, basé sur le modèle multimodal **GLM-OCR fine-tuné avec LoRA**, déployé sur GPU serverless (Modal.com), avec interface React professionnelle et stockage PostgreSQL.

---

## Table des matières

- [Architecture](#architecture)
- [Pipeline complet](#pipeline-complet)
- [Modèle GLM-OCR](#modèle-glm-ocr)
- [Backend Modal (GPU)](#backend-modal-gpu)
- [API locale (BDD)](#api-locale-bdd)
- [Frontend React](#frontend-react)
- [Base de données PostgreSQL](#base-de-données-postgresql)
- [Authentification multi-utilisateur](#authentification-multi-utilisateur)
- [Human-in-the-Loop](#human-in-the-loop)
- [Frontend Streamlit](#frontend-streamlit-conservé)
- [Performances](#performances)
- [Stack technique](#stack-technique)
- [Lancer le projet](#lancer-le-projet)

---

## Architecture

```
OCR-systeme-pfe_GLM/
├── modal_app.py              # Backend FastAPI GPU (Modal.com · T4)
├── local_api/
│   ├── main.py               # API FastAPI locale → PostgreSQL
│   └── requirements.txt
├── frontend/                 # Interface React + Vite
│   ├── src/
│   │   ├── pages/
│   │   │   ├── Dashboard.tsx       # KPIs temps réel + graphiques
│   │   │   ├── UploadPage.tsx      # Upload + OCR + HITL
│   │   │   ├── DocumentsPage.tsx   # Historique des analyses
│   │   │   ├── CalendarPage.tsx    # Vue calendrier
│   │   │   ├── ProfilePage.tsx     # Profil utilisateur
│   │   │   ├── SettingsPage.tsx    # Paramètres + gestion users
│   │   │   └── LoginPage.tsx       # Auth + inscription
│   │   ├── components/
│   │   │   └── AppLayout.tsx       # Layout responsive (sidebar + topbar)
│   │   ├── lib/
│   │   │   ├── api.ts              # Client Modal backend
│   │   │   ├── auth.ts             # Auth multi-utilisateur localStorage
│   │   │   └── i18n.ts             # Traductions FR / EN
│   │   └── contexts/
│   │       └── AppContext.tsx      # Theme + langue globaux
│   └── package.json
├── app/                      # Interface Streamlit (conservée)
│   ├── main.py
│   └── _pages/
│       └── inference_hitl.py
├── data/                     # Données d'entraînement et d'évaluation
├── diagrams/                 # Logos et schémas
└── .env                      # Variables d'environnement
```

---

## Pipeline complet

```
┌─────────────────────────────────────────────────────────────────────┐
│                        PIPELINE OCR ODSINET                         │
└─────────────────────────────────────────────────────────────────────┘

  [Image facture]
        │
        ▼
  ┌─────────────┐
  │  Navigateur │  React · localhost:3000
  │  (Upload)   │
  └──────┬──────┘
         │ multipart/form-data
         ▼
  ┌─────────────────────────────────┐
  │  Backend Modal (GPU T4)         │
  │  modal_app.py · FastAPI         │
  │                                 │
  │  1. Réception image             │
  │  2. Chargement GLM-OCR          │
  │     (Goubaa/glmocr-factures)    │
  │  3. Tokenisation + encodage     │
  │  4. Inférence LoRA float16      │
  │  5. Parsing JSON entités        │
  └──────────────┬──────────────────┘
                 │ JSON { entities, full_text, timing }
                 ▼
  ┌─────────────────────────────────┐
  │  Frontend React                 │
  │  Affichage résultats            │
  │  + Human-in-the-Loop (HITL)     │
  │  → Correction manuelle entités  │
  └──────────────┬──────────────────┘
                 │ POST /factures
                 ▼
  ┌─────────────────────────────────┐
  │  API locale · localhost:8001    │
  │  local_api/main.py · FastAPI    │
  └──────────────┬──────────────────┘
                 │ INSERT INTO factures
                 ▼
  ┌─────────────────────────────────┐
  │  PostgreSQL 16 · localhost:5432 │
  │  Base : postgres                │
  │  Table : factures               │
  └─────────────────────────────────┘
```

---

## Modèle GLM-OCR

| Paramètre | Valeur |
|-----------|--------|
| Modèle publié | `Goubaa/glmocr-factures` |
| Modèle de base | `zai-org/GLM-OCR` |
| Fine-tuning | LoRA · merged · float16 |
| GPU | NVIDIA T4 · CUDA 12.1 |
| PyTorch | 2.4.1 |
| Transformers | HuggingFace git HEAD |
| Cold-start | ~40s (1er appel / après 2 min idle) |
| Inférence (warm) | ~65s par facture |

### Entités extraites

| Entité | Description | Exemple |
|--------|-------------|---------|
| `CLIENT` | Nom du client | `IEEE TUNISIA SECTION` |
| `FOURNISSEUR` | Nom du fournisseur | `STE ZRELLI DE COMMERCE` |
| `NUMERO_FACTURE` | Numéro de la facture | `509-2022` |
| `DATE_FACTURE` | Date de la facture | `06/04/2022` |
| `MONTANT_TTC` | Montant total TTC | `40.470` |

### Économie de crédits GPU

Le container GPU s'éteint automatiquement après **2 minutes** d'inactivité (`scaledown_window=120`). Vous payez uniquement le temps réel de calcul GPU.

---

## Backend Modal (GPU)

### Déploiement

```bash
modal deploy modal_app.py
```

### URL de production

```
https://<workspace>--glmocr-backend-fastapi-app.modal.run
```

### Endpoints

| Méthode | Route | Description |
|---------|-------|-------------|
| `GET` | `/health` | État du backend + infos GPU |
| `GET` | `/labels` | Liste des entités cibles |
| `POST` | `/predict` | Inférence image → entités JSON |

### Format réponse `/predict`

```json
{
  "entities": [
    { "label": "CLIENT",         "text": "IEEE TUNISIA SECTION" },
    { "label": "FOURNISSEUR",    "text": "STE ZRELLI DE COMMERCE" },
    { "label": "NUMERO_FACTURE", "text": "509-2022" },
    { "label": "DATE_FACTURE",   "text": "06/04/2022" },
    { "label": "MONTANT_TTC",    "text": "40.470" }
  ],
  "full_text": "<think></think>\n{...}",
  "timing": {
    "inference_ms": 4136,
    "total_ms": 4136
  }
}
```

---

## API locale (BDD)

Serveur FastAPI local qui fait le pont entre React et PostgreSQL.

### Lancer

```bash
cd local_api
pip install -r requirements.txt
uvicorn main:app --reload --port 8001
```

### Endpoints

| Méthode | Route | Description |
|---------|-------|-------------|
| `GET` | `/health` | État de l'API locale |
| `POST` | `/factures` | Insérer une facture en BDD |
| `GET` | `/factures` | Lister les factures (50 dernières) |
| `DELETE` | `/factures/{id}` | Supprimer une facture |

### Format payload `/factures` (POST)

```json
{
  "filename": "facture_001.jpg",
  "entities": {
    "CLIENT":         "IEEE TUNISIA SECTION",
    "FOURNISSEUR":    "STE ZRELLI DE COMMERCE",
    "NUMERO_FACTURE": "509-2022",
    "DATE_FACTURE":   "06/04/2022",
    "MONTANT_TTC":    "40.470"
  },
  "corrections": {
    "CLIENT": {
      "original": "IEEE TUNISIA",
      "corrected": "IEEE TUNISIA SECTION"
    }
  },
  "full_text": "<think></think>\n{...}",
  "timing": { "inference_ms": 4136, "total_ms": 4136 }
}
```

---

## Frontend React

### Installation et lancement

```bash
cd frontend
npm install
npm run dev
# → http://localhost:3000
```

### Pages

| Page | Route | Description |
|------|-------|-------------|
| Connexion | `/login` | Auth + création de compte |
| Tableau de bord | `/` | KPIs réels + graphiques |
| Analyser une facture | `/upload` | OCR + HITL + export |
| Historique | `/documents` | Liste des analyses |
| Calendrier | `/calendar` | Vue par date |
| Mon profil | `/profile` | Modifier profil + mot de passe |
| Paramètres | `/settings` | Backend URL + thème + langue + users |

### Fonctionnalités

- **Thème** : dark / light (persistant localStorage)
- **Langue** : Français / English (i18n complet)
- **Responsive** : mobile · tablette · desktop
- **Multi-utilisateur** : sessions isolées par utilisateur
- **Historique par user** : clé `odsinet_history_{username}`

### Comptes par défaut

| Utilisateur | Mot de passe | Rôle |
|-------------|-------------|------|
| `admin` | `admin123` | Administrateur |
| `hanen` | `pfe2025` | Administrateur |

---

## Base de données PostgreSQL

### Installation

```powershell
winget install PostgreSQL.PostgreSQL.16
```

### Connexion

```powershell
psql -U postgres
# mot de passe : postgres
```

### Schéma table `factures`

```sql
CREATE DATABASE odsinet_db;
\c odsinet_db

CREATE TABLE factures (
    id              SERIAL PRIMARY KEY,
    filename        VARCHAR(255)     NOT NULL,
    client          VARCHAR(500)     DEFAULT 'N/A',
    fournisseur     VARCHAR(500)     DEFAULT 'N/A',
    numero_facture  VARCHAR(100)     DEFAULT 'N/A',
    date_facture    VARCHAR(50)      DEFAULT 'N/A',
    montant_ttc     VARCHAR(100)     DEFAULT 'N/A',
    corrected       BOOLEAN          DEFAULT FALSE,
    full_text       TEXT,
    inference_ms    INTEGER,
    created_at      TIMESTAMP        DEFAULT NOW()
);
```

### Import Python depuis JSON exporté

```python
import json, psycopg

with open("facture.json") as f:
    data = json.load(f)

e = data["entities"]
conn = psycopg.connect("postgresql://postgres:postgres@localhost/postgres")
cur  = conn.cursor()
cur.execute("""
    INSERT INTO factures
        (filename, client, fournisseur, numero_facture, date_facture, montant_ttc,
         corrected, full_text, inference_ms)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
""", (
    data["filename"],
    e.get("CLIENT",          "N/A"),
    e.get("FOURNISSEUR",     "N/A"),
    e.get("NUMERO_FACTURE",  "N/A"),
    e.get("DATE_FACTURE",    "N/A"),
    e.get("MONTANT_TTC",     "N/A"),
    "corrections" in data,
    data.get("full_text"),
    data.get("timing", {}).get("inference_ms"),
))
conn.commit()
```

---

## Authentification multi-utilisateur

- Stockage : **localStorage** (`odsinet_users`, `odsinet_session`)
- Historique isolé par user : `odsinet_history_{username}`
- Rôles : `admin` (accès gestion users) / `user`
- Avatar avec initiales + couleur personnalisable
- Changement de mot de passe depuis le profil
- Les comptes `admin` et `hanen` sont protégés (non supprimables)

---

## Human-in-the-Loop

Après chaque analyse OCR, l'utilisateur peut :

1. **Corriger** une entité erronée (clic sur ✏ → édition inline)
2. **Rétablir** la valeur originale (bouton ↩)
3. **Valider** les corrections → mise à jour localStorage + historique
4. **Enregistrer en BDD** → POST vers l'API locale → INSERT PostgreSQL
5. **Exporter JSON** → fichier avec version finale + diff corrections

Le JSON exporté contient toujours les **5 entités** (valeur corrigée ou `N/A`) pour garantir un INSERT SQL complet.

---

## Frontend Streamlit (conservé)

Interface originale conservée dans `app/` pour référence.

```bash
venv\Scripts\activate          # Windows
source venv/bin/activate       # Linux/Mac
streamlit run app/main.py
```

---

## Performances

| Métrique | Valeur |
|----------|--------|
| Taux de succès global | 94.2% |
| F1-score global | 0.912 |
| Précision CLIENT | 82.7% |
| Précision FOURNISSEUR | 89.7% |
| Précision NUMERO_FACTURE | 87.4% |
| Précision DATE_FACTURE | 92.1% |
| Précision MONTANT_TTC | 96.2% |
| Temps inférence (warm) | ~65s |
| Temps cold-start | ~40s |

---

## Stack technique

### Backend GPU
| Outil | Version | Rôle |
|-------|---------|------|
| Modal.com | — | Serverless GPU T4 |
| FastAPI | 0.115 | API REST |
| PyTorch | 2.4.1 | Inférence |
| Transformers | HF git | GLM-OCR |
| Python | 3.11 | Runtime |

### API locale
| Outil | Version | Rôle |
|-------|---------|------|
| FastAPI | 0.135 | API REST locale |
| psycopg | 3.3 | Connecteur PostgreSQL |
| uvicorn | 0.44 | Serveur ASGI |
| PostgreSQL | 16 | Base de données |

### Frontend
| Outil | Version | Rôle |
|-------|---------|------|
| React | 18 | UI |
| Vite | 5 | Bundler |
| TypeScript | 5 | Typage |
| Tailwind CSS | 3 | Styles |
| shadcn/ui | — | Composants |
| framer-motion | 11 | Animations |
| recharts | 2 | Graphiques |
| react-router-dom | 6 | Routing |
| react-day-picker | 8 | Calendrier |
| lucide-react | — | Icônes |

---

## Lancer le projet

### 1 — Backend GPU Modal (cloud)
```bash
modal deploy modal_app.py
```

### 2 — API locale BDD (terminal 1)
```bash
cd local_api
uvicorn main:app --reload --port 8001
```

### 3 — Frontend React (terminal 2)
```bash
cd frontend
npm run dev
# → http://localhost:3000
```

### 4 — PostgreSQL (service Windows)
```powershell
# Démarrer si arrêté
net start postgresql-x64-16

# Vérifier la table
psql -U postgres -c "SELECT COUNT(*) FROM factures;"
```

---

