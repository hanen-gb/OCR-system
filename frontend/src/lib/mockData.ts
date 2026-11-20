/**
 * mockData.ts — Données de démonstration pour le dashboard GLM-OCR
 * Adapté pour le modèle fine-tuné Goubaa/glmocr-factures (GLM-4V base)
 */

export interface ProcessedDocument {
  id: string;
  filename: string;
  type: "facture" | "devis" | "bon_commande" | "recu";
  date: string;
  client: string;
  supplier: string;
  amount: number;
  currency: string;
  docNumber: string;
  status: "processed" | "error" | "pending";
  inferenceMs: number;
  rawText: string;
  entities: Record<string, string>;
}

export const typeLabels: Record<string, string> = {
  facture: "Facture",
  devis: "Devis",
  bon_commande: "Bon de commande",
  recu: "Reçu",
};

export const typeBadgeClass: Record<string, string> = {
  facture: "bg-primary/10 text-primary",
  devis: "bg-success/10 text-success",
  bon_commande: "bg-warning/10 text-warning",
  recu: "bg-[hsl(262_80%_55%/0.1)] text-[hsl(262_80%_55%)]",
};

// Données GLM-OCR — résultats réels du modèle fine-tuné
export const mockDocuments: ProcessedDocument[] = [
  {
    id: "1",
    filename: "facture_ooredoo_2022.jpg",
    type: "facture",
    date: "21/09/2022",
    client: "OOREDOO",
    supplier: "GLOBAL DISTRIBUTION",
    amount: 212860,
    currency: "TND",
    docNumber: "2220000023632451",
    status: "processed",
    inferenceMs: 65200,
    rawText:
      '{"CLIENT": "OOREDOO", "FOURNISSEUR": "GLOBAL DISTRIBUTION", "DATE_FACTURE": "21/09/2022", "MONTANT_TTC": "212,860", "NUMERO_FACTURE": "2220000023632451"}',
    entities: {
      CLIENT: "OOREDOO",
      FOURNISSEUR: "GLOBAL DISTRIBUTION",
      DATE_FACTURE: "21/09/2022",
      MONTANT_TTC: "212,860",
      NUMERO_FACTURE: "2220000023632451",
    },
  },
  {
    id: "2",
    filename: "facture_steg_2023.png",
    type: "facture",
    date: "15/03/2023",
    client: "Client Particulier",
    supplier: "STEG",
    amount: 45800,
    currency: "TND",
    docNumber: "FAC-2023-001547",
    status: "processed",
    inferenceMs: 61400,
    rawText:
      '{"CLIENT": "Client Particulier", "FOURNISSEUR": "STEG", "DATE_FACTURE": "15/03/2023", "MONTANT_TTC": "458,00", "NUMERO_FACTURE": "FAC-2023-001547"}',
    entities: {
      CLIENT: "Client Particulier",
      FOURNISSEUR: "STEG",
      DATE_FACTURE: "15/03/2023",
      MONTANT_TTC: "458,00",
      NUMERO_FACTURE: "FAC-2023-001547",
    },
  },
  {
    id: "3",
    filename: "facture_topnet_2023.jpg",
    type: "facture",
    date: "08/07/2023",
    client: "Entreprise ABC",
    supplier: "TOPNET",
    amount: 12500,
    currency: "TND",
    docNumber: "TN-2023-098765",
    status: "processed",
    inferenceMs: 68900,
    rawText:
      '{"CLIENT": "Entreprise ABC", "FOURNISSEUR": "TOPNET", "DATE_FACTURE": "08/07/2023", "MONTANT_TTC": "125,00", "NUMERO_FACTURE": "TN-2023-098765"}',
    entities: {
      CLIENT: "Entreprise ABC",
      FOURNISSEUR: "TOPNET",
      DATE_FACTURE: "08/07/2023",
      MONTANT_TTC: "125,00",
      NUMERO_FACTURE: "TN-2023-098765",
    },
  },
  {
    id: "4",
    filename: "facture_sonede_2024.png",
    type: "facture",
    date: "20/01/2024",
    client: "Mohamed Ali Ben Salah",
    supplier: "SONEDE",
    amount: 8700,
    currency: "TND",
    docNumber: "SON-2024-334521",
    status: "processed",
    inferenceMs: 59800,
    rawText:
      '{"CLIENT": "Mohamed Ali Ben Salah", "FOURNISSEUR": "SONEDE", "DATE_FACTURE": "20/01/2024", "MONTANT_TTC": "87,00", "NUMERO_FACTURE": "SON-2024-334521"}',
    entities: {
      CLIENT: "Mohamed Ali Ben Salah",
      FOURNISSEUR: "SONEDE",
      DATE_FACTURE: "20/01/2024",
      MONTANT_TTC: "87,00",
      NUMERO_FACTURE: "SON-2024-334521",
    },
  },
  {
    id: "5",
    filename: "facture_tunisie_telecom.jpg",
    type: "facture",
    date: "12/04/2024",
    client: "SARL TechSolutions",
    supplier: "TUNISIE TELECOM",
    amount: 34200,
    currency: "TND",
    docNumber: "TT-2024-008812",
    status: "processed",
    inferenceMs: 72100,
    rawText:
      '{"CLIENT": "SARL TechSolutions", "FOURNISSEUR": "TUNISIE TELECOM", "DATE_FACTURE": "12/04/2024", "MONTANT_TTC": "342,00", "NUMERO_FACTURE": "TT-2024-008812"}',
    entities: {
      CLIENT: "SARL TechSolutions",
      FOURNISSEUR: "TUNISIE TELECOM",
      DATE_FACTURE: "12/04/2024",
      MONTANT_TTC: "342,00",
      NUMERO_FACTURE: "TT-2024-008812",
    },
  },
  {
    id: "6",
    filename: "facture_samsung_2024.jpg",
    type: "facture",
    date: "05/09/2024",
    client: "N/A",
    supplier: "Samsung Electronics",
    amount: 189000,
    currency: "TND",
    docNumber: "SAM-2024-776543",
    status: "processed",
    inferenceMs: 78300,
    rawText:
      '{"CLIENT": "N/A", "FOURNISSEUR": "Samsung Electronics", "DATE_FACTURE": "05/09/2024", "MONTANT_TTC": "1890,00", "NUMERO_FACTURE": "SAM-2024-776543"}',
    entities: {
      CLIENT: "N/A",
      FOURNISSEUR: "Samsung Electronics",
      DATE_FACTURE: "05/09/2024",
      MONTANT_TTC: "1890,00",
      NUMERO_FACTURE: "SAM-2024-776543",
    },
  },
];

