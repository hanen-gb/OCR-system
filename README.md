# ODSINET — Système OCR Multi-Agent GLM · Extraction d'entités sur documents commerciaux tunisiens

**PFE 2026 · Goubaa Hanen · ENIG Gabès**

Système complet d'extraction automatique d'entités clés à partir de factures et lettres de change tunisiennes, basé sur une architecture **multi-agent LangGraph**, un modèle **GLM-OCR fine-tuné avec LoRA**, et une interface React professionnelle.

---

## Table des matières

- [Architecture globale](#architecture-globale)
- [Frontend React](#frontend-react)
  - [Stack technique](#stack-technique-frontend)
  - [Structure des fichiers](#structure-des-fichiers)
  - [Authentification](#authentification--authts)
  - [Contextes globaux](#contextes-globaux)
  - [Pages](#pages)
  - [Composants partagés](#composants-partagés)
- [Backend GLM-OCR](#backend-glm-ocr--backendmainpy--port-7860)
  - [Modèle](#modèle)
  - [Pipeline d'inférence](#pipeline-dinférence)
  - [Endpoints GLM](#endpoints-glm-ocr)
- [Backend Agents](#backend-agents--assistantapimainpy--port-8002)
  - [Endpoint /analyse](#endpoint-analyse--pipeline-principal)
  - [Agent 1 — L'Extracteur](#agent-1--lextracteur)
  - [Agent 2 — L'Auditeur](#agent-2--lauditeur)
  - [Agent 3 — L'Analyste](#agent-3--lanalyste)
  - [Agent 4 — Le Chatbot](#agent-4--le-chatbot)
  - [Base SQLite](#base-sqlite)
- [Clés API](#clés-api-requises)
- [Observabilité LangSmith](#observabilité-langsmith)
- [Performances du modèle](#performances-du-modèle)
- [Lancer le projet](#lancer-le-projet)

---

## Architecture globale

```
Frontend (React/Vite)         :3000
         ↕  REST (multipart + JSON)
Backend Agents (FastAPI)      :8002   ← orchestration LangGraph (Agents 1, 2, 3, 4)
         ↕  REST (image → JSON)
Backend GLM-OCR (FastAPI)     :7860   ← inférence modèle Vision-Language
```

```
┌──────────────────────────────────────────────────────────────────────┐
│                         PIPELINE ODSINET                             │
└──────────────────────────────────────────────────────────────────────┘

  [Facture / Lettre de change]
              │
              ▼
  ┌───────────────────────┐
  │   Frontend React      │  localhost:3000
  │   Upload de fichier   │
  └──────────┬────────────┘
             │ POST /predict (image)
             ▼
  ┌───────────────────────────────┐
  │  Backend GLM-OCR · :7860      │
  │  Modèle Goubaa/glmocr-factures│
  │  → 5 entités de base (JSON)   │
  └──────────┬────────────────────┘
             │ POST /analyse (fichier + base_entities)
             ▼
  ┌───────────────────────────────────────────────────────────┐
  │  Backend Agents · :8002                                   │
  │                                                           │
  │  Agent 1 (Extracteur)  → 30+ entités enrichies           │
  │       ↓                                                   │
  │  Agent 2 (Auditeur)    → rapport audit + verdict          │
  │       ↓                                                   │
  │  Agent 3 (Analyste)    → anomalies + insights IA          │
  │       ↓                                                   │
  │  Agent 4 (Chatbot)     → réponses conversationnelles      │
  └──────────┬────────────────────────────────────────────────┘
             │ JSON { analyse_contextuelle, audit, analyse }
             ▼
  ┌───────────────────────┐
  │   Frontend React      │  Affichage résultats
  │   HITL + Chatbot IA   │  Correction manuelle
  └───────────────────────┘
```

---

## FRONTEND REACT

### Stack technique Frontend

| Outil | Rôle |
|---|---|
| React 18 + TypeScript | Framework UI |
| Vite 5 | Bundler / dev server |
| React Router v6 | Routing SPA |
| shadcn/ui | Composants primitifs (Button, Dialog, Input, Tabs, Table…) |
| Tailwind CSS | Utilitaires CSS |
| framer-motion | Animations fluides (sidebar, transitions, cartes) |
| lucide-react | Icônes |
| Recharts | Graphiques (AreaChart, PieChart) |
| TanStack Query | Cache requêtes HTTP |

---

### Structure des fichiers

```
frontend/src/
├── App.tsx                     ← Router principal + providers globaux
├── main.tsx                    ← Point d'entrée Vite
├── lib/
│   ├── auth.ts                 ← Auth multi-utilisateur (localStorage)
│   ├── api.ts                  ← Appels REST vers les deux backends
│   └── i18n.ts                 ← Traductions FR / EN
├── contexts/
│   ├── AppContext.tsx           ← Thème dark/light + langue globaux
│   └── ChatbotContext.tsx       ← État du chatbot IA flottant
├── components/
│   ├── AppLayout.tsx            ← Sidebar + topbar + layout général
│   ├── ChatbotWidget.tsx        ← Widget chatbot flottant (bas droite)
│   └── ui/                     ← 40+ composants shadcn/ui
└── pages/
    ├── LoginPage.tsx            ← Page de connexion / inscription
    ├── Dashboard.tsx            ← Tableau de bord analytics temps réel
    ├── UploadPage.tsx           ← Page d'analyse (page principale)
    ├── DocumentsPage.tsx        ← Historique des documents
    ├── CalendarPage.tsx         ← Vue calendrier des échéances
    ├── ProfilePage.tsx          ← Profil utilisateur + import photo
    └── SettingsPage.tsx         ← Paramètres (thème, langue, users admin)
```

---

### Authentification — auth.ts + JWT FastAPI

Système en deux couches :

**Couche 1 — Identité (localStorage, `auth.ts`)** : stockage des profils, vérification du mot de passe, gestion de session. Pas de réseau.

**Couche 2 — Autorisation API (JWT, FastAPI)** : après un login réussi, le frontend appelle `POST /token` sur FastAPI. L'agent retourne un JWT HS256 signé `{sub: username, role}`. Ce token est stocké dans `localStorage["odsinet_agent_token"]` et envoyé dans chaque requête agent via `Authorization: Bearer <token>`. Le endpoint `DELETE /documents/{type}/{number}` vérifie le token et rejette avec 403 si `role != "admin"`.

**Flux JWT au login :**
```
1. login(username, password)  →  localStorage  (session)
2. fetchToken(username, role) →  POST /token   (FastAPI)
3. JWT stocké dans localStorage["odsinet_agent_token"]
4. analyseDocument()          →  Authorization: Bearer <jwt>
5. deleteDocument()           →  Authorization: Bearer <jwt>  [admin seulement]
```

**Variable d'environnement optionnelle** (`assistant/.env`) :
```env
JWT_SECRET=votre-secret-de-production-difficile-a-deviner
```
Si absent, la valeur par défaut `change-me` est utilisée (suffisant en local).

**Séparation des rôles concrète** :

| Action | user | admin |
|---|---|---|
| Upload + analyse | ✅ | ✅ |
| Corriger entités (HITL) | ✅ | ✅ |
| Chatbot, historique, export | ✅ | ✅ |
| Voir tous les comptes (SettingsPage) | ❌ (masqué UI) | ✅ |
| Supprimer un utilisateur | ❌ | ✅ (sauf admin + hanen) |
| `DELETE /documents/{type}/{n}` | ❌ (403 FastAPI) | ✅ (JWT vérifié) |

> **Pour un déploiement production** : ajouter JWT expiry (`exp`), refresh token, et une colonne `owner_username` dans PostgreSQL (déjà présente) pour filtrer les documents par utilisateur côté SQL.

Système multi-utilisateur dont la base d'identité est **entièrement côté client** (localStorage). Pas de backend d'authentification pour les profils.

**Interface `UserProfile`** :
```typescript
{
  username: string;
  password: string;
  displayName: string;
  email: string;
  role: "admin" | "user";
  avatarColor: string;
  photo?: string;      // base64 data-URL (import photo profil)
  bio: string;
  createdAt: string;
  lang: "fr" | "en";
  theme: "dark" | "light";
}
```

**Comptes par défaut** (toujours présents, non supprimables) :

| Utilisateur | Mot de passe | Rôle |
|---|---|---|
| `admin` | `admin123` | Administrateur |
| `hanen` | `pfe2025` | Administrateur |

**Fonctions exportées** :

| Fonction | Description |
|---|---|
| `login(username, password)` | Vérifie les credentials, écrit la session en localStorage |
| `logout()` | Supprime la session courante |
| `getSession()` | Lit le profil de l'utilisateur connecté |
| `isAuthenticated()` | Booléen pour la protection des routes |
| `register(username, password, displayName, email)` | Crée un nouveau compte (role "user") |
| `updateProfile(username, updates)` | Met à jour displayName, email, bio, photo, avatarColor |
| `changePassword(username, current, new)` | Vérifie l'ancien avant de modifier |
| `deleteUser(username)` | Interdit sur "admin" et "hanen" |
| `getAllUsers()` | Fusionne utilisateurs stockés avec les defaults |
| `getHistoryKey(username)` | Clé localStorage d'historique par user |

**Clés localStorage** :
- `odsinet_users` → tableau JSON de tous les profils
- `odsinet_session` → profil de l'utilisateur connecté
- `odsinet_history_<username>` → historique des analyses isolé par utilisateur

---

### Contextes globaux

**AppContext** (`contexts/AppContext.tsx`) :
- Gère `theme: "dark" | "light"` persisté dans `odsinet_theme`
- Gère `lang: "fr" | "en"` persisté dans `odsinet_lang`
- Applique la classe `.light` sur `<html>` pour Tailwind
- Expose `t(key: TranslationKey)` : fonction de traduction FR/EN

**ChatbotContext** (`contexts/ChatbotContext.tsx`) :
- Gère l'état ouvert/fermé du widget chatbot flottant
- Partage le contexte document courant (entités, audit, analyse) entre `UploadPage` et `ChatbotWidget`

---

### Pages

#### App.tsx — Router & Routes protégées

`ProtectedRoute` redirige vers `/login` si `isAuthenticated()` retourne false, sinon enveloppe la page dans `<AppLayout>`.

Routes déclarées :

| Route | Page | Protection |
|---|---|---|
| `/login` | LoginPage | Publique |
| `/` | Dashboard | Protégée |
| `/upload` | UploadPage | Protégée |
| `/documents` | DocumentsPage | Protégée |
| `/calendar` | CalendarPage | Protégée |
| `/profile` | ProfilePage | Protégée |
| `/settings` | SettingsPage | Protégée |
| `*` | NotFound | — |

---

#### AppLayout — Sidebar & Navigation

Wrapper de toutes les pages protégées. Structure :

**Sidebar desktop** (collapsible animée, 252px ↔ 60px via framer-motion) :
- Deux sections : "Main" (Dashboard, Analyze, History, Calendar) et "System" (Profile, Settings)
- Indicateur de page active animé (`layoutId="active-nav"`)
- Toggles thème + langue en bas
- Avatar + displayName + email + bouton Logout en pied de sidebar

**Sidebar mobile** : drawer animé (`x: -280 → 0`) avec overlay noir semi-transparent (`bg-black/50`), fermé au clic sur l'overlay ou les liens.

**Topbar** (h-14) : hamburger mobile + badge "Backend Active" avec point vert pulsant (`animate-pulse`).

**ChatbotWidget** monté en superposition globale sur toutes les pages.

**Composant Avatar** : affiche la photo importée (base64) en priorité, sinon initiales colorées.

---

#### Dashboard

Affiche des analytics calculées **en temps réel depuis l'historique localStorage** de l'utilisateur connecté.

**6 KPI cards** :
- Total documents analysés
- Fournisseurs uniques (dédupliqués par nom normalisé)
- Clients uniques
- Taux de complétion (document avec ≥ 4 entités extraites = complet)
- Temps d'inférence moyen (en secondes)
- Date et nom du dernier document analysé

**2 graphiques Recharts** :
- `AreaChart` avec gradient : temps d'inférence des 10 derniers documents
- `PieChart` en donut : taux de détection par entité (CLIENT, FOURNISSEUR, NUMERO_FACTURE, DATE_FACTURE, MONTANT_TTC)

**Table historique** : 6 derniers documents avec toutes leurs entités extraites.

---

#### UploadPage — Page principale d'analyse

Orchestre l'ensemble du pipeline d'analyse.

**Flux d'analyse** :
1. Dépôt ou sélection d'un fichier (JPG, PNG, PDF)
2. `POST :7860/predict` → GLM-OCR → 5 entités de base
3. `POST :8002/analyse` (multipart + `base_entities` JSON) → Agent 1 + 2 + 3
4. Affichage des résultats : entités enrichies, rapport d'audit avec verdict, rapport analyste avec niveau d'alerte
5. **HITL (Human-in-the-Loop)** : correction manuelle des entités par l'utilisateur
6. Bouton "Re-auditer" → `POST :8002/audit` avec les entités corrigées
7. Sauvegarde dans l'historique localStorage de l'utilisateur

---

#### DocumentsPage

Historique complet des analyses depuis le localStorage de l'utilisateur. Affiche nom de fichier, date, entités extraites et statut d'audit. Permet la suppression d'entrées individuelles.

---

#### CalendarPage

Vue calendrier des documents. Positionne les factures et lettres de change sur leurs dates (date facture ou date d'échéance). Visualisation des échéances à venir.

---

#### ProfilePage

Formulaire de modification du profil : photo (import base64), displayName, email, bio. Changement de mot de passe avec vérification de l'ancien. Sauvegarde via `updateProfile()` et `changePassword()` de `auth.ts`.

---

#### SettingsPage

3 sections :
1. **Apparence** : toggle Dark / Light avec boutons Sun/Moon
2. **Langue** : Français / English
3. **Gestion utilisateurs** *(admin uniquement)* : liste tous les utilisateurs avec avatar/photo, rôle, badge "protégé" pour admin/hanen, bouton suppression rouge pour les autres

---

### Composants partagés

#### ChatbotWidget

Widget flottant en bas à droite, visible sur toutes les pages. Quand un document est analysé, injecte automatiquement le contexte dans chaque message :
- Entités extraites enrichies
- Rapport d'audit (verdict + détails checks)
- Rapport analyste (niveau d'alerte + insights)

Appelle `POST :8002/chat` avec l'historique de conversation + contexte. Affiche les réponses de l'Agent 4 (Groq llama-3.3-70b).

---

---

## BACKEND GLM-OCR — `backend/main.py` · Port 7860

### Rôle

Premier backend dédié à l'**inférence du modèle Vision-Language GLM-OCR** fine-tuné sur les documents commerciaux tunisiens. Extrait 5 entités de base depuis une image.

### Modèle

| Paramètre | Valeur |
|---|---|
| Modèle publié | `Goubaa/glmocr-factures` |
| Base | `zai-org/GLM-OCR` (ZhipuAI) |
| Fine-tuning | LoRA mergé sur factures tunisiennes |
| Source locale | `backend/model/glm_model/` (si présent) |
| Chargement | Singleton via `lifespan` FastAPI (une seule fois au démarrage) |
| Device | CUDA float16 si GPU, sinon CPU float32 |
| Max new tokens | 256 |
| Max image size | 1024px (côté max, resize LANCZOS) |

**Entités extraites (5)** :

| Entité | Description | Exemple |
|---|---|---|
| `CLIENT` | Nom du client | `IEEE TUNISIA SECTION` |
| `FOURNISSEUR` | Nom du fournisseur | `STE ZRELLI DE COMMERCE` |
| `NUMERO_FACTURE` | Numéro de la facture | `509-2022` |
| `DATE_FACTURE` | Date (format JJ/MM/AAAA) | `06/04/2022` |
| `MONTANT_TTC` | Montant total TTC | `40.470` |

### Pipeline d'inférence

Fonction `run_glm(pil_image)` :
1. Conversion image → RGB
2. Resize si > 1024px (côté max, LANCZOS)
3. Construction du message avec le template de chat GLM :
   ```python
   [{"role": "user", "content": [{"type": "image", ...}, {"type": "text", "text": PROMPT}]}]
   ```
4. Prompt fixe d'extraction des 5 entités (identique à l'entraînement)
5. `model.generate()` avec `max_new_tokens=256`, `do_sample=False`
6. Décodage uniquement des tokens générés (pas du prompt)
7. `parse_glm_output()` : regex `\{[^{}]*\}` pour extraire le JSON brut
8. Fallback : `N/A` pour toutes les entités si parsing impossible

### Endpoints GLM-OCR

| Route | Méthode | Description |
|---|---|---|
| `POST /predict` | POST | `multipart/form-data` image → `{entities, full_text, timing}` |
| `GET /health` | GET | `{status, models_ready, model, device, source}` |
| `GET /labels` | GET | `{labels: [...5 entités...], count: 5}` |

**Format réponse `/predict`** :
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

> `box: null` — GLM-OCR ne fournit pas de coordonnées spatiales (limitation connue vs LayoutXLM).

---

---

## BACKEND AGENTS — `assistant/api/main.py` · Port 8002

### Rôle

Second backend dédié à l'**orchestration des 4 agents LangGraph**. Reçoit le fichier document + les entités GLM, exécute la chaîne Agent1 → Agent2 → Agent3, et expose le chatbot Agent4.

### Endpoints

| Route | Méthode | Agents | Description |
|---|---|---|---|
| `POST /analyse` | POST | 1 + 2 + 3 | Pipeline complet : extraction + audit + analyse comportementale |
| `POST /audit` | POST | 2 seul | Re-auditer un JSON d'entités (après correction HITL) |
| `POST /chat` | POST | 4 | Chatbot contextuel avec historique de conversation |
| `GET /documents` | GET | — | Liste les documents en base SQLite |
| `DELETE /documents/{type}/{number}` | DELETE | — | Supprime un document (annule une détection doublon) |
| `GET /health` | GET | — | `{status: "ok", agents: [...], version: "3.0"}` |

---

### Endpoint `/analyse` — Pipeline principal

**Paramètres** (multipart/form-data) :
- `file` : image (JPG/PNG/BMP/TIFF) ou PDF
- `document_type` : `"facture"` | `"lettre_de_change"` | `"auto"` (défaut)
- `base_entities` : JSON string des entités GLM (optionnel)

**Séquence d'exécution** :
```
1. extractor_graph.invoke(file_path, document_type, base_entities)
      → complete_entities (30+ champs enrichis)

2. auditor_graph.invoke(complete_entities, base_entities)
      → audit_report {verdict, checks, anomalies}

3. analyst_graph.invoke(complete_entities, audit_report)
      → analyst_report {alert_level, stats, insights}
```

**Réponse** :
```json
{
  "analyse_contextuelle": { "...30+ entités..." },
  "audit": {
    "status_validite": "VALIDÉ | ERREUR_CALCUL | DOUBLON | SIGNATURE_MANQUANTE | ...",
    "checks": { "arithmetique": [...], "tva": {...}, "net_a_payer": {...}, "gouvernance": {...} }
  },
  "analyse": {
    "alert_level": "NORMAL | ATTENTION | ALERTE",
    "anomalies": [...],
    "insights": "Texte d'analyse généré par LLM..."
  },
  "file_type": "image | pdf_native | pdf_scanned",
  "status": "ok"
}
```

---

### Agent 1 — L'Extracteur

**Fichier** : `assistant/agents/extractor/graph.py` + `assistant/agents/extractor/tools.py`

**État** (`ExtractorState`) : `file_path`, `document_type`, `base_entities`, `file_type`, `native_text`, `vision_text`, `augmented_entities`, `visual_fields`, `complete_entities`, `messages`

**Graphe LangGraph — 6 nœuds** :

```
detect_type
    │
    └─ route_extraction()
            ├─ "native"  → extract_native (pdfplumber)
            └─ "vision"  → extract_vision (OCR.space → Gemini → Groq)
                    │
              extract_entities (LLM texte : 30+ entités)
                    │
              extract_visual (LLM vision : signatures, cachets)
                    │
                merge_node (fusion + 6 post-traitements)
```

**5 outils** (`@tool`) :

| Outil | Ligne | Description |
|---|---|---|
| `detect_file_type()` | l.261 | pdfplumber → `pdf_native` / `pdf_scanned` / `image` |
| `extract_text_pdf_native()` | l.306 | pdfplumber : texte brut + tableaux |
| `extract_text_vision()` | l.346 | OCR.space → Gemini 2.0-flash → Groq llama-4-scout-17b |
| `extract_augmented_entities()` | l.879 | Groq qwen3-32b → HF Qwen2.5-7B → Gemini 1.5-flash |
| `extract_visual_fields()` | l.661 | Groq llama-4-scout-17b → Gemini 2.0-flash |

**Chaîne LLM texte** (`_call_llm()` l.49) :
- Groq `qwen3-32b` (primaire, ultra-rapide)
- HuggingFace `Qwen2.5-7B-Instruct` (fallback texte)
- Google `Gemini 1.5-flash` (dernier recours)

**Prompt** : 17 règles métier — détection bilinguisme FR/AR, format DT à 3 décimales, matricule fiscal tunisien, FODEC, timbre 0.600 DT, reconnaissance traite vs facture.

**6 post-traitements dans `merge_node`** :
- Détection GPS dans les montants (pattern `JJ.MM.AAAA` confondu avec montant)
- Restauration des millimes (3 décimales DT)
- Détection EUR → signalement pour conversion
- Validation timbre fiscal (standard tunisien : 0.600 DT)
- Normalisation format date → `JJ/MM/AAAA`
- Normalisation matricule fiscal → `XXXXXXXXX/A/X/XXX`

---

### Agent 2 — L'Auditeur

**Fichier** : `assistant/agents/auditor/graph.py` + `assistant/agents/auditor/checks.py`

**Graphe LangGraph — 7 nœuds séquentiels** :

| Nœud | Ligne | Fonction |
|---|---|---|
| `prepare_node` | l.98 | Normalise les types str→float, initialise l'état |
| `arithmetic_node` | l.137 | `check_arithmetic_lines()` : QTE × PU × (1-remise%) ≈ Total_HT_ligne |
| `tva_node` | l.146 | `validate_tva_globale()` : Σ(HT × taux_TVA) ≈ montant_TVA |
| `net_node` | l.230 | `check_net_a_payer()` : base_HTVA + TVA + timbre ≈ net à payer |
| `doublon_node` | l.293 | `check_doublon()` SQLite sur `(doc_type, doc_number)` |
| `gouvernance_node` | l.300 | `check_governance()` : signatures + cachets |
| `verdict_node` | l.308 | Agrège tous les checks, détermine le verdict final |

**Tolérance arithmétique** : 0.005 DT (5 millimes) pour absorber les arrondis.

**Spécificité `_parse_tva_rate()`** (l.11) : gère les erreurs OCR — `"2016"` → 20%, `"1906"` → 19%, valeurs > 100 → correction automatique.

**Priorité du verdict** :
```
DOUBLON > SIGNATURE_MANQUANTE > ERREUR_CALCUL > ERREUR_TVA > ERREUR_NET_A_PAYER > VALIDÉ
```

**Check `check_net_a_payer()`** — Priorité base HTVA :
1. `net_htva` extrait (NET H.TVA déjà avec remise + FODEC)
2. `montant_ht + fodec` (si net_htva absent)
3. `montant_ht` seul (si pas de FODEC)

**Check gouvernance par type** :
- **Facture** : `signature_presente` + `cachet_present`
- **Lettre de change** : `signature_tire` + `signature_tireur` + `cachet_present` + `aval_bancaire` (optionnel)

---

### Agent 3 — L'Analyste

**Fichier** : `assistant/agents/analyst/graph.py` + `assistant/agents/analyst/checks.py`

**Graphe LangGraph — 5 nœuds** :

| Nœud | Ligne | Fonction |
|---|---|---|
| `load_history` | l.61 | `list_documents(500)` SQLite → historique des 500 derniers docs |
| `compute_stats` | l.68 | `compute_supplier_stats()` + `compute_global_stats()` |
| `detect_anomalies` | l.86 | Comparaison montant courant vs historique fournisseur et global |
| `generate_insights` | l.107 | Génération texte analyse via Groq qwen3-32b |
| `verdict` | l.162 | Calcul niveau d'alerte global |

**Seuils de détection d'anomalies** :

| Condition | Niveau |
|---|---|
| Premier document de ce fournisseur | ATTENTION |
| Montant déviant de ≥ 30% de la moyenne fournisseur | ATTENTION |
| Montant déviant de ≥ 60% de la moyenne fournisseur | ALERTE |
| Montant > 3× la moyenne globale | ATTENTION |

---

### Agent 4 — Le Chatbot

**Fichier** : `assistant/agents/chatbot/graph.py`

**Graphe LangGraph — 3 nœuds** :

| Nœud | Ligne | Fonction |
|---|---|---|
| `understand_intent` | l.106 | Classification par mots-clés (entités / audit / analyse / général) |
| `query_db` | l.120 | Enrichissement depuis SQLite si pertinent |
| `generate_response` | l.128 | Génération réponse LLM avec contexte injecté |

**`_build_context_block()`** (l.56) : injecte dans le system prompt toutes les entités extraites + rapport audit + rapport analyste du document courant.

**Chaîne LLM chatbot** :
- Groq `llama-3.3-70b` (primaire)
- Groq `llama3-groq-70b-8192` (fallback)
- Google `Gemini 2.0-flash` (dernier recours)

---

### Base SQLite

**Fichier** : `assistant/data/documents.db`

**Table `documents`** :
```sql
CREATE TABLE documents (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    doc_type    TEXT    NOT NULL,   -- "facture" | "lettre_de_change"
    doc_number  TEXT    NOT NULL,   -- clé de déduplication
    fournisseur TEXT,
    montant     REAL,
    date_doc    TEXT,
    first_seen  TEXT    NOT NULL    -- ISO 8601
);

CREATE UNIQUE INDEX idx_doc_key ON documents (doc_type, doc_number);
```

**Fonctions** (`assistant/agents/auditor/db.py`) :

| Fonction | Description |
|---|---|
| `check_doublon(doc_type, doc_number)` | Retourne `NOUVEAU` / `DOUBLON` / `INCONNU` |
| `register_document(...)` | INSERT OR IGNORE (idempotent) |
| `list_documents(limit)` | SELECT DESC ORDER BY id (partagé avec Agent 3) |
| `delete_document(doc_type, doc_number)` | Annule une détection doublon |

La base est **partagée entre les Agents 2, 3 et 4** — Agent 2 y écrit, Agent 3 y lit pour les statistiques, Agent 4 peut y faire des requêtes pour le contexte.

---

---

## Clés API requises

Créer un fichier `.env` à la racine du dossier `assistant/` :

```env
GROQ_API_KEY=gsk_...
GOOGLE_API_KEY=AIza...
OCR_SPACE_API_KEY=K_...
HUGGINGFACEHUB_API_TOKEN=hf_...
LANGCHAIN_API_KEY=ls__...
LANGCHAIN_PROJECT=OCR-PFE-GLM
LANGCHAIN_TRACING_V2=true
```

| Clé | Modèles utilisés |
|---|---|
| `GROQ_API_KEY` | qwen3-32b (extraction), llama-4-scout-17b (vision), llama-3.3-70b (chatbot) |
| `GOOGLE_API_KEY` | Gemini 2.0-flash (OCR fallback + vision), Gemini 1.5-flash (texte fallback) |
| `OCR_SPACE_API_KEY` | OCR primaire (25 000 req/mois gratuit) |
| `HUGGINGFACEHUB_API_TOKEN` | Qwen2.5-7B-Instruct (fallback extraction texte) |
| `LANGCHAIN_API_KEY` | LangSmith observabilité |

---

## Observabilité LangSmith

Les Agents 1, 2 et 3 sont tracés automatiquement dans LangSmith. Chaque invocation est loggée avec :
- `run_name` : `"Extracteur — facture.pdf"` / `"Auditeur — facture.pdf"` / `"Analyste — facture.pdf"`
- `tags` : `["agent1", "extracteur", "facture"]` etc.
- `metadata` : `{filename, document_type}`

Tableau de bord : [smith.langchain.com](https://smith.langchain.com) — projet `OCR-PFE-GLM`.

---

## Performances du modèle

| Métrique | Valeur |
|---|---|
| Taux de succès global | 94.2% |
| F1-score global | 0.912 |
| Précision CLIENT | 82.7% |
| Précision FOURNISSEUR | 89.7% |
| Précision NUMERO_FACTURE | 87.4% |
| Précision DATE_FACTURE | 92.1% |
| Précision MONTANT_TTC | 96.2% |
| Dataset d'entraînement | 4 020 documents tunisiens |
| Fine-tuning | LoRA mergé — zai-org/GLM-OCR |

---

## Lancer le projet

### 1 — Backend GLM-OCR (terminal 1)

```bash
cd backend
pip install -r requirements.txt
python main.py
# → http://localhost:7860
```

### 2 — Backend Agents LangGraph (terminal 2)

```bash
cd assistant
pip install -r requirements.txt
uvicorn api.main:app --host 0.0.0.0 --port 8002 --reload
# → http://localhost:8002
```

### 3 — Frontend React (terminal 3)

```bash
cd frontend
npm install
npm run dev
# → http://localhost:3000
```

### Vérification

```bash
# Santé Backend GLM-OCR
curl http://localhost:7860/health

# Santé Backend Agents
curl http://localhost:8002/health

# Entités supportées
curl http://localhost:7860/labels
```

---

## Stack technique complète

### Backend GLM-OCR

| Outil | Version | Rôle |
|---|---|---|
| FastAPI | 0.115+ | API REST |
| PyTorch | 2.4.1 | Inférence GPU/CPU |
| Transformers (HuggingFace) | git HEAD | GLM-OCR |
| Pillow | — | Traitement image |
| Python | 3.11 | Runtime |

### Backend Agents

| Outil | Version | Rôle |
|---|---|---|
| FastAPI | 0.135+ | API REST |
| LangGraph | — | Orchestration agents |
| LangChain | — | Abstractions LLM |
| pdfplumber | — | Extraction PDF natif |
| SQLite3 | stdlib | Déduplication + historique |
| Groq SDK | — | qwen3-32b, llama-4-scout, llama-3.3 |
| Google GenerativeAI | — | Gemini 2.0-flash, 1.5-flash |
| HuggingFace Hub | — | Qwen2.5-7B-Instruct |
| LangSmith | — | Observabilité |
| Python | 3.11 | Runtime |

### Frontend

| Outil | Version | Rôle |
|---|---|---|
| React | 18 | UI |
| Vite | 5 | Bundler |
| TypeScript | 5 | Typage |
| Tailwind CSS | 3 | Styles utilitaires |
| shadcn/ui | — | Composants primitifs |
| framer-motion | 11 | Animations |
| Recharts | 2 | Graphiques analytics |
| React Router | 6 | Routing SPA |
| TanStack Query | 5 | Cache requêtes HTTP |
| lucide-react | — | Icônes |

---

*ODSINET — PFE 2026 · Goubaa Hanen · École Nationale d'Ingénieurs de Gabès (ENIG)*
