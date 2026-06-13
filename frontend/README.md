# OCR Multi-Agent Pipeline — Frontend

Interface web React pour le système d'extraction, d'audit et d'analyse de documents financiers tunisiens (**factures** et **lettres de change**) alimenté par un pipeline multi-agents LangGraph.

> PFE 2025 · Goubaa Hanen · ENIG Gabès · ODSInet

---

## Stack technique

| Technologie | Rôle |
|------------|------|
| React 18 + Vite | UI + bundling |
| TypeScript | Typage statique |
| Tailwind CSS | Styles utilitaires |
| shadcn/ui | Composants UI (Button, Card, Dialog…) |
| framer-motion | Animations de page / entrées |
| recharts | Graphiques Dashboard (AreaChart, PieChart) |
| lucide-react | Icônes |
| react-router-dom v6 | Routing SPA |

---

## Structure du projet

```
frontend/
├── src/
│   ├── contexts/
│   │   └── AppContext.tsx        # i18n (FR/EN) + thème dark/light
│   ├── lib/
│   │   ├── api.ts               # Appels API : Modal OCR + agent server :8002
│   │   ├── auth.ts              # Auth localStorage (session, utilisateurs)
│   │   └── i18n.ts              # Toutes les chaînes FR + EN
│   ├── components/
│   │   ├── ui/                  # shadcn/ui composants
│   │   ├── Layout.tsx           # Sidebar + topbar
│   │   └── AuditCheckCard.tsx   # Carte OK/ERREUR/INCOMPLET pour les checks
│   ├── pages/
│   │   ├── LoginPage.tsx        # Authentification
│   │   ├── Dashboard.tsx        # KPIs + graphiques + historique récent
│   │   ├── UploadPage.tsx       # Pipeline complet + HITL + chatbot
│   │   ├── DocumentsPage.tsx    # Historique PostgreSQL + localStorage
│   │   ├── ProfilePage.tsx      # Profil utilisateur + photo
│   │   ├── SettingsPage.tsx     # Thème + langue + gestion utilisateurs
│   │   └── CalendarPage.tsx     # Calendrier des échéances (traites)
│   └── main.tsx
├── index.html
└── vite.config.ts
```

---

## Pages

### LoginPage
- Authentification par username/password stockée en localStorage
- Comptes prédéfinis : `admin` / `hanen` (rôle admin), autres utilisateurs (rôle user)
- Session persistante via `localStorage`

