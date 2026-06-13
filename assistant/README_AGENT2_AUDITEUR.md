# Agent 2 — L'Auditeur

> Dernière mise à jour : Juin 2026 — v4.5

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
lettres          ─── Couche 3 : net_a_payer_lettres vs net_a_payer numérique   ← v4.3
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
notification     ─── Email d'alerte si montant > seuil ou échéance proche
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
| `check_lettres` | `dict?` | **v4.3** — Cross-check `net_a_payer_lettres` vs `net_a_payer` numérique |
| `check_doublon` | `dict?` | Détection doublon SQLite |
| `check_gouvernance` | `dict?` | Signatures / tampons |
| `status_validite` | `str?` | **Output** — statut final |
| `audit_report` | `dict?` | **Output** — rapport complet |

---

## Nœuds

### `prepare_node`
Résout les champs clés depuis `complete_entities` et `base_entities`.
- Facture : `num_facture` **ou `numero_facture`** (v3.0), `fournisseur.nom`, `montant_ttc`, `date_facture`
- Lettre de change : `num_lettre`, `tireur`, `montant`, `date_echeance`

**v3.0 — Détection de valeur hallucinée (`_is_hallucinated`) :**
Si `montant_ttc` est une valeur aberrante → elle est rejetée (`montant_ttc = null`) avant de polluer les checks suivants.
Deux critères de détection :
1. **Chiffres répétitifs** : `333333`, `111111`, `999999`… (4+ chiffres identiques)
2. **Aberration statistique** : valeur > 10× la somme réelle des `total_ht_ligne` des articles

**v3.0 — Gestion virgule décimale (`_num`) :**
`"135,660"` → `135.660` ; `"1.200,50"` → `1200.50`. Fonctionne pour les notations FR et tunisiennes.

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

**v3.0 — Fallback taux global :**
Si `tva_rate_ligne` est `null` pour toutes les lignes (factures sans colonne TVA individuelle), le nœud injecte automatiquement le `tva_rate` global sur chaque ligne avant le calcul. Évite les faux positifs "TVA ERREUR" sur les factures françaises/télécoms.

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

**v3.0 — Fallback `montant_ht` depuis les articles :**
Si `montant_ht` est `null` globalement (fréquent sur les factures télécom/services), le nœud reconstitue automatiquement `montant_ht = Σ(total_ht_ligne)`. Évite le faux positif "Net à payer ERREUR" quand le total HT est absent du pied de facture.

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

### `lettres_node` *(v4.3)*

Couche 3 — cross-check `net_a_payer_lettres` (texte) vs `net_a_payer` (numérique).

**Principe :** le texte en lettres est l'ancre de vérité. Il ne souffre d'aucune ambiguïté de séparateur décimal (point/virgule), contrairement au montant numérique qui peut avoir été mal parsé par l'OCR ou le LLM.

**Exemple :** `"MILLE TROIS CENT VINGT DINARS SIX CENTS MILLIMES"` → `1320.600 DT` sans ambiguïté.

**Parser français `parse_lettres_to_amount()` :**

| Texte | Résultat |
|-------|----------|
| `"MILLE TROIS CENT VINGT DINARS SIX CENTS MILLIMES"` | `1320.600` |
| `"TRENTE DINARS ET SEPT CENT CINQUANTE MILLIMES"` | `30.750` |
| `"DIX NEUF DINARS CINQ CENT QUATRE VINGT DIX NEUF MILLIMES"` | `19.599` |
| `"DEUX CENT QUATRE VINGT QUATORZE DINARS"` | `294.000` |

**Composites français gérés :** `QUATRE VINGT DIX` (90), `QUATRE VINGT` (80), `SOIXANTE DIX` (70), `DIX NEUF/HUIT/SEPT` (17-19).

**Règle `\b` (v4.4) :** les regex `DIX NEUF/HUIT/SEPT` utilisent `\bDIX\b` pour ne pas matcher le `DIX` terminal de `QUATRE_VINGT_DIX`. Sans cette frontière, `"CINQ CENT QUATRE VINGT DIX NEUF"` produisait `QUATRE_VINGT_DIX_NEUF` (token inconnu) au lieu de `90 + 9 = 99`.

**Résultat `check_lettres` :**
```json
{
  "valeur_lettres"  : 1320.600,
  "valeur_extraite" : 1320.600,
  "ecart"           : 0.0,
  "status"          : "OK",
  "detail"          : "Cohérence lettres/chiffres confirmée"
}
```

Tolérance : **500 millimes** (les lettres omettent parfois les millimes).
Retourne `INCOMPLET` si `net_a_payer_lettres` absent ou non parseable.

---

### `verdict_node`
Calcule le `status_validite` final par priorité décroissante :

