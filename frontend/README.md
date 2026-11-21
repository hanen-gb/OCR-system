# Frontend — document review interface

React interface of the document AI system: upload or photograph an invoice or a bill of exchange, review and correct
the fields extracted by GLM-OCR (human-in-the-loop), run the LangGraph agents, and browse the history.

## Stack

| Technology | Role |
|---|---|
| React 18 + Vite | UI and bundling |
| TypeScript | Static typing |
| Tailwind CSS + shadcn/ui (Radix) | Styling and UI components |
| Recharts | Dashboard charts |
| framer-motion, lucide-react | Animations, icons |
| react-router-dom 6 | Routing |

## Structure

```
frontend/src/
├── pages/          Login, Dashboard, Upload, Documents, Calendar, Profile, Settings
├── components/     AppLayout (sidebar + top bar), ChatbotWidget, shadcn/ui components
├── contexts/       AppContext (language + theme), ChatbotContext (current document)
└── lib/
    ├── api.ts      inference API (POST /predict) and agents API (port 8002) client
    ├── auth.ts     local demo authentication
    ├── i18n.ts     English and French strings
    └── mockData.ts demo data for an empty dashboard
```

## Pages

| Page | Route | Content |
|---|---|---|
| Upload | `/upload` | Upload or camera capture (images are resized to 1024 px before sending), extracted fields with inline correction and reset, agent results (contextual analysis, audit checks, anomalies), re-audit after correction, save to PostgreSQL |
| Dashboard | `/` | KPIs, document-type distribution, inference times, recent documents |
| Documents | `/documents` | History stored in PostgreSQL, search, deletion (admin) |
| Calendar | `/calendar` | Documents processed per day |
| Profile | `/profile` | Name, photo, bio, password |
| Settings | `/settings` | Theme, language, user management (admin) |

A floating chatbot (Agent 4) is available on every page and uses the current document as context.

## Language

Every visible string goes through `t(key)` from `useApp()`; the keys are defined in
[`src/lib/i18n.ts`](src/lib/i18n.ts) with an English and a French entry.

## Authentication

The frontend uses a lightweight **local demo** authentication stored in `localStorage`
(`odsinet_session`, `odsinet_users`, `odsinet_history_<user>`). The demo `admin` password is read from
`VITE_DEMO_ADMIN_PASSWORD`; if it is not set, a random one is generated and printed once in the browser console.
After login, the agents API issues a signed JWT (`POST /token`) used for its protected routes.

## Configuration and start-up

```bash
cd frontend
npm install
cp .env.example .env      # VITE_API_URL (inference API), VITE_AGENT_URL (agents API), VITE_DEMO_ADMIN_PASSWORD
npm run dev               # http://localhost:3000
npm run build             # production build
npx tsc --noEmit          # type check
```

## Fields displayed

| Invoice | Bill of exchange |
|---|---|
| `CLIENT`, `FOURNISSEUR`, `NUMERO_FACTURE`, `DATE_FACTURE`, `MONTANT_TTC` (GLM-OCR) | `NUMERO_TRAITE`, `DATE_ECHEANCE`, `MONTANT`, `TIREUR`, `TIRE`, `RIB`, `DOMICILIATION` (GLM-OCR) |
| `MONTANT_HT`, `MONTANT_TVA`, `TIMBRE_FISCAL`, `NET_A_PAYER_LETTRES`, items… (Extractor agent) | `MONTANT_EN_LETTRES`, endorsements, guarantee… (Extractor agent) |

Field names are kept as the model and API return them (client, supplier, invoice number, invoice date, total amount
incl. VAT; bill number, due date, amount, drawer, drawee, bank identifier, paying bank).
