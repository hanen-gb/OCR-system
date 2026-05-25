# Agent 2 — L'Auditeur

Sous-graphe LangGraph de contrôle de conformité pour documents commerciaux tunisiens (factures et lettres de change).

---

## Architecture du graphe

```
START
  │
  ▼
prepare          ─── Résout doc_type, doc_number, fournisseur, montant_ttc
  │
  ▼
arithmetic       ─── QTE × PU_HT ≈ Total_HT (par ligne d'article)
  │
  ▼
tva              ─── Σ TVA lignes ≈ montant_tva global
  │
  ▼
net              ─── HT + TVA + Timbre ≈ Net à payer (TTC)
  │
  ▼
doublon          ─── SQLite : N° de document déjà enregistré ?
  │
  ▼
gouvernance      ─── Signatures, tampons, aval (champs visuels)
  │
  ▼
verdict          ─── Status final + enregistrement en base si NOUVEAU
  │
  ▼
 END
```

---

## État — `AuditorState`

| Champ | Type | Description |
|-------|------|-------------|
| `complete_entities` | `dict` | **Input** — entités fusionnées produites par l'Agent 1 |
| `base_entities` | `dict?` | **Input** — entités GLM brutes (optionnel) |
| `doc_type` | `str?` | `"facture"` ou `"lettre_de_change"` |
| `doc_number` | `str?` | Numéro de facture ou de lettre |
| `fournisseur` | `str?` | Nom du fournisseur |
| `montant_ttc` | `float?` | Montant TTC (DT avec millimes) |
| `date_doc` | `str?` | Date du document |
| `check_arithmetique` | `List[dict]?` | Résultat par ligne d'article |
| `check_tva` | `dict?` | Validation TVA globale |
| `check_net` | `dict?` | Conformité Net à payer |
| `check_doublon` | `dict?` | Détection doublon SQLite |
| `check_gouvernance` | `dict?` | Signatures / tampons |
| `status_validite` | `str?` | **Output** — statut final |
| `audit_report` | `dict?` | **Output** — rapport complet |

---

## Nœuds

### `prepare_node`
Résout les champs clés depuis `complete_entities` et `base_entities`.
- Facture : `num_facture`, `fournisseur.nom`, `montant_ttc`, `date_facture`
- Lettre de change : `num_lettre`, `tireur`, `montant`, `date_echeance`

### `arithmetic_node`
Appelle `check_arithmetic_lines(articles)`.
Pour chaque ligne : `QTE × PU_HT` vs `Total_HT` extrait.
Tolérance : **5 millimes (0.005 DT)**.

Résultat par ligne :
```json
{
  "article": "BOITE 2M ENCAST",
  "qte": 8,
  "pu_ht": 4.987,
  "total_ht_extrait": 39.896,
  "total_ht_calcule": 39.896,
  "ecart": 0.0,
  "status": "OK"
}
```
Statuts possibles : `OK` | `ERREUR` | `INCOMPLET` (champ manquant)

### `tva_node`
Appelle `validate_tva_globale(articles, montant_tva)`.
Calcule `Σ (Total_HT × taux_tva)` pour toutes les lignes, compare au `montant_tva` global extrait.

```json
{
  "tva_extraite": 12.345,
  "tva_calculee": 12.341,
  "ecart": 0.004,
  "status": "OK"
}
```

### `net_node`
Appelle `check_net_a_payer(montant_ht, montant_tva, timbre_fiscal, net_extrait)`.
Vérifie : `montant_ht + montant_tva + timbre_fiscal ≈ net_a_payer`.

```json
{
  "montant_ht": 100.0,
  "montant_tva": 19.0,
  "timbre_fiscal": 1.0,
  "net_calcule": 120.0,
  "net_extrait": 120.0,
  "ecart": 0.0,
  "status": "OK"
}
```

### `doublon_node`
Consulte `assistant/data/documents.db` (SQLite).
Clé d'unicité : `(doc_type, doc_number)`.

```json
{ "status": "NOUVEAU" }   // première occurrence
{ "status": "DOUBLON" }   // déjà enregistré
{ "status": "INCONNU" }   // doc_number indisponible
```

### `gouvernance_node`
Appelle `check_governance(complete_entities)`.
Vérifie les champs visuels extraits par la vision (Section II) :
- Facture : `cachet_fournisseur`, `signature_fournisseur`, `cachet_client`, `signature_client`
- Lettre de change : `aval_banque`, `cachet_tire`, `signature_tire`

```json
{
  "status": "OK",
  "champs_presents": ["cachet_fournisseur", "signature_fournisseur"],
  "champs_manquants": []
}
```

### `verdict_node`
Calcule le `status_validite` final par priorité décroissante :