| Priorité | Condition | Status |
|----------|-----------|--------|
| 1 | doublon détecté | `DOUBLON` |
| 2 | signature/tampon manquant **ET** non facture électronique | `SIGNATURE_MANQUANTE` |
| 3 | erreur calcul arithmétique | `ERREUR_CALCUL` |
| 4 | erreur TVA | `ERREUR_TVA` |
| 5 | erreur Net à payer | `ERREUR_NET_A_PAYER` |
| **6** | **net_a_payer ≠ valeur des lettres (écart > 500 mill.)** | **`ERREUR_MONTANT_LETTRES`** |
| — | tout OK | `VALIDÉ` |

Si `status == "NOUVEAU"` → appelle `register_document()` pour enregistrer en base.

**v4.2 — Cachet tunisien = validation légale (`verdict_node`) :**
En droit tunisien, un cachet officiel (tampon humide) équivaut à une validation légale, même en l'absence de signature manuscrite.
`SIGNATURE_MANQUANTE` n'est levé que si **cachet_present = false ET signature_presente = false** simultanément.
Résultat : les factures portant un tampon officiel sont correctement classées `VALIDÉ`.

**v3.0 — Détection générique de facture électronique :**
Les factures de services (télécom, énergie, eau…) ne comportent jamais de signature manuscrite. Le verdict ne lève pas `SIGNATURE_MANQUANTE` si les 3 conditions suivantes sont vraies :
1. `logo_detecte = true` — document d'une entité identifiée
2. `etat_document = "original"` — document natif numérique
3. Articles = résumé global uniquement — pas de QTE/PU individuels, ou désignations de type "Total HT", "Abonnement", "Forfait"…

**v3.0 — Détection de document incomplet :**
Si `montant_ht`, `montant_tva` et `montant_ttc` sont tous `null` mais que des articles existent → `document_incomplet: true` dans le rapport. Indique que l'image est probablement tronquée (bloc totaux hors cadre).

**v3.0 — Correction `_parse_tva_rate` :**
Taux > 100 = erreur OCR (ex: `"2016"` au lieu de `"20%"`) → correction automatique par correspondance des premiers chiffres avec les taux connus (7, 13, 19, 20, 25).

**v4.0 — Validation et correction du taux TVA global (`tva_node`) :**
Si le taux extrait n'est pas dans les taux connus (7, 13, 19, 20, 25), recalcul depuis `montant_tva / montant_ht × 100`, puis arrondi au taux connu le plus proche (tolérance ±3%). Corrige les erreurs OCR type "18" au lieu de "19".

**v4.0 — Triple fallback pour `montant_ht` (`net_node`) :**
1. Depuis `montant_ht_ar` (Total HT Après Remise)
2. Somme des `total_ht_ligne` des articles
3. **Rétro-calcul** : `HT = TTC - TVA - Timbre - FODEC` — permet de valider le Net à payer même quand le HT global est absent du JSON

**v4.0 — `check_arithmetic_lines` avec remise par ligne :**
Formule : `QTE × PU × (1 - remise_pct_ligne/100) ≈ total_ht_ligne`. Gère les factures avec colonne `%RM` (remise par article).

**v4.0 — `check_net_a_payer` avec FODEC et `net_htva` :**
Formule adaptée au marché tunisien : `net_htva + TVA + Timbre ≈ net_a_payer`.
- Priorité 1 : `net_htva` (déjà inclut remise + FODEC)
- Priorité 2 : `montant_ht + fodec`
- Priorité 3 : `montant_ht` seul

**v4.0 — Détection valeur hallucinée enrichie (`_is_hallucinated`) :**
Ajout du Cas 3 : `value > montant_ht × 5` → valeur aberrante même sans articles (factures de services).

**v4.0 — Gestion virgule décimale (`_num`) :**
`"135,660"` → `135.660` ; `"1.200,50"` → `1200.50`. Fonctionne pour les notations FR et tunisiennes.

**v4.1 — Calcul automatique `montant_tva` quand null (`tva_node` + `net_node`) :**
Si `montant_tva` est `null` mais `tva_rate` + `montant_ht` (ou Σ articles) disponibles :
```
montant_tva = montant_ht × tva_rate / 100
```
Corrige le cas où Agent 1 manque la ligne TVA du tableau récapitulatif.
Exemple : `100.839 × 19% = 19.159` → Net à payer `100.839 + 19.159 + 0.600 = 120.598` ✓

**v4.1 — Remise globale distribuée dans `tva_node` :**
Si `remise_globale` est présente (valeur négative), elle est distribuée proportionnellement sur chaque ligne avant le calcul TVA : `total_ht_ligne × (1 - |remise| / Σ HT)`. Évite le faux positif TVA ERREUR sur les factures avec réduction globale (ex: Pixmania).

---

### `notification_node`

Vérifie les conditions d'alerte et envoie un **message WhatsApp via Twilio** *(v4.5)*.