### Dashboard
- **6 KPIs** : Documents analysés, Fournisseurs uniques, Clients distincts, Taux de complétion, Temps moyen d'inférence, Dernière analyse
- **Graphique** temps d'inférence (10 derniers documents — AreaChart)
- **Donut** taux de détection par entité, calculé sur le bon sous-ensemble (factures ou traites selon la majorité dans l'historique)
- **Tableau** des 6 dernières analyses
- Toutes les chaînes de texte passent par i18n (`t(key)`) — entièrement bilingue FR/EN

### UploadPage (analyse principale)
Orchestre le pipeline complet en 4 étapes :

```
1. Dépôt du fichier (drag & drop ou sélecteur)
         │
         ▼
2. Extraction (Agent 1) — entités structurées via GLM-OCR + LLM
   └─ HITL : correction manuelle des entités avant validation
         │
         ▼
3. Audit (Agent 2) — rapport de conformité KPI par KPI
   └─ Facture  : Arithmétique · TVA · Net à payer · Lettres · Doublon · Gouvernance
   └─ Traite   : Montant lettres · Échéance · RIB · Gouvernance · Doublon
         │
         ▼
4. Analyse (Agent 3) — statistiques fournisseur + anomalies + insights LLM
   └─ Chatbot (Agent 4) — questions/réponses sur le document
```

**KPI cards — Facture :** Arithmétique, TVA, Net à payer, Lettres, Doublon, Gouvernance

**KPI cards — Traite :** Montant lettres, Échéance, RIB Bancaire, Gouvernance, Doublon

**HITL (Human-in-the-Loop) :**
- Après l'extraction, l'utilisateur peut modifier les valeurs des entités dans un formulaire
- Les corrections sont passées comme `base_entities` au prochain appel `/analyse`
- `mergedContextual` fusionne entités Agent 1 + corrections manuelles pour l'affichage final

**Sauvegarde PostgreSQL :**
- Bouton "Enregistrer dans la BDD" → `POST /save`
- Affiche le message d'erreur PostgreSQL réel si l'enregistrement échoue (max 200 chars)

### DocumentsPage
Deux onglets :
- **PostgreSQL** : requête `GET /pg/documents` — affiche id, fichier, type, fournisseur, montant, statut audit, durée pipeline, propriétaire
  - Bouton "Vider SQLite" (admin uniquement) → `DELETE /admin/clear-sqlite` — resynchronise le détecteur de doublons avec PostgreSQL
- **Local** : historique `localStorage` — 10 derniers documents analysés dans le navigateur

### ProfilePage
- Informations de l'utilisateur connecté : nom, rôle, avatar
- Upload de photo de profil (stockée en base64 localStorage)

### SettingsPage
- **Thème** : dark / light (persisté en localStorage)
- **Langue** : Français / English (persisté en localStorage)
- **Gestion utilisateurs** (admin uniquement) : liste des comptes, suppression, comptes `admin` et `hanen` protégés

### CalendarPage
- Calendrier mensuel des échéances de lettres de change
- Données issues de l'historique localStorage

---

## Internationalisation (i18n)

Toutes les chaînes visibles à l'utilisateur passent par `t(key)` via le hook `useApp()`.

```tsx
const { t, lang, setLang } = useApp();
// Utilisation
<p>{t("dash_suppliers_sub").replace("{n}", String(totalDocs))}</p>
```

Les clés sont définies dans [src/lib/i18n.ts](src/lib/i18n.ts) avec une entrée FR et EN pour chaque clé. Pour ajouter une langue, étendre l'objet `translations` dans ce fichier.

---

## Authentification

Authentification légère basée sur `localStorage` (pas de JWT côté frontend).

```
localStorage:
  odsinet_session       → { username, role, displayName }
  odsinet_users         → tableau de tous les comptes
  odsinet_history_<usr> → historique des analyses de l'utilisateur
```

L'API backend `/token` génère un JWT utilisé uniquement pour les appels aux endpoints protégés (notamment `/save`, `/admin/clear-sqlite`).

---

## Connexion API

Deux backends :
- **GLM-OCR (Modal)** : extraction OCR via `src/lib/api.ts` → `POST /predict`
- **Agent server (port 8002)** : pipeline multi-agents → `POST /analyse`, `POST /chat`, `POST /save`, `GET /pg/documents`, etc.

La constante `AGENT_BASE_URL` dans `api.ts` pointe sur `http://localhost:8002`.

---

## Installation et démarrage

### Prérequis
- Node.js 20+
- Agent server backend démarré sur le port 8002

### Installation

```bash
cd frontend
npm install
```

### Développement

```bash
npm run dev
```

Ouvre l'interface sur `http://localhost:5173`.

### Build de production

```bash
npm run build
npm run preview   # prévisualiser le build
```

### Vérification TypeScript

```bash
npx tsc --noEmit
```

---

## Entités reconnues

### Facture

| Label | Description |
|-------|-------------|
| `CLIENT` | Nom du client |
| `FOURNISSEUR` | Nom du fournisseur |
| `NUMERO_FACTURE` | N° de facture |
| `DATE_FACTURE` | Date de la facture |
| `MONTANT_TTC` | Montant TTC |
| `MONTANT_HT` | Montant hors taxe |
| `MONTANT_TVA` | Montant TVA |
| `TIMBRE_FISCAL` | Timbre fiscal |
| `NET_A_PAYER_LETTRES` | Montant en toutes lettres |

### Lettre de change (traite)

| Label | Description |
|-------|-------------|
| `TIREUR` | Émetteur de la traite |
| `TIRE` | Destinataire |
| `RIB` | RIB bancaire 20 chiffres |
| `DOMICILIATION` | Banque domiciliataire |
| `MONTANT` | Montant en chiffres |
| `MONTANT_EN_LETTRES` | Montant en toutes lettres |
| `DATE_ECHEANCE` | Date d'échéance |
| `NUMERO_TRAITE` | N° de la traite |