| Priorité | Condition | Status |
|----------|-----------|--------|
| 1 | doublon détecté | `DOUBLON` |
| 2 | signature/tampon manquant | `SIGNATURE_MANQUANTE` |
| 3 | erreur calcul arithmétique | `ERREUR_CALCUL` |
| 4 | erreur TVA | `ERREUR_TVA` |
| 5 | erreur Net à payer | `ERREUR_NET_A_PAYER` |
| — | tout OK | `VALIDÉ` |

Si `status == "NOUVEAU"` → appelle `register_document()` pour enregistrer en base.

---

## Fichiers sources

```
assistant/
├── agents/
│   └── auditor/
│       ├── __init__.py       ← exporte auditor_graph + audit_document
│       ├── graph.py          ← définition du graphe LangGraph (7 nœuds)
│       ├── checks.py         ← fonctions de vérification arithmétique / TVA / net / gouvernance
│       ├── auditor.py        ← orchestrateur fonction (legacy — wrapper autour du graphe)
│       └── db.py             ← SQLite : init_db, check_doublon, register_document
├── data/
│   └── documents.db          ← base SQLite (créée automatiquement)
└── state.py                  ← AuditorState TypedDict
```

---

## Base SQLite — `documents.db`

Table `documents` :

| Colonne | Type | Description |
|---------|------|-------------|
| `id` | INTEGER PK | Auto-increment |
| `doc_type` | TEXT | `"facture"` ou `"lettre_de_change"` |
| `doc_number` | TEXT | Numéro du document |
| `fournisseur` | TEXT | Nom du fournisseur |
| `montant` | REAL | Montant TTC |
| `date_doc` | TEXT | Date du document |
| `created_at` | TEXT | Timestamp ISO8601 d'enregistrement |

Index UNIQUE sur `(doc_type, doc_number)` — garantit la détection de doublons.

---

## Tolérance arithmétique

Tous les contrôles numériques utilisent une tolérance de **5 millimes (0.005 DT)**, cohérente avec la notation tunisienne (3 décimales).

Exemple : `39.896 × 8 = 319.168` → accepte `319.165` à `319.173`.

---

## Rapport d'audit (`audit_report`)

```json
{
  "status_validite": "VALIDÉ",
  "doc_type": "facture",
  "doc_number": "FAC-2024-001",
  "fournisseur": "Sfax Clean SARL",
  "nb_articles": 3,
  "nb_erreurs_calcul": 0,
  "nb_lignes_incompletes": 0,
  "check_arithmetique_lignes": [...],
  "validation_tva_globale": {
    "tva_extraite": 12.345,
    "tva_calculee": 12.341,
    "ecart": 0.004,
    "status": "OK"
  },
  "conformite_net_a_payer": {
    "net_calcule": 120.0,
    "net_extrait": 120.0,
    "ecart": 0.0,
    "status": "OK"
  },
  "gouvernance": {
    "status": "OK",
    "champs_presents": ["cachet_fournisseur", "signature_fournisseur"],
    "champs_manquants": []
  },
  "alerte_doublon": {
    "status": "NOUVEAU"
  }
}
```

---

## API REST

### `POST /analyse` — Pipeline complet (Agent 1 + Agent 2)

```
multipart/form-data:
  file          : image ou PDF
  document_type : "facture" | "lettre_de_change" | "auto"
  base_entities : JSON string des entités GLM (optionnel)
```

Réponse :
```json
{
  "analyse_contextuelle": { ... },
  "audit": { "status_validite": "VALIDÉ", ... },
  "file_type": "image",
  "status": "ok"
}
```

### `POST /audit` — Audit seul (sans ré-extraction)

```json
{
  "complete_entities": { ... },
  "base_entities": { ... }
}
```

### `GET /documents` — Liste des documents enregistrés

```
?limit=50
```

### `DELETE /documents/{doc_type}/{doc_number}` — Supprime un doublon

---

## Lancer le serveur

```bash
cd assistant
uvicorn api.main:app --host 0.0.0.0 --port 8002 --reload
```

Visualiser le graphe dans LangSmith Studio :
```bash
cd assistant
langgraph dev
```
→ ouvre `http://localhost:2024` → Studio → sélectionner `agent_extracteur`

---

## LangSmith — Observabilité

Chaque invocation du graphe est tracée dans le projet **OCR-PFE-GLM** sur [smith.langchain.com](https://smith.langchain.com).

Variables d'environnement requises (`.env`) :
```
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=lsv2_pt_...
LANGCHAIN_PROJECT=OCR-PFE-GLM
```

Chaque run Agent 2 est taggué `["agent2", "auditeur"]` et porte le nom `"Auditeur — <filename>"`.