**Conditions déclenchantes :**

| Condition | Seuil | Variable `.env` |
|---|---|---|
| Montant TTC > seuil financier | 5 000 DT (défaut) | `ALERT_THRESHOLD_DT` |
| Échéance dans ≤ N jours | 7 jours (défaut) | `ALERT_DEADLINE_DAYS` |
| Échéance déjà dépassée | — | automatique |

**Message WhatsApp** (Markdown Twilio — gras, émojis) :
```
*[OCR-PFE] Action requise*
────────────────────────
*Type :* Facture
*N° :* FA-2024-0517
*Montant TTC :* 20,754.000 DT
*Statut audit :* Doublon détecté 🔁
────────────────────────
  ⚡ Montant TTC (20,754.000 DT) dépasse le seuil de 5,000 DT
```

**Champs ajoutés dans `audit_report` :**
```json
"notification": {
  "alerted"  : true,
  "sent"     : true,
  "alerts"   : ["Montant TTC (20,754.000 DT) dépasse le seuil de 5,000 DT"],
  "recipient": "whatsapp:+21671234567"
}
```

**Variables `.env` requises :**
```env
TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_AUTH_TOKEN=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_WHATSAPP_FROM=whatsapp:+14155238886
ALERT_WHATSAPP_TO=whatsapp:+216XXXXXXXX
ALERT_THRESHOLD_DT=5000
ALERT_DEADLINE_DAYS=7
```

**Setup Twilio WhatsApp Sandbox (gratuit, 5 min) :**
1. Créer un compte sur twilio.com/try-twilio
2. Console → **Messaging → Try it out → Send a WhatsApp message**
3. Depuis ton téléphone : envoyer `join <mot-clé>` au **+1 415 523 8886**
4. Copier `Account SID` + `Auth Token` depuis twilio.com/console
5. Remplir `.env` et relancer le serveur

---

## Fichiers sources

