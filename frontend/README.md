# GLM-OCR Frontend — React + Vite

Interface utilisateur React pour le système d'extraction d'entités sur factures basé sur le modèle **GLM-OCR fine-tuné**.

> PFE 2025 · Goubaa Hanen · ENIG Gabès

---

## Stack technique

| Technologie | Version | Rôle |
|------------|---------|------|
| React | 18.3 | Framework UI |
| Vite | 5.4 | Bundler / Dev server |
| TypeScript | 5.8 | Typage statique |
| Tailwind CSS | 3.4 | Styles utilitaires |
| shadcn/ui | latest | Composants UI (Radix) |
| framer-motion | 12 | Animations |
| recharts | 2.15 | Graphiques dashboard |
| react-router-dom | 6.30 | Routing |

---

## Lancer le projet

### Prérequis
- Node.js >= 18
- npm ou bun

### Installation

```bash
cd frontend
npm install
```

### Développement

```bash
npm run dev
# Ouverture sur http://localhost:8080
```

### Build production

```bash
npm run build
# Sortie dans frontend/dist/
```

---

## Authentification

| Identifiant | Mot de passe | Rôle |
|------------|-------------|------|
| `admin` | `admin123` | Administrateur |
| `hanen` | `pfe2025` | Administrateur |

Les sessions sont stockées dans `localStorage` (pas de serveur d'auth requis).

---

## Pages

| Route | Page | Description |
|-------|------|-------------|
| `/login` | Connexion | Authentification |
| `/` | Tableau de bord | KPIs, graphiques, documents récents |
| `/upload` | Analyser une facture | Upload -> inférence GLM-OCR -> résultats |
| `/documents` | Historique | Liste des analyses (localStorage) |
| `/settings` | Paramètres | URL API, infos modèle, test connexion |

---

## Backend

Le frontend appelle directement le backend FastAPI déployé sur Modal :

```
https://<workspace>--glmocr-backend-fastapi-app.modal.run
```

Endpoints utilisés :
- `GET /health` — vérification de l'état du backend
- `POST /predict` — inférence sur une image de facture (multipart/form-data)

---

## Entités extraites

Le modèle extrait 5 entités :

| Entité | Description |
|--------|-------------|
| `CLIENT` | Nom du client |
| `FOURNISSEUR` | Nom du fournisseur |
| `NUMERO_FACTURE` | Numéro de la facture |
| `DATE_FACTURE` | Date (format JJ/MM/AAAA) |
| `MONTANT_TTC` | Montant total TTC |

---

## Variables d'environnement

Créez un fichier `.env.local` dans `frontend/` :

```env
VITE_API_URL=https://<workspace>--glmocr-backend-fastapi-app.modal.run
```

---

## Structure des fichiers clés

```
frontend/src/
├── App.tsx                    # Routes + auth guard
├── lib/
│   ├── api.ts                 # Client Modal (checkHealth, predictInvoice)
│   ├── auth.ts                # Auth localStorage (login, logout, getSession)
│   └── mockData.ts            # Données démo dashboard
├── pages/
│   ├── LoginPage.tsx          # Page de connexion
│   ├── Dashboard.tsx          # Tableau de bord GLM-OCR
│   ├── UploadPage.tsx         # Inférence réelle (appel API Modal)
│   ├── DocumentsPage.tsx      # Historique localStorage
│   └── SettingsPage.tsx       # Config + test backend
└── components/
    ├── AppLayout.tsx           # Sidebar + topbar (branding GLM-OCR)
    └── ui/                    # Composants shadcn/ui
```
