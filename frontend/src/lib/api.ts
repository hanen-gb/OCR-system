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
  doc_type?: string;                  // "factures" | "traites" — renvoyé par le classificateur
  classification_confidence?: number; // 0–1
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

/** Crée un signal d'abandon avec timeout compatible tous navigateurs */
function makeTimeoutSignal(ms: number): { signal: AbortSignal; clear: () => void } {
  const controller = new AbortController();
  const id = setTimeout(() => controller.abort(), ms);
  return { signal: controller.signal, clear: () => clearTimeout(id) };
}

/**
 * Redimensionne une image côté client avant envoi.
 * Une photo de caméra (4000x3000, ~8MB) devient ~200KB après resize à 1024px.
 */
async function resizeImage(file: File, maxPx = 1024): Promise<File> {
  return new Promise((resolve) => {
    const img = new Image();
    const url = URL.createObjectURL(file);
    img.onload = () => {
      URL.revokeObjectURL(url);
      const scale = Math.min(1, maxPx / Math.max(img.width, img.height));
      if (scale === 1) { resolve(file); return; }           // déjà assez petit
      const canvas = document.createElement("canvas");
      canvas.width  = Math.round(img.width  * scale);
      canvas.height = Math.round(img.height * scale);
      canvas.getContext("2d")!.drawImage(img, 0, 0, canvas.width, canvas.height);
      canvas.toBlob(
        (blob) => {
          if (!blob) { resolve(file); return; }
          resolve(new File([blob], file.name.replace(/\.[^.]+$/, ".jpg"), { type: "image/jpeg" }));
        },
        "image/jpeg", 0.88,
      );
    };
    img.onerror = () => { URL.revokeObjectURL(url); resolve(file); };
    img.src = url;
  });
}

/** Vérifie si le backend répond */
export async function checkHealth(): Promise<HealthResult> {
  const { signal, clear } = makeTimeoutSignal(10_000);
  try {
    const res = await fetch(`${getApiUrl()}/health`, { signal });
    clear();
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return res.json();
  } catch (err) {
    clear();
    throw err;
  }
}

/** Envoie une image et retourne les entités extraites */
export async function predictInvoice(
  file: File,
  onProgress?: (step: number) => void,
  documentType: "auto" | "factures" | "traites" = "auto",
): Promise<PredictResult> {
  // Redimensionne avant envoi : photo caméra 8MB → ~200KB
  const resized = await resizeImage(file);

  const formData = new FormData();
  formData.append("file", resized);
  if (documentType !== "auto") {
    formData.append("document_type", documentType);
  }

  // Wake Lock : empêche l'écran mobile de s'éteindre pendant l'analyse
  let wakeLock: WakeLockSentinel | null = null;
  try {
    if ("wakeLock" in navigator) wakeLock = await navigator.wakeLock.request("screen");
  } catch { /* non supporté sur certains navigateurs */ }

  const steps = [1, 2, 3, 4];
  let stepIdx = 0;
  const progressInterval = setInterval(() => {
    if (stepIdx < steps.length) onProgress?.(steps[stepIdx++]);
  }, 8_000);

  const { signal, clear } = makeTimeoutSignal(310_000);

  try {
    const res = await fetch(`${getApiUrl()}/predict`, {
      method: "POST",
      body: formData,
      signal,
    });

    clearInterval(progressInterval);
    clear();
    wakeLock?.release();
    onProgress?.(5);

    if (!res.ok) {
      const msg = await res.text().catch(() => `HTTP ${res.status}`);
      throw new Error(msg);
    }

    return res.json();
  } catch (err) {
    clearInterval(progressInterval);
    clear();
    wakeLock?.release();
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

export const TRAITE_LABELS = [
  "NUMERO_TRAITE",
  "DATE_ECHEANCE",
  "TIREUR",
  "TIRE",
  "MONTANT",
  "RIB",
  "DOMICILIATION",
] as const;
export type TraiteLabel = (typeof TRAITE_LABELS)[number];

// ── Agent Extracteur — Analyse Contextuelle et Complémentaire ─────────────────

/** URL du serveur local de l'agent (lancé via uvicorn) */
export const AGENT_API_URL =
  import.meta.env.VITE_AGENT_URL || "http://localhost:8002";

// ── Gestion du token JWT (émis par POST /token de FastAPI) ───────────────────

const TOKEN_KEY = "odsinet_agent_token";

export function getAgentToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

function setAgentToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token);
}

export function clearAgentToken(): void {
  localStorage.removeItem(TOKEN_KEY);
}

/**
 * Appelle POST /token sur FastAPI et stocke le JWT dans localStorage.
 * À appeler une fois après un login réussi.
 * Silencieux si le serveur agent est hors ligne.
 */
export async function fetchToken(username: string, role: string): Promise<boolean> {
  try {
    const res = await fetch(`${AGENT_API_URL}/token`, {
      method : "POST",
      headers: { "Content-Type": "application/json" },
      body   : JSON.stringify({ username, role }),
      signal : AbortSignal.timeout(5_000),
    });
    if (!res.ok) return false;
    const data = await res.json();
    if (data.access_token) { setAgentToken(data.access_token); return true; }
    return false;
  } catch {
    return false;
  }
}

/**
 * Supprime un document de la base SQLite (annule un doublon).
 * Lève une erreur si le token est absent ou si le rôle n'est pas admin.
 */