```
assistant/
├── agents/
│   └── auditor/
│       ├── __init__.py       ← exporte auditor_graph + audit_document
│       ├── graph.py          ← définition du graphe LangGraph (9 nœuds depuis v4.3)
│       ├── checks.py         ← vérifications arithmétique / TVA / net / gouvernance
│       │                        + parse_lettres_to_amount() + check_net_lettres() (v4.3)
│       ├── notifier.py       ← notification email (v4.2) — seuil financier + échéance
│       ├── auditor.py        ← orchestrateur fonction (legacy — wrapper autour du graphe)
│       └── db.py             ← SQLite : init_db, check_doublon, register_document
├── data/
│   └── documents.db          ← base SQLite (créée automatiquement)
└── state.py                  ← AuditorState TypedDict (+ check_lettres v4.3)
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

## Rapport d'audit (`audit_report`) — v4.3

```json
{
  "status_validite": "VALIDÉ",
  "document_incomplet": false,
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
    "base_htva"    : 546.217,
    "base_label"   : "net_htva",
    "montant_tva"  : 103.781,
    "timbre_fiscal": 0.600,
    "fodec"        : 5.408,
    "net_calcule"  : 650.598,
    "net_extrait"  : 650.598,
    "ecart"        : 0.0,
    "status"       : "OK"
  },
  "check_lettres_vs_net": {
    "valeur_lettres"  : 650.598,
    "valeur_extraite" : 650.598,
    "ecart"           : 0.0,
    "status"          : "OK",
    "detail"          : "Cohérence lettres/chiffres confirmée"
  },
  "gouvernance": {
    "status": "OK",
    "champs_manquants": []
  },
  "alerte_doublon": {
    "status": "NOUVEAU"
  },
  "notification": {
    "alerted"  : false,
    "sent"     : false,
    "alerts"   : [],
    "recipient": null
  }
}
```

**Nouveau champ `document_incomplet` (v3.0) :**
- `true` → bloc totaux absent (image tronquée ou document incomplet) → affiché en alerte orange dans le frontend
- `false` → document complet

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

---

## Historique des versions

### v4.5 — Juin 2026
- **`notification_node`** : Basculement Gmail → **WhatsApp via Twilio**. `send_alert_email()` remplacé par `send_alert_whatsapp()`. Message formaté en Markdown WhatsApp (gras, émojis, séparateurs). Variables `.env` : `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_WHATSAPP_FROM`, `ALERT_WHATSAPP_TO`
- `pip install twilio` ajouté aux dépendances

### v4.4 — Juin 2026
- **Bug `\bDIX\b` dans `_lettres_to_int`** : les regex `DIX[\s\-]+NEUF/HUIT/SEPT` n'avaient pas de frontière de mot `\b`. En présence de `QUATRE_VINGT_DIX NEUF`, le `DIX` terminal de `QUATRE_VINGT_DIX` était capturé, produisant le token fictif `QUATRE_VINGT_DIX_NEUF` (inconnu → ignoré) → perte des 99 millimes. Exemple corrigé : `"DIX NEUF DINARS CINQ CENT QUATRE VINGT DIX NEUF MILLIMES"` → `19.599` (était `19.5`)
- **13 cas de test lettres** validés (F1→F6, edge cases DIX SEPT, DIX HUIT, DIX NEUF×1000)

### v4.3 — Juin 2026
- **`lettres_node`** : Nouveau 9ème nœud — Couche 3 du système 3-couches de parsing. Cross-check `net_a_payer_lettres` (texte en français) vs `net_a_payer` numérique. Le texte en lettres est l'ancre de vérité (pas d'ambiguïté de séparateur décimal)
- **`parse_lettres_to_amount()`** dans `checks.py` : Parser français complet — gère `QUATRE VINGT DIX NEUF` (99), `MILLE`/`CENT` multiplicateurs, séparation DINARS/MILLIMES. Tolérance 500 millimes
- **`check_net_lettres()`** dans `checks.py` : Compare `net_a_payer_lettres` parsé avec `net_a_payer` extrait → statuts `OK` / `ERREUR_MONTANT` / `INCOMPLET`
- **Nouveau statut `ERREUR_MONTANT_LETTRES`** : Dans la chaîne de priorité, entre `ERREUR_NET_A_PAYER` et `VALIDÉ`
- **`state.py`** : Ajout de `check_lettres: Optional[dict]` dans `AuditorState`
- **Rapport** : Nouveau champ `check_lettres_vs_net` dans `audit_report`

### v4.2 — Juin 2026
- **`notification_node`** : Nouveau 8ème nœud — envoie un email d'alerte (plain text) si montant TTC > seuil (`ALERT_THRESHOLD_DT`, défaut 5 000 DT) ou échéance dans ≤ `ALERT_DEADLINE_DAYS` jours (défaut 7)
- **`notifier.py`** : Nouveau fichier — `check_alert_conditions()` + `send_alert_email()` via Gmail SMTP
- **`verdict_node`** : Correction `SIGNATURE_MANQUANTE` — en droit tunisien, `cachet_present=true` suffit comme validation légale ; `SIGNATURE_MANQUANTE` ne se lève plus si un cachet est présent
- **`state.py`** : Ajout de `notification_sent: Optional[bool]` et `notification_alerts: Optional[List[str]]` dans `AuditorState`

### v4.1 — Juin 2026
- **`tva_node`** : Calcul automatique `montant_tva = HT × taux` quand null (Agent 1 l'a manqué)
- **`tva_node`** : Remise globale distribuée proportionnellement avant calcul TVA
- **`net_node`** : `montant_tva` calculé si null pour `check_net_a_payer`
- **`merge_node`** : Détection devise EUR via regex `\bEUR\b` (évite faux positif "CAPTEUR")
- **README** : Historique des versions et post-traitements mis à jour

### v4.0 — Juin 2026
- **`tva_node`** : Validation du taux TVA global — si aberrant (ex: 18 au lieu de 19), recalcul depuis `TVA/HT` et correction vers le taux connu le plus proche
- **`net_node`** : Triple fallback pour `montant_ht` : 1) `montant_ht_ar`, 2) somme articles, 3) rétro-calcul `TTC - TVA - Timbre`
- **`check_arithmetic_lines`** : Intègre la remise par ligne — formule : `QTE × PU × (1 - remise/100) ≈ total_ht`
- **`check_net_a_payer`** : Gère FODEC et `net_htva` — formule tunisienne complète
- **`_is_hallucinated`** : Nouveau Cas 3 — aberration vs `montant_ht × 5`
- **`_num`** : Gestion virgule décimale (`"135,660"` → `135.660`)
- **Rapport** : `document_incomplet` flag visible dans le frontend (alerte orange)

### v3.0 — Juin 2026
- Détection générique facture électronique (sans liste hardcodée)
- Détection valeur hallucinée (`_is_hallucinated` — chiffres répétitifs + aberration vs articles)
- Détection document incomplet (`document_incomplet: true`)
- Correction `_parse_tva_rate` — taux OCR > 100 corrigé
- `prepare_node` : cherche `numero_facture` en plus de `num_facture`
- Gestion virgule décimale dans `_num`
- Fallback `montant_ht` depuis Σ(total_ht_ligne)
- Fallback taux TVA global si `tva_rate_ligne` absent sur toutes les lignes

### v2.0 — Version initiale (mai 2026)
- 7 nœuds LangGraph (prepare → arithmetic → tva → net → doublon → gouvernance → verdict)
- Vérification arithmétique ligne par ligne (tolérance 5 millimes)
- Validation TVA globale
- Conformité Net à payer
- Détection doublon SQLite
- Gouvernance (signatures, tampons)
