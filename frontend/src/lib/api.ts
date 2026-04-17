/**
 * api.ts — Client pour le backend GLM-OCR déployé sur Modal
 * Backend : https://<workspace>--glmocr-backend-fastapi-app.modal.run
 */

export const DEFAULT_API_URL =
  import.meta.env.VITE_API_URL ||
  "https://<workspace>--glmocr-backend-fastapi-app.modal.run";

export interface Entity {
  label: string;
  text: string;
  box: null;
  words: unknown[];
}

export interface PredictResult {
  entities: Entity[];
  full_text: string;
  timing: { inference_ms: number; total_ms: number };
}

export interface HealthResult {
  status: string;
  model: string;
  gpu: string;
}

/** Retourne l'URL de l'API stockée dans localStorage (ou la valeur par défaut) */
export function getApiUrl(): string {
  return localStorage.getItem("glmocr_api_url") || DEFAULT_API_URL;
}

/** Sauvegarde une URL personnalisée */
export function setApiUrl(url: string): void {
  localStorage.setItem("glmocr_api_url", url);
}

/** Vérifie si le backend répond */
export async function checkHealth(): Promise<HealthResult> {
  const res = await fetch(`${getApiUrl()}/health`, { signal: AbortSignal.timeout(10_000) });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

/** Envoie une image et retourne les entités extraites */
export async function predictInvoice(
  file: File,
  onProgress?: (step: number) => void,
): Promise<PredictResult> {
  const formData = new FormData();
  formData.append("file", file);

  // Simulation des étapes de progression côté client (le backend ne streame pas)
  const steps = [1, 2, 3, 4];
  let stepIdx = 0;
  const progressInterval = setInterval(() => {
    if (stepIdx < steps.length) {
      onProgress?.(steps[stepIdx++]);
    }
  }, 8_000); // ~8s par étape — inference totale ~65s

  try {
    const res = await fetch(`${getApiUrl()}/predict`, {
      method: "POST",
      body: formData,
      signal: AbortSignal.timeout(310_000), // 5 min + marge
    });

    clearInterval(progressInterval);
    onProgress?.(5);

    if (!res.ok) {
      const msg = await res.text().catch(() => `HTTP ${res.status}`);
      throw new Error(msg);
    }

    return res.json();
  } catch (err) {
    clearInterval(progressInterval);
    throw err;
  }
}

export const TARGET_LABELS = [
  "FOURNISSEUR",
  "CLIENT",
  "NUMERO_FACTURE",
  "DATE_FACTURE",
  "MONTANT_TTC",
] as const;

export type TargetLabel = (typeof TARGET_LABELS)[number];