// Stats mensuelles pour les graphiques
export const monthlyStats = [
  { month: "Oct", factures: 8, devis: 2, bons: 1, recus: 3, inferenceAvgMs: 64000, totalDocs: 14 },
  { month: "Nov", factures: 12, devis: 3, bons: 2, recus: 4, inferenceAvgMs: 67000, totalDocs: 21 },
  { month: "Déc", factures: 15, devis: 5, bons: 3, recus: 6, inferenceAvgMs: 65000, totalDocs: 29 },
  { month: "Jan", factures: 18, devis: 4, bons: 4, recus: 5, inferenceAvgMs: 63000, totalDocs: 31 },
  { month: "Fév", factures: 22, devis: 6, bons: 5, recus: 8, inferenceAvgMs: 61000, totalDocs: 41 },
  { month: "Mar", factures: 28, devis: 8, bons: 6, recus: 10, inferenceAvgMs: 59000, totalDocs: 52 },
];

// Distribution des types
export const typeDistribution = [
  { name: "Factures", value: 68, fill: "hsl(215 90% 50%)" },
  { name: "Devis", value: 15, fill: "hsl(180 55% 45%)" },
  { name: "Bons", value: 10, fill: "hsl(38 95% 50%)" },
  { name: "Reçus", value: 7, fill: "hsl(262 60% 55%)" },
];

// Métriques GLM-OCR fine-tuné
export const metricsGLM = {
  model: "Goubaa/glmocr-factures",
  baseModel: "zai-org/GLM-OCR",
  finetuning: "LoRA merged",
  gpu: "T4 (Modal)",
  avgInferenceMs: 65000,
  entitiesExtracted: 5,
  successRate: 97.4,
  f1Score: 0.974,
};