export async function deleteDocument(docType: string, docNumber: string): Promise<boolean> {
  const token = getAgentToken();
  if (!token) throw new Error("Token JWT absent — veuillez vous reconnecter");
  const res = await fetch(`${AGENT_API_URL}/documents/${docType}/${docNumber}`, {
    method : "DELETE",
    headers: { Authorization: `Bearer ${token}` },
  });
  if (res.status === 403) throw new Error("Accès refusé — rôle admin requis");
  if (res.status === 401) throw new Error("Token expiré — veuillez vous reconnecter");
  return res.ok;
}

export interface AuditReport {
  status_validite: string;
  doc_type?: string;
  doc_number?: string;
  fournisseur?: string;
  // Traite-specific
  check_montant_traite?: {
    status: string;
    valeur_lettres?: number;
    valeur_chiffres?: number;
    ecart?: number;
    detail?: string;
  };
  check_echeance?: {
    status: string;
    date?: string;
    jours_restants?: number;
    jours_depassement?: number;
    detail?: string;
  };
  check_rib?: {
    status: string;
    rib?: string;
    nb_chiffres?: number;
    detail?: string;
  };
  // Facture-specific
  nb_articles?: number;
  nb_erreurs_calcul?: number;
  nb_lignes_incompletes?: number;
  check_arithmetique_lignes?: Array<{
    status: string;
    qte?: number;
    pu_ht?: number;
    total_ht_extrait?: number;
    total_ht_calcule?: number;
    ecart?: number;
  }>;
  validation_tva_globale?: {
    tva_extraite?: number;
    tva_calculee?: number;
    ecart?: number;
    status: string;
  };
  conformite_net_a_payer?: {
    montant_ht?: number;
    montant_tva?: number;
    timbre_fiscal?: number;
    net_calcule?: number;
    net_extrait?: number;
    ecart?: number;
    status: string;
  };
  gouvernance?: {
    status: string;
    champs_manquants?: string[];
    champs_presents?: string[];
  };
  alerte_doublon?: {
    status: string;
    doc_type?: string;
    doc_number?: string;
  };
}

export interface AnalystReport {
  alert_level: "NORMAL" | "ATTENTION" | "ALERTE" | string;
  nb_anomalies: number;
  anomalies: Array<{
    type: string;
    niveau: "ATTENTION" | "ALERTE";
    message: string;
    montant_actuel?: number;
    montant_moyen?: number;
    ecart_pct?: number;
  }>;
  stats_fournisseur?: {
    nb_documents: number;
    montant_moyen?: number | null;
    montant_total?: number | null;
  };
  stats_globales?: {
    nb_documents_total: number;
    nb_fournisseurs: number;
    montant_moyen_global?: number | null;
  };
  insights?: string | null;
}

export interface AgentAnalysisResult {
  /** Toutes les entités extraites par l'agent LangGraph */
  analyse_contextuelle: Record<string, unknown>;
  /** Rapport d'audit Agent 2 */
  audit?: AuditReport;
  /** Rapport d'analyse comportementale Agent 3 */
  analyse?: AnalystReport;
  /** Type de fichier détecté : "image" | "pdf_native" | "pdf_scanned" */
  file_type?: string;
  status: "ok" | "error";
  error?: string | null;
}

// ── Agent Chatbot (Agent 4) ───────────────────────────────────────────────────

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

export interface ChatResponse {
  response: string;
  status: "ok" | "error";
  error?: string;
}

export async function sendChatMessage(
  message: string,
  history: ChatMessage[],
  context?: {
    entities?: Record<string, unknown>;
    audit?: AuditReport;
    analyst?: AnalystReport;
  },
): Promise<ChatResponse> {
  const { signal, clear } = makeTimeoutSignal(60_000);
  try {
    const res = await fetch(`${AGENT_API_URL}/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        message,
        history,
        context_entities : context?.entities  ?? {},
        context_audit    : context?.audit     ?? {},
        context_analyst  : context?.analyst   ?? {},
      }),
      signal,
    });
    clear();
    if (!res.ok) {
      const body = await res.json().catch(() => ({ status: "error", error: `HTTP ${res.status}` }));
      return { response: "", status: "error", ...body } as ChatResponse;
    }
    return res.json();
  } catch (err) {
    clear();
    throw err;
  }
}

/**
 * Envoie un document à l'agent extracteur local (port 8002).
 * Tourne en PARALLÈLE avec predictInvoice — ne bloque pas le flux principal.
 * Retourne null si l'agent n'est pas disponible (échoue silencieusement).
 */
export async function analyseDocument(
  file: File,
  documentType = "auto",
  baseEntities?: Record<string, string>,
): Promise<AgentAnalysisResult> {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("document_type", documentType);
  if (baseEntities && Object.keys(baseEntities).length > 0) {
    formData.append("base_entities", JSON.stringify(baseEntities));
  }

  const { signal, clear } = makeTimeoutSignal(180_000); // 3 min max

  const agentHeaders: HeadersInit = {};
  const token = getAgentToken();
  if (token) agentHeaders["Authorization"] = `Bearer ${token}`;

  try {
    const res = await fetch(`${AGENT_API_URL}/analyse`, {
      method : "POST",
      body   : formData,
      headers: agentHeaders,
      signal,
    });
    clear();
    // 500 = serveur tourne mais erreur interne → retourne l'erreur sans throw
    // Network error = serveur inaccessible → throw (catch dans UploadPage)
    if (!res.ok) {
      const body = await res.json().catch(() => ({ status: "error", error: `HTTP ${res.status}` }));
      return { analyse_contextuelle: {}, file_type: undefined, status: "error", ...body } as AgentAnalysisResult;
    }
    return res.json();
  } catch (err) {
    clear();
    throw err;
  }
}
