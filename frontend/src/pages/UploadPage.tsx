import { useState, useCallback, useEffect, useRef, useMemo } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Upload, FileImage, FileText, Loader2, CheckCircle2,
  Tag, Hash, Calendar, User, DollarSign, Building2, CreditCard, Landmark,
  X, Clock, Brain, AlertCircle, AlertTriangle, XCircle, Shield,
  Pencil, Save, RotateCcw, Database, Camera,
  Sparkles, Copy, ChevronDown, ChevronUp, ServerOff,
  TrendingUp, ZoomIn, ZoomOut, RefreshCw,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { predictInvoice, analyseDocument, reauditEntities, reanalyzeEntities, AGENT_API_URL, getAgentToken, fetchToken, TARGET_LABELS, TRAITE_LABELS, type PredictResult, type AgentAnalysisResult, type Entity } from "@/lib/api";
import { useChatbot } from "@/contexts/ChatbotContext";
import { getSession, getHistoryKey } from "@/lib/auth";
import { useApp } from "@/contexts/AppContext";

const ENTITY_ICONS: Record<string, React.ElementType> = {
  // Facture
  NUMERO_FACTURE: Hash,
  DATE_FACTURE:   Calendar,
  CLIENT:         User,
  FOURNISSEUR:    Building2,
  MONTANT_TTC:    DollarSign,
  // Bill of exchange
  NUMERO_TRAITE:  Hash,
  DATE_ECHEANCE:  Calendar,
  TIREUR:         Building2,
  TIRE:           User,
  MONTANT:        DollarSign,
  RIB:            CreditCard,
  DOMICILIATION:  Landmark,
};

const usePipelineSteps = (t: (k: string) => string) => [
  { label: t("upload_step1"), icon: Upload },
  { label: t("upload_step2"), icon: Brain },
  { label: t("upload_step3"), icon: FileImage },
  { label: t("upload_step4"), icon: Tag },
  { label: t("upload_step5"), icon: FileText },
];

const ProcessingStep = ({
  label, icon: Icon, done, active, badge,
}: { label: string; icon: React.ElementType; done: boolean; active: boolean; badge?: string }) => (
  <div className={`flex items-center gap-3 py-2 px-3 rounded-lg transition-colors
    ${done ? "bg-success/5" : active ? "bg-primary/5" : ""}`}>
    {done
      ? <CheckCircle2 className="w-4 h-4 shrink-0 text-success" />
      : active
      ? <Loader2 className="w-4 h-4 shrink-0 text-primary animate-spin" />
      : <div className="w-4 h-4 shrink-0 rounded-full border-2 border-border" />}
    <Icon className="w-3.5 h-3.5 shrink-0 text-muted-foreground" />
    <span className={`text-sm ${done ? "text-foreground" : active ? "text-primary font-medium" : "text-muted-foreground"}`}>
      {label}
    </span>
    {done && badge && (
      <span className="ml-1 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-primary/10 text-primary border border-primary/20">
        {badge}
      </span>
    )}
    {done && <span className="ml-auto text-[10px] text-success font-medium">✓</span>}
  </div>
);

interface HistoryEntry {
  id: string;
  filename: string;
  date: string;
  result: PredictResult;
  inferenceMs: number;
  corrected?: boolean;
}

// Mapping of analyse_contextuelle keys → Entity labels (upper/lower case)
const CTX_KEY_MAP: [string, string][] = [
  ["TIREUR", "TIREUR"],         ["tireur", "TIREUR"],
  ["TIRE", "TIRE"],             ["tire", "TIRE"],
  ["RIB", "RIB"],               ["rib_tire", "RIB"],        ["rib", "RIB"],
  ["DATE_ECHEANCE", "DATE_ECHEANCE"], ["date_echeance", "DATE_ECHEANCE"],
  ["MONTANT", "MONTANT"],       ["montant", "MONTANT"],
  ["NUMERO_TRAITE", "NUMERO_TRAITE"], ["numero_traite", "NUMERO_TRAITE"],
  ["DOMICILIATION", "DOMICILIATION"], ["banque_domiciliataire", "DOMICILIATION"],
  ["FOURNISSEUR", "FOURNISSEUR"],     ["fournisseur", "FOURNISSEUR"],
  ["CLIENT", "CLIENT"],               ["client", "CLIENT"],
  ["NUMERO_FACTURE", "NUMERO_FACTURE"], ["numero_facture", "NUMERO_FACTURE"],
  ["DATE_FACTURE", "DATE_FACTURE"],   ["date_facture", "DATE_FACTURE"],
  ["MONTANT_TTC", "MONTANT_TTC"],     ["montant_ttc", "MONTANT_TTC"],
];

function saveToHistory(entry: HistoryEntry) {
  const session = getSession();
  const key = session ? getHistoryKey(session.username) : "odsinet_history_guest";
  const raw = localStorage.getItem(key);
  const list: HistoryEntry[] = raw ? JSON.parse(raw) : [];
  list.unshift(entry);
  localStorage.setItem(key, JSON.stringify(list.slice(0, 200)));
}

function updateHistoryEntry(id: string, updatedResult: PredictResult) {
  const session = getSession();
  const key = session ? getHistoryKey(session.username) : "odsinet_history_guest";
  const raw = localStorage.getItem(key);
  if (!raw) return;
  const list: HistoryEntry[] = JSON.parse(raw);
  const idx = list.findIndex((e) => e.id === id);
  if (idx !== -1) {
    list[idx] = { ...list[idx], result: updatedResult, corrected: true };
    localStorage.setItem(key, JSON.stringify(list));
  }
}

// ── Editable entity component ────────────────────────────────────────────────
function EntityRow({
  label,
  original,
  value,
  onChange,
}: {
  label: string;
  original: string;
  value: string;
  onChange: (v: string) => void;
}) {
  const { t } = useApp();
  const [editing, setEditing] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const Icon = ENTITY_ICONS[label] ?? Tag;
  const found = !!original && original !== "N/A";
  const isModified = value !== original;

  useEffect(() => {
    if (editing) inputRef.current?.focus();
  }, [editing]);

  const handleBlur = () => setEditing(false);
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" || e.key === "Escape") setEditing(false);
  };

  return (
    <div
      className="flex items-center gap-3 p-3 rounded-lg transition-all"
      style={{
        background: isModified
          ? "hsl(38 90% 52% / 0.08)"
          : found
          ? "hsl(var(--muted) / 0.4)"
          : "hsl(var(--muted) / 0.2)",
        border: isModified ? "1px solid hsl(38 90% 52% / 0.3)" : "1px solid transparent",
      }}
    >
      {/* Icon */}
      <div
        className="p-1.5 rounded-md shrink-0"
        style={{ background: isModified ? "hsl(38 90% 52% / 0.15)" : "hsl(var(--primary) / 0.1)" }}
      >
        <Icon className="w-3.5 h-3.5" style={{ color: isModified ? "hsl(38 90% 52%)" : "hsl(var(--primary))" }} />
      </div>

      {/* Label + value */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-1.5 mb-0.5">
          <p className="text-[10px] font-mono text-muted-foreground">{label}</p>
          {isModified && (
            <span className="text-[9px] font-semibold px-1.5 py-0.5 rounded-full"
              style={{ background: "hsl(38 90% 52% / 0.15)", color: "hsl(38 90% 52%)" }}>
              {t("entity_corrected")}
            </span>
          )}
        </div>

        {editing ? (
          <input
            ref={inputRef}
            value={value}
            onChange={(e) => onChange(e.target.value)}
            onBlur={handleBlur}
            onKeyDown={handleKeyDown}
            className="w-full text-sm font-medium bg-transparent outline-none border-b"
            style={{ color: "hsl(var(--foreground))", borderColor: "hsl(var(--primary))" }}
          />
        ) : (
          <p className={`text-sm font-medium truncate ${
            value && value !== "N/A"
              ? isModified ? "" : "text-foreground"
              : "text-muted-foreground/50 italic"
          }`}
            style={isModified ? { color: "hsl(38 90% 52%)" } : undefined}
          >
            {value && value !== "N/A" ? value : t("upload_not_detected")}
          </p>
        )}

        {/* Original value if modified */}
        {isModified && original && original !== "N/A" && (
          <p className="text-[10px] text-muted-foreground line-through mt-0.5 truncate">{original}</p>
        )}
      </div>

      {/* Actions */}
      <div className="flex items-center gap-1 shrink-0">
        {isModified && (
          <button
            onClick={() => { onChange(original); setEditing(false); }}
            className="p-1 rounded hover:bg-muted transition-colors"
            title="Restore the original value"
            style={{ color: "hsl(var(--muted-foreground))" }}
          >
            <RotateCcw className="w-3 h-3" />
          </button>
        )}
        <button
          onClick={() => setEditing(!editing)}
          className="p-1 rounded transition-colors"
          title="Modifier"
          style={{
            color: editing ? "hsl(var(--primary))" : "hsl(var(--muted-foreground))",
            background: editing ? "hsl(var(--primary) / 0.1)" : "transparent",
          }}
        >
          <Pencil className="w-3 h-3" />
        </button>
        {!isModified && found && <CheckCircle2 className="w-3.5 h-3.5 text-success" />}
      </div>
    </div>
  );
}

// ── Read-only entity component (raw GLM output) ──────────────────────────────
function EntityReadOnlyRow({ label, value }: { label: string; value: string }) {
  const { t } = useApp();
  const Icon = ENTITY_ICONS[label] ?? Tag;
  const found = !!value && value !== "N/A" && value !== "";
  return (
    <div className="flex items-center gap-3 p-3 rounded-lg"
      style={{ background: found ? "hsl(var(--muted) / 0.4)" : "hsl(var(--muted) / 0.2)" }}>
      <div className="p-1.5 rounded-md shrink-0" style={{ background: "hsl(var(--primary) / 0.1)" }}>
        <Icon className="w-3.5 h-3.5" style={{ color: "hsl(var(--primary))" }} />
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-[10px] font-mono text-muted-foreground mb-0.5">{label}</p>
        <p className={`text-sm font-medium truncate ${found ? "text-foreground" : "text-muted-foreground/50 italic"}`}>
          {found ? value : t("upload_not_detected")}
        </p>
      </div>
      {found && <CheckCircle2 className="w-3.5 h-3.5 text-success shrink-0" />}
    </div>
  );
}

// ── Helpers d'audit ─────────────────────────────────────────────────────────

function auditStatusColor(status: string) {
  switch (status) {
    case "VALIDÉ":              return { bg: "hsl(152 60% 40% / 0.1)",  text: "hsl(152 60% 40%)",  border: "hsl(152 60% 40% / 0.3)" };
    case "DOUBLON":             return { bg: "hsl(38 90% 52% / 0.1)",   text: "hsl(38 90% 52%)",   border: "hsl(38 90% 52% / 0.3)"  };
    case "SIGNATURE_MANQUANTE": return { bg: "hsl(45 90% 52% / 0.1)",   text: "hsl(45 90% 52%)",   border: "hsl(45 90% 52% / 0.3)"  };
    default:                    return { bg: "hsl(0 72% 50% / 0.1)",    text: "hsl(0 72% 50%)",    border: "hsl(0 72% 50% / 0.3)"   };
  }
}

function AuditStatusBadge({ status }: { status: string }) {
  const c = auditStatusColor(status);
  const icon = status === "VALIDÉ"
    ? <CheckCircle2 className="w-3 h-3" />
    : status === "DOUBLON" || status === "SIGNATURE_MANQUANTE"
    ? <AlertTriangle className="w-3 h-3" />
    : <XCircle className="w-3 h-3" />;
  return (
    <span className="flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold"
      style={{ background: c.bg, color: c.text, border: `1px solid ${c.border}` }}>
      {icon} {status.replace(/_/g, " ")}
    </span>
  );
}

type AuditCheckData = {
  status: string;
  detail?: string;
  ecart?: number;
  champs_manquants?: string[];
  first_seen?: string;
} | null;

function _fmtFirstSeen(iso: string): string {
  try {
    const d = new Date(iso);
    return d.toLocaleDateString("en-GB", { day: "2-digit", month: "2-digit", year: "numeric" })
      + " at " + d.toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" });
  } catch {
    return iso.slice(0, 10);
  }
}

function AuditCheckCard({ title, data }: { title: string; data: AuditCheckData }) {
  const { t } = useApp();
  if (!data) {
    return (
      <div className="rounded-lg p-3" style={{ background: "hsl(var(--muted) / 0.3)", border: "1px solid hsl(var(--border))" }}>
        <p className="text-[10px] font-semibold text-muted-foreground mb-1">{title}</p>
        <p className="text-xs text-muted-foreground italic">—</p>
      </div>
    );
  }
  const isOk   = data.status === "OK" || data.status === "NOUVEAU";
  const isWarn = data.status === "DOUBLON" || data.status === "INCOMPLET";
  const bg     = isOk ? "hsl(152 60% 40% / 0.08)" : isWarn ? "hsl(38 90% 52% / 0.08)" : "hsl(0 72% 50% / 0.08)";
  const color  = isOk ? "hsl(152 60% 40%)"         : isWarn ? "hsl(38 90% 52%)"         : "hsl(0 72% 50%)";
  const border = isOk ? "hsl(152 60% 40% / 0.2)"   : isWarn ? "hsl(38 90% 52% / 0.2)"   : "hsl(0 72% 50% / 0.2)";
  return (
    <div className="rounded-lg p-3" style={{ background: bg, border: `1px solid ${border}` }}>
      <p className="text-[10px] font-semibold text-muted-foreground mb-1">{title}</p>
      <p className="text-xs font-bold" style={{ color }}>
        {isOk ? (data.status === "NOUVEAU" ? t("audit_status_new") : "✓ OK") : data.status.replace(/_/g, " ")}
      </p>
      {data.detail && <p className="text-[10px] text-muted-foreground mt-0.5 truncate">{data.detail}</p>}
      {typeof data.ecart === "number" && Math.abs(data.ecart) > 0.001 && (
        <p className="text-[10px] text-muted-foreground mt-0.5">difference: {data.ecart.toFixed(3)}</p>
      )}
      {data.champs_manquants && data.champs_manquants.length > 0 && (
        <p className="text-[10px] text-muted-foreground mt-0.5 truncate">{data.champs_manquants.join(", ")}</p>
      )}
      {data.status === "DOUBLON" && data.first_seen && (
        <p className="text-[10px] mt-1 font-medium" style={{ color }}>
          First stored: {_fmtFirstSeen(data.first_seen)}
        </p>
      )}
    </div>
  );
}

// ── Badge niveau alerte analyste ────────────────────────────────────────────
function AnalystAlertBadge({ level }: { level: string }) {
  const { t } = useApp();
  const cfg: Record<string, { bg: string; text: string; icon: React.ElementType; labelKey: string }> = {
    NORMAL:    { bg: "hsl(152 60% 40% / 0.1)", text: "hsl(152 60% 40%)", icon: CheckCircle2,  labelKey: "alert_normal"    },
    ATTENTION: { bg: "hsl(38 90% 52% / 0.1)",  text: "hsl(38 90% 52%)",  icon: AlertTriangle, labelKey: "alert_attention" },
    ALERTE:    { bg: "hsl(0 72% 50% / 0.1)",   text: "hsl(0 72% 50%)",   icon: XCircle,       labelKey: "alert_alerte"    },
  };
  const c = cfg[level] ?? cfg.NORMAL;
  const Icon = c.icon;
  return (
    <span className="flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold"
      style={{ background: c.bg, color: c.text, border: `1px solid ${c.text}40` }}>
      <Icon className="w-3 h-3" /> {t(c.labelKey as Parameters<typeof t>[0])}
    </span>
  );
}

// ── Page principale ─────────────────────────────────────────────────────────
const UploadPage = () => {
  const { t } = useApp();
  const { setDocContext } = useChatbot();
  const pipelineSteps = usePipelineSteps(t);

  const [file, setFile]                 = useState<File | null>(null);
  const [imageUrl, setImageUrl]               = useState<string | null>(null);
  const [dragActive, setDragActive]           = useState(false);
  const [processing, setProcessing]           = useState(false);
  const [result, setResult]                   = useState<PredictResult | null>(null);
  const [step, setStep]                       = useState(0);
  const [pipelineStep, setPipelineStep]       = useState(-1);
  const [error, setError]                     = useState<string | null>(null);
  const [elapsedMs, setElapsedMs]             = useState(0);
  const [historyId, setHistoryId]             = useState<string>("");
  const [classificationLabel, setClassificationLabel] = useState<string | null>(null);
  const [classificationConf, setClassificationConf]   = useState<number | null>(null);
  const [docTypeGlm, setDocTypeGlm]           = useState<"factures" | "traites" | null>(null);
  const [forcedDocType, setForcedDocType]     = useState<"auto" | "factures" | "traites">("auto");

  // Active labels according to the detected document type
  const activeLabels: readonly string[] = docTypeGlm === "traites" ? TRAITE_LABELS : TARGET_LABELS;

  // Human-in-the-loop: editable values + original values
  const [editedMap, setEditedMap]       = useState<Record<string, string>>({});
  const [originalMap, setOriginalMap]   = useState<Record<string, string>>({});
  const [savedCorrections, setSavedCorrections] = useState(false);
  const [dbStatus, setDbStatus]               = useState<"idle"|"saving"|"ok"|"error">("idle");
  const [dbError,  setDbError]                = useState<string | null>(null);

  // Extractor Agent — contextual and complementary analysis
  const [agentResult, setAgentResult]   = useState<AgentAnalysisResult | null>(null);
  const [agentLoading, setAgentLoading] = useState(false);
  const [agentError, setAgentError]     = useState<string | null>(null);
  const [agentExpanded, setAgentExpanded] = useState(true);
  const [agentCopied, setAgentCopied]   = useState(false);
  const [agentStarted, setAgentStarted] = useState(false);

  // Agent server status (ping /health when the page loads)
  const [agentStatus, setAgentStatus]   = useState<"checking" | "online" | "offline">("checking");

  // Manual editing of the contextual analysis (HITL) — corrections are propagated
  // to the Auditor (Agent 2) and the Analyst (Agent 3) without re-running the extraction
  const [contextualEditing, setContextualEditing]   = useState(false);
  const [contextualDraft, setContextualDraft]       = useState("");
  const [contextualOverride, setContextualOverride] = useState<Record<string, unknown> | null>(null);
  const [contextualError, setContextualError]       = useState<string | null>(null);
  const [reanalyzing, setReanalyzing]               = useState(false);

  // Merge corrections GLM into agent contextual JSON for display
  const mergedContextual = useMemo<Record<string, unknown>>(() => {
    const base = contextualOverride ?? agentResult?.analyse_contextuelle;
    if (!base) return {};
    const merged: Record<string, unknown> = { ...base };
    if (!contextualOverride) {
      for (const [k, v] of Object.entries(editedMap)) {
        if (v && v.trim()) {
          const lower = k.toLowerCase();
          merged[lower] = v.trim();
          if (lower === "montant_ttc") merged["net_a_payer"] = v.trim();
        }
      }
    }
    return merged;
  }, [agentResult, editedMap, contextualOverride]);

  const handleEditContextual = () => {
    setContextualDraft(JSON.stringify(mergedContextual, null, 2));
    setContextualError(null);
    setContextualEditing(true);
  };

  const handleCancelContextual = () => {
    setContextualEditing(false);
    setContextualError(null);
  };

  const handleSaveContextual = async () => {
    let parsed: Record<string, unknown>;
    try {
      parsed = JSON.parse(contextualDraft);
    } catch (e) {
      setContextualError("JSON invalide : " + (e instanceof Error ? e.message : String(e)));
      return;
    }
    setContextualError(null);
    setContextualOverride(parsed);
    setContextualEditing(false);

    // Propagates the correction to Agents 2 (audit) and 3 (analysis) — without
    // re-running the extraction (Agent 1), only a recomputation on the corrected JSON.
    setReanalyzing(true);
    try {
      const baseEntities: Record<string, string> = {};
      for (const [k, v] of Object.entries(editedMap)) {
        if (v && v.trim()) baseEntities[k] = v.trim();
      }
      const auditRes = await reauditEntities(parsed, baseEntities);
      const analystRes = await reanalyzeEntities(parsed, (auditRes.audit as unknown as Record<string, unknown>) ?? {});
      setAgentResult((prev) =>
        prev
          ? {
              ...prev,
              analyse_contextuelle: parsed,
              audit  : auditRes.audit ?? prev.audit,
              analyse: analystRes.analyse ?? prev.analyse,
            }
          : prev,
      );
    } catch {
      setContextualError("Re-check failed — make sure the agent backend is running.");
    } finally {
      setReanalyzing(false);
    }
  };

  // Zoom modal image
  const [imageZoomOpen,  setImageZoomOpen]  = useState(false);
  const [imageZoomLevel, setImageZoomLevel] = useState(1);
  const openImageZoom  = () => { setImageZoomLevel(1); setImageZoomOpen(true); };
  const closeImageZoom = () => setImageZoomOpen(false);

  const checkAgentHealth = useCallback(async () => {
    setAgentStatus("checking");
    try {
      const res = await fetch(`${AGENT_API_URL}/health`, {
        signal: AbortSignal.timeout(3000),
      });
      setAgentStatus(res.ok ? "online" : "offline");
    } catch {
      setAgentStatus("offline");
    }
  }, []);

  // Automatic ping when the page loads
  useEffect(() => { checkAgentHealth(); }, [checkAgentHealth]);

  // Close the image zoom with Escape
  useEffect(() => {
    if (!imageZoomOpen) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") closeImageZoom(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [imageZoomOpen]);

  // Update the global chatbot context when the analysis is available
  useEffect(() => {
    if (agentResult?.status === "ok") {
      setDocContext({
        entities : mergedContextual,
        audit    : agentResult.audit,
        analyst  : agentResult.analyse,
      });
      // If GLM failed (docTypeGlm === null), get the type from the agent
      if (docTypeGlm === null) {
        const agentDocType = agentResult.analyse_contextuelle._document_type as string;
        if (agentDocType && (agentDocType.includes("traite") || agentDocType.includes("lettre") || agentDocType.includes("change"))) {
          setDocTypeGlm("traites");
          const map: Record<string, string> = {};
          for (const lbl of TRAITE_LABELS) map[lbl] = "";
          setOriginalMap(map);
          setEditedMap(map);
        }
      }
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [agentResult, mergedContextual, setDocContext]);

  // If GLM extracted no entity, enrich the history entry with the agent data
  useEffect(() => {
    if (agentResult?.status !== "ok" || !historyId || !result) return;
    if (result.entities.length > 0) return; // GLM already has entities, nothing to do

    const ctx = (agentResult.analyse_contextuelle || {}) as Record<string, unknown>;
    const seen = new Set<string>();
    const agentEntities: Entity[] = [];
    for (const [ctxKey, label] of CTX_KEY_MAP) {
      if (seen.has(label)) continue;
      const val = ctx[ctxKey];
      if (val && typeof val === "string" && val.trim() && val !== "N/A" && val.toLowerCase() !== "null") {
        agentEntities.push({ label, text: val.trim(), box: null, words: [] });
        seen.add(label);
      }
    }
    if (agentEntities.length === 0) return;

    const docT = ctx._document_type as string | undefined;
    const detectedType: "factures" | "traites" =
      docT && (docT.includes("lettre") || docT.includes("traite") || docT.includes("change"))
        ? "traites"
        : "factures";
    updateHistoryEntry(historyId, { ...result, entities: agentEntities, doc_type: detectedType });
  }, [agentResult, historyId, result]);


  useEffect(() => {
    return () => { if (imageUrl) URL.revokeObjectURL(imageUrl); };
  }, [imageUrl]);

  const handleFile = useCallback(async (f: File) => {
    const allowed = ["image/jpeg", "image/jpg", "image/png", "image/bmp", "image/tiff"];
    if (!allowed.includes(f.type)) { setError("Unsupported format — JPG, PNG, BMP, TIFF"); return; }
    if (f.size > 20 * 1024 * 1024) { setError(t("upload_max")); return; }

    const url = URL.createObjectURL(f);
    setImageUrl(url);
    setError(null); setFile(f);
    setStep(1); setProcessing(true); setPipelineStep(0);
    setSavedCorrections(false);

    // Reset the agent state for this new document
    setAgentResult(null);
    setAgentError(null);
    setAgentLoading(false);
    setAgentStarted(false);
    setAgentExpanded(true);

    const t0 = Date.now();
    try {
      const res = await predictInvoice(f, (s) => setPipelineStep(s), forcedDocType);
      const ms = Date.now() - t0;
      setElapsedMs(ms);
      setResult(res);

      // Show the classification result on step 2
      if (res.doc_type) {
        const label = res.doc_type === "factures" ? t("classify_facture") : t("classify_traite");
        const override = forcedDocType !== "auto" ? " ✎" : "";
        setClassificationLabel(`${label}${override}`);
        setClassificationConf(res.classification_confidence ?? null);
      }

      // Detect the type and choose the matching labels
      const detectedType: "factures" | "traites" = res.doc_type === "traites" ? "traites" : "factures";
      setDocTypeGlm(detectedType);
      const currentLabels: readonly string[] = detectedType === "traites" ? TRAITE_LABELS : TARGET_LABELS;

      // Initialise the maps used for editing (labels normalised to upper case)
      const map: Record<string, string> = {};
      for (const e of res.entities) map[e.label.toUpperCase()] = e.text;
      for (const lbl of currentLabels) if (!map[lbl]) map[lbl] = "";
      setOriginalMap({ ...map });
      setEditedMap({ ...map });

      setStep(2);
      const id = `${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
      setHistoryId(id);
      saveToHistory({
        id,
        filename: f.name,
        date: new Date().toLocaleString("fr-FR"),
        result: res,
        inferenceMs: ms,
      });
    } catch (err: unknown) {
      // GLM backend unavailable — move to step 2 anyway
      // to show the agent results (running in parallel)
      const ms = Date.now() - t0;
      setElapsedMs(ms);
      setError(`GLM backend offline — agent results only`);
      const stubResult: PredictResult = {
        entities: [],
        full_text: `(Backend GLM indisponible : ${err instanceof Error ? err.message : String(err)})`,
        timing: { inference_ms: 0, total_ms: ms },
      };
      setResult(stubResult);
      setDocTypeGlm(null); // set from agentResult when available
      const map: Record<string, string> = {};
      for (const lbl of TARGET_LABELS) map[lbl] = "";
      setOriginalMap({ ...map });
      setEditedMap({ ...map });
      setStep(2);
    } finally {
      setProcessing(false);
      setPipelineStep(pipelineSteps.length);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [t]);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragActive(false);
    const dropped = e.dataTransfer.files[0];
    if (dropped) handleFile(dropped);
  }, [handleFile]);

  const reset = () => {
    if (imageUrl) URL.revokeObjectURL(imageUrl);
    setFile(null); setImageUrl(null); setResult(null);
    setStep(0); setProcessing(false);
    setPipelineStep(-1); setError(null); setElapsedMs(0);
    setEditedMap({}); setOriginalMap({}); setSavedCorrections(false);
    setClassificationLabel(null); setClassificationConf(null); setDocTypeGlm(null);
    setAgentResult(null); setAgentLoading(false); setAgentError(null);
    setAgentCopied(false); setAgentStarted(false);
    setDocContext({});
  };

  const handleEntityChange = (label: string, value: string) => {
    setEditedMap((prev) => ({ ...prev, [label]: value }));
    setSavedCorrections(false);
  };

  const correctedCount = Object.keys(editedMap).filter(
    (k) => editedMap[k] !== originalMap[k]
  ).length;

  const handleStartAgents = useCallback(() => {
    if (!file || agentStarted) return;
    setAgentStarted(true);
    setAgentLoading(true);
    setAgentError(null);
    setAgentExpanded(true);

    const docType = docTypeGlm === "traites" ? "lettre_de_change" : "facture";
    // Pass the edited entities as base_entities → the auditor receives the corrected MONTANT
    const baseEntities: Record<string, string> = {};
    for (const [k, v] of Object.entries(editedMap)) {
      if (v && v.trim()) baseEntities[k] = v.trim();
    }

    analyseDocument(file, docType, baseEntities)
      .then((res) => {
        setAgentResult(res);
        setAgentStatus("online");
      })
      .catch(() => {
        setAgentError(t("agent_unavailable"));
        setAgentStatus("offline");
        setAgentStarted(false);
      })
      .finally(() => setAgentLoading(false));
  }, [file, agentStarted, docTypeGlm, editedMap, t]);

  const handleRerunAgents = useCallback(() => {
    if (!file || agentLoading) return;
    setAgentLoading(true);
    setAgentError(null);
    setAgentExpanded(true);

    const docType = docTypeGlm === "traites" ? "lettre_de_change" : "facture";
    const baseEntities: Record<string, string> = {};
    for (const [k, v] of Object.entries(editedMap)) {
      if (v && v.trim()) baseEntities[k] = v.trim();
    }

    analyseDocument(file, docType, baseEntities)
      .then((res) => { setAgentResult(res); setAgentStatus("online"); })
      .catch(() => { setAgentError(t("agent_unavailable")); setAgentStatus("offline"); })
      .finally(() => setAgentLoading(false));
  }, [file, agentLoading, docTypeGlm, editedMap, t]);

  const handleSaveCorrections = () => {
    if (!result) return;
    const updatedEntities = activeLabels
      .filter((lbl) => editedMap[lbl] && editedMap[lbl] !== "")
      .map((lbl) => ({ label: lbl, text: editedMap[lbl] }));
    const updatedResult: PredictResult = {
      ...result,
      entities: updatedEntities,
    };
    updateHistoryEntry(historyId, updatedResult);
    setSavedCorrections(true);
    setTimeout(() => setSavedCorrections(false), 3000);
  };

  const handleSaveToDB = async () => {
    if (!result) return;
    setDbStatus("saving");

    const finalEntities: Record<string, string> = {};
    for (const lbl of activeLabels) {
      const v = editedMap[lbl];
      finalEntities[lbl] = v && v.trim() !== "" ? v.trim() : "N/A";
    }

    const payload = {
      filename:     file?.name ?? "inconnu",
      entities:     finalEntities,
      doc_type:     docTypeGlm === "traites" ? "lettre_de_change" : "facture",
      audit_report: agentResult?.audit ?? {},
    };

    try {
      // If the token is missing (agent offline at login time), request it again now
      let token = getAgentToken();
      if (!token) {
        const session = getSession();
        if (session) await fetchToken(session.username, session.role).catch(() => {});
        token = getAgentToken();
      }
      const headers: Record<string, string> = { "Content-Type": "application/json" };
      if (token) headers["Authorization"] = `Bearer ${token}`;
      const res = await fetch(`${AGENT_API_URL}/save`, {
        method:  "POST",
        headers,
        body:    JSON.stringify(payload),
        signal:  AbortSignal.timeout(10_000),
      });
      if (!res.ok) {
        const body = await res.text().catch(() => `HTTP ${res.status}`);
        throw new Error(body);
      }
      setDbStatus("ok");
      setTimeout(() => setDbStatus("idle"), 4000);
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      console.error("[Save BDD]", msg);
      setDbStatus("error");
      setDbError(msg.slice(0, 200));
      setTimeout(() => { setDbStatus("idle"); setDbError(null); }, 6000);
    }
  };

  const handleExport = () => {
    // Final entities: all non-empty values (N/A included → field processed but not found)
    const finalEntities: Record<string, string> = {};
    for (const lbl of activeLabels) {
      const v = editedMap[lbl];
      if (v && v.trim() !== "") {
        finalEntities[lbl] = v.trim();
      } else {
        finalEntities[lbl] = "N/A";
      }
    }

    // Corrections diff: only the fields that changed
    const corrections: Record<string, { original: string; corrected: string }> = {};
    for (const lbl of activeLabels) {
      if (editedMap[lbl] !== originalMap[lbl]) {
        corrections[lbl] = {
          original: originalMap[lbl] ?? "",
          corrected: editedMap[lbl] ?? "",
        };
      }
    }

    const data: Record<string, unknown> = {
      filename: file?.name,
      entities: finalEntities,
    };
    if (Object.keys(corrections).length > 0) {
      data.corrections = corrections;
    }
    data.full_text = result?.full_text;
    data.timing    = result?.timing;

    const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url; a.download = `${file?.name ?? "result"}.json`; a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="p-4 sm:p-6 lg:p-8 space-y-5 max-w-screen-xl mx-auto">

      {/* Header with title + agent status badge */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-xl font-bold text-foreground">{t("upload_title")}</h1>

        {/* Badge statut Agent IA — toujours visible */}
        <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg border border-border bg-card">
          {/* Coloured indicator */}
          <div className={`w-2 h-2 rounded-full shrink-0 ${
            agentStatus === "online"   ? "bg-green-500" :
            agentStatus === "checking" ? "bg-yellow-400 animate-pulse" :
                                         "bg-red-400"
          }`} />

          {/* Agent icon */}
          <Sparkles className="w-3.5 h-3.5 shrink-0" style={{
            color: agentStatus === "online"   ? "hsl(152 60% 40%)" :
                   agentStatus === "checking" ? "hsl(38 90% 52%)"  :
                                                "hsl(var(--muted-foreground))"
          }} />

          {/* Texte statut */}
          <span className="text-xs font-medium">
            {agentStatus === "online"   && <span style={{ color: "hsl(152 60% 40%)" }}>{t("agent_status_online")}</span>}
            {agentStatus === "offline"  && <span className="text-muted-foreground">{t("agent_status_offline")}</span>}
            {agentStatus === "checking" && <span className="text-muted-foreground">{t("agent_status_checking")}</span>}
          </span>

          {/* Re-check button */}
          <button
            onClick={checkAgentHealth}
            title="Check again"
            className="ml-1 text-[10px] text-muted-foreground hover:text-foreground transition-colors px-1.5 py-0.5 rounded hover:bg-muted"
          >
            {agentStatus === "checking" ? "…" : "↺"}
          </button>

          {/* Command to run when offline */}
          {agentStatus === "offline" && (
            <span className="text-[10px] text-muted-foreground/60 font-mono border-l border-border pl-2">
              uvicorn api.main:app --port 8002
            </span>
          )}
        </div>
      </div>

      <AnimatePresence mode="wait">

        {/* ── STEP 0 : Upload ── */}
        {step === 0 && (
          <motion.div key="upload"
            initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -16 }}>
            <div className="flex flex-wrap items-center gap-2 mb-4">
              {["JPG / JPEG", "PNG", "BMP / TIFF"].map((f) => (
                <div key={f} className="flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs border border-border bg-card">
                  <FileText className="w-3 h-3 text-primary" />
                  <span className="font-semibold text-foreground">{f}</span>
                </div>
              ))}
            </div>

            <div
              className={`upload-zone p-10 sm:p-16 flex flex-col items-center justify-center ${dragActive ? "upload-zone-active" : ""}`}
              onDragOver={(e) => { e.preventDefault(); setDragActive(true); }}
              onDragLeave={() => setDragActive(false)}
              onDrop={handleDrop}
              onClick={() => document.getElementById("file-input")?.click()}
            >
              <input id="file-input" type="file" className="hidden"
                accept=".jpg,.jpeg,.png,.bmp,.tiff,.tif"
                onChange={(e) => e.target.files?.[0] && handleFile(e.target.files[0])} />
              {/* Camera input — opens the camera directly on mobile */}
              <input id="camera-input" type="file" className="hidden"
                accept="image/*" capture="environment"
                onChange={(e) => e.target.files?.[0] && handleFile(e.target.files[0])} />
              <div className="p-4 rounded-2xl bg-primary/10 mb-4">
                <Upload className="w-8 h-8 text-primary" />
              </div>
              <p className="text-foreground font-semibold text-lg text-center">{t("upload_drop")}</p>
              <p className="text-sm text-muted-foreground mt-1">{t("upload_click")}</p>
              <p className="text-xs text-muted-foreground mt-3 opacity-60">{t("upload_max")}</p>
            </div>

            {/* Bouton appareil photo / scan */}
            <button
              type="button"
              onClick={() => document.getElementById("camera-input")?.click()}
              className="mt-3 w-full flex items-center justify-center gap-2 px-4 py-3 rounded-lg border border-dashed border-primary/40 bg-primary/5 hover:bg-primary/10 transition-colors text-sm font-medium text-primary"
            >
              <Camera className="w-4 h-4" />
              {t("upload_camera")}
            </button>

            {error && (
              <div className="flex items-center gap-2 mt-3 px-4 py-3 rounded-lg text-sm"
                style={{ background: "hsl(var(--danger-bg))", color: "hsl(var(--danger))", border: "1px solid hsl(var(--danger) / 0.3)" }}>
                <AlertCircle className="w-4 h-4 shrink-0" />{error}
              </div>
            )}

            <div className="mt-5 glass-card rounded-lg p-5">
              <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-3">
                {t("upload_pipeline")}
              </p>
              <div className="flex flex-wrap items-center gap-2">
                {pipelineSteps.map((s, i) => (
                  <div key={i} className="flex items-center gap-2">
                    <div className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-md bg-muted text-xs font-medium text-foreground">
                      <s.icon className="w-3 h-3 text-primary" />
                      {s.label.split("(")[0].trim()}
                    </div>
                    {i < pipelineSteps.length - 1 && <span className="text-muted-foreground text-xs">→</span>}
                  </div>
                ))}
              </div>
            </div>
          </motion.div>
        )}

        {/* ── STEP 1 : Traitement ── */}
        {step === 1 && (
          <motion.div key="processing"
            initial={{ opacity: 0, scale: 0.97 }} animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0 }} className="glass-card rounded-lg p-6 sm:p-8">
            <div className="flex flex-col sm:flex-row gap-6">
              {imageUrl && (
                <div className="sm:w-48 md:w-64 shrink-0">
                  <p className="text-xs font-semibold text-muted-foreground mb-2">{t("upload_image")}</p>
                  <img src={imageUrl} alt="facture"
                    className="w-full rounded-lg object-contain border border-border"
                    style={{ maxHeight: 220, background: "hsl(var(--muted))" }} />
                </div>
              )}
              <div className="flex-1">
                <div className="flex items-center gap-3 mb-6">
                  <div className="w-10 h-10 rounded-full bg-primary/10 flex items-center justify-center shrink-0">
                    <Loader2 className="w-5 h-5 text-primary animate-spin" />
                  </div>
                  <div>
                    <p className="font-semibold text-foreground">{t("upload_processing")}</p>
                    <p className="text-xs text-muted-foreground truncate max-w-xs">{file?.name}</p>
                  </div>
                </div>
                <div className="space-y-1">
                  {pipelineSteps.map((s, i) => (
                    <ProcessingStep key={i} label={s.label} icon={s.icon}
                      done={pipelineStep > i} active={pipelineStep === i}
                      badge={i === 1 ? classificationLabel ?? undefined : undefined} />
                  ))}
                </div>
                <div className="mt-4 flex items-center gap-2">
                  <div className="progress-bar flex-1">
                    <div className="progress-fill"
                      style={{ width: `${(Math.min(pipelineStep, pipelineSteps.length) / pipelineSteps.length) * 100}%` }} />
                  </div>
                  <span className="text-xs font-mono text-muted-foreground shrink-0">
                    {Math.round((Math.min(pipelineStep, pipelineSteps.length) / pipelineSteps.length) * 100)}%
                  </span>
                </div>
              </div>
            </div>
          </motion.div>
        )}

        {/* ── STEP 2: results ── */}
        {step === 2 && result && (
          <motion.div key="results" initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} className="space-y-5">

            {/* Success bar + actions */}
            <div className="flex flex-wrap items-center justify-between gap-3 glass-card rounded-lg px-5 py-3">
              <div className="flex items-center gap-3">
                <div className="p-1.5 rounded-lg bg-success/10">
                  <CheckCircle2 className="w-5 h-5 text-success" />
                </div>
                <div>
                  <p className="font-semibold text-foreground text-sm">{t("upload_success")}</p>
                  <p className="text-xs text-muted-foreground truncate max-w-xs">{file?.name}</p>
                </div>
              </div>
              <Button variant="outline" size="sm" onClick={reset}>
                <X className="w-3.5 h-3.5 mr-1.5" /> {t("upload_new")}
              </Button>
            </div>

            {/* GLM backend offline warning */}
            {error && (
              <div className="flex items-center gap-2 px-4 py-3 rounded-lg text-sm"
                style={{ background: "hsl(38 90% 52% / 0.08)", color: "hsl(38 90% 52%)", border: "1px solid hsl(38 90% 52% / 0.3)" }}>
                <AlertCircle className="w-4 h-4 shrink-0" />
                {error}
              </div>
            )}

            {/* Quick metrics */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              {[
                { label: t("upload_metric_entities"), value: `${result.entities.length}/${activeLabels.length}`, color: "text-primary" },
                {
                  label: t("upload_metric_type"),
                  value: classificationLabel
                    ? classificationConf !== null && forcedDocType === "auto"
                      ? `${classificationLabel} ${Math.round(classificationConf * 100)}%`
                      : classificationLabel
                    : "—",
                  color: classificationConf !== null && classificationConf < 0.70 && forcedDocType === "auto"
                    ? "text-warning"
                    : "text-primary",
                },
                { label: t("upload_metric_correct"),  value: correctedCount > 0 ? `${correctedCount}` : "—",
                  color: correctedCount > 0 ? "text-warning" : "text-muted-foreground" },
                { label: t("upload_metric_duration"), value: `${(elapsedMs / 1000).toFixed(1)}s`,
                  color: elapsedMs < 90000 ? "text-success" : "text-warning" },
              ].map((m) => (
                <div key={m.label} className="glass-card rounded-lg p-4">
                  <p className="text-xs text-muted-foreground mb-1">{m.label}</p>
                  <p className={`text-xl font-bold ${m.color}`}>{m.value}</p>
                </div>
              ))}
            </div>

            {/* Image + entities + raw text */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">

              {/* Image */}
              {imageUrl && (
                <div className="glass-card rounded-lg p-5">
                  <div className="flex items-center justify-between mb-3">
                    <h3 className="text-sm font-semibold text-foreground flex items-center gap-2">
                      <FileImage className="w-4 h-4 text-primary" />
                      {t("upload_image")}
                    </h3>
                    <button
                      onClick={openImageZoom}
                      title="Zoom"
                      className="p-1.5 rounded-md hover:bg-muted transition-colors"
                      style={{ color: "hsl(var(--muted-foreground))" }}
                    >
                      <ZoomIn className="w-4 h-4" />
                    </button>
                  </div>
                  <img src={imageUrl} alt="analysed document"
                    className="w-full rounded-lg object-contain border border-border cursor-zoom-in"
                    style={{ maxHeight: 320, background: "hsl(var(--muted))" }}
                    onClick={openImageZoom} />
                </div>
              )}

              {/* GLM entities — human in the loop */}
              <div className="glass-card rounded-lg p-5">
                <div className="flex items-center justify-between mb-3">
                  <h3 className="text-sm font-semibold text-foreground flex items-center gap-2">
                    <Tag className="w-4 h-4 text-primary" />
                    {t("upload_entities")}
                  </h3>
                    <div className="flex items-center gap-1.5">
                    {docTypeGlm === "traites" && (
                      <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full"
                        style={{ background: "hsl(142 70% 45% / 0.12)", color: "hsl(142 70% 35%)", border: "1px solid hsl(142 70% 45% / 0.3)" }}>
                        {t("doc_badge_traite")}
                      </span>
                    )}
                    <div className="flex items-center gap-1 text-[10px] font-semibold px-2 py-0.5 rounded-full"
                      style={{ background: "hsl(var(--primary) / 0.1)", color: "hsl(var(--primary))" }}>
                      <Pencil className="w-2.5 h-2.5" />
                      {t("entity_editable")}
                    </div>
                  </div>
                </div>

                <div className="space-y-2">
                  {activeLabels.map((label) => (
                    <EntityRow
                      key={label}
                      label={label}
                      original={originalMap[label] ?? ""}
                      value={editedMap[label] ?? ""}
                      onChange={(v) => handleEntityChange(label, v)}
                    />
                  ))}
                </div>

                <div className="mt-3 flex items-center gap-3 text-[10px] text-muted-foreground">
                  <span className="flex items-center gap-1">
                    <Pencil className="w-2.5 h-2.5" /> {t("entity_click_edit")}
                  </span>
                  <span className="flex items-center gap-1">
                    <RotateCcw className="w-2.5 h-2.5" /> {t("entity_restore")}
                  </span>
                </div>
              </div>

              {/* Texte brut */}
              <div className="glass-card rounded-lg p-5">
                <h3 className="text-sm font-semibold text-foreground mb-3 flex items-center gap-2">
                  <Brain className="w-4 h-4 text-primary" />
                  {t("upload_raw")}
                </h3>
                <pre className="text-xs font-mono bg-muted/40 rounded-lg p-4 overflow-auto max-h-72 text-foreground whitespace-pre-wrap leading-relaxed">
                  {result.full_text}
                </pre>
                <div className="flex items-center gap-4 mt-3 pt-3 border-t border-border text-xs text-muted-foreground">
                  <span className="flex items-center gap-1">
                    <Clock className="w-3 h-3" />
                    {(result.timing.inference_ms / 1000).toFixed(1)}s inference
                  </span>
                  <span>{(result.timing.total_ms / 1000).toFixed(1)}s total</span>
                </div>
              </div>
            </div>

            {/* ── Agents launch button — after the GLM correction ── */}
            {!agentStarted ? (
              <button
                onClick={handleStartAgents}
                className="w-full flex items-center justify-center gap-2.5 py-3.5 rounded-lg font-semibold text-sm transition-all hover:opacity-90 active:scale-[0.99]"
                style={{ background: "hsl(var(--primary))", color: "white" }}
              >
                <Sparkles className="w-4 h-4" />
                {t("start_agents")}
              </button>
            ) : agentLoading ? (
              <div className="flex items-center justify-center gap-2.5 py-3.5 rounded-lg text-sm font-medium"
                style={{ background: "hsl(262 60% 55% / 0.08)", color: "hsl(262 60% 55%)", border: "1px solid hsl(262 60% 55% / 0.2)" }}>
                <Loader2 className="w-4 h-4 animate-spin" /> {t("agents_running")}
              </div>
            ) : null}

            {/* ── Agent sections — visible only after launch ── */}
            {agentStarted && (
              <>
            {/* ── Contextual and complementary analysis (LangGraph agent) ── */}
            <div className="glass-card rounded-lg overflow-hidden">

              {/* Block header */}
              <button
                type="button"
                onClick={() => setAgentExpanded((v) => !v)}
                className="w-full flex items-center justify-between px-5 py-4 hover:bg-muted/30 transition-colors"
              >
                <div className="flex items-center gap-3">
                  <div className="p-1.5 rounded-lg" style={{ background: "hsl(262 60% 55% / 0.12)" }}>
                    <Sparkles className="w-4 h-4" style={{ color: "hsl(262 60% 55%)" }} />
                  </div>
                  <div className="text-left">
                    <p className="text-sm font-semibold text-foreground">{t("agent_section_title")}</p>
                    {t("agent_section_sub") && <p className="text-[11px] text-muted-foreground">{t("agent_section_sub")}</p>}
                  </div>
                  {/* Badge statut */}
                  {agentLoading && (
                    <span className="flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold"
                      style={{ background: "hsl(262 60% 55% / 0.12)", color: "hsl(262 60% 55%)" }}>
                      <Loader2 className="w-2.5 h-2.5 animate-spin" /> {t("agent_in_progress")}
                    </span>
                  )}
                  {!agentLoading && agentResult?.status === "ok" && (
                    <span className="flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-success/10 text-success">
                      <CheckCircle2 className="w-2.5 h-2.5" />
                      {Object.keys(mergedContextual).filter(k => mergedContextual[k] !== null).length} {t("agent_fields")}
                    </span>
                  )}
                  {!agentLoading && agentResult?.status === "error" && !agentError && (
                    <span className="flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold"
                      style={{ background: "hsl(0 72% 50% / 0.1)", color: "hsl(0 72% 50%)" }}>
                      <AlertCircle className="w-2.5 h-2.5" /> {t("agent_server_error")}
                    </span>
                  )}
                  {!agentLoading && agentError && (
                    <span className="flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold"
                      style={{ background: "hsl(0 72% 50% / 0.1)", color: "hsl(0 72% 50%)" }}>
                      <ServerOff className="w-2.5 h-2.5" /> {t("agent_offline_badge")}
                    </span>
                  )}
                </div>
                {agentExpanded ? <ChevronUp className="w-4 h-4 text-muted-foreground" /> : <ChevronDown className="w-4 h-4 text-muted-foreground" />}
              </button>

              {/* Block body */}
              {agentExpanded && (
                <div className="px-5 pb-5 border-t border-border">

                  {/* Loading */}
                  {agentLoading && (
                    <div className="flex items-center gap-3 py-6">
                      <Loader2 className="w-5 h-5 animate-spin shrink-0" style={{ color: "hsl(262 60% 55%)" }} />
                      <p className="text-sm text-muted-foreground">{t("agent_loading")}</p>
                    </div>
                  )}

                  {/* Network error / agent offline */}
                  {!agentLoading && agentError && (
                    <div className="flex items-center gap-3 py-4 px-4 mt-4 rounded-lg"
                      style={{ background: "hsl(0 72% 50% / 0.06)", border: "1px solid hsl(0 72% 50% / 0.2)" }}>
                      <ServerOff className="w-4 h-4 shrink-0" style={{ color: "hsl(0 72% 50%)" }} />
                      <div>
                        <p className="text-sm font-medium" style={{ color: "hsl(0 72% 50%)" }}>{agentError}</p>
                        <p className="text-[11px] text-muted-foreground mt-0.5">
                          cd assistant &nbsp;→&nbsp; uvicorn api.main:app --port 8002
                        </p>
                      </div>
                    </div>
                  )}

                  {/* Server error (500 / extraction failed) */}
                  {!agentLoading && !agentError && agentResult?.status === "error" && (
                    <div className="flex items-start gap-3 py-4 px-4 mt-4 rounded-lg"
                      style={{ background: "hsl(0 72% 50% / 0.06)", border: "1px solid hsl(0 72% 50% / 0.2)" }}>
                      <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" style={{ color: "hsl(0 72% 50%)" }} />
                      <div>
                        <p className="text-sm font-medium" style={{ color: "hsl(0 72% 50%)" }}>
                          {t("agent_extract_error")}
                        </p>
                        {agentResult.error && (
                          <p className="text-[11px] font-mono text-muted-foreground mt-1 break-all">{String(agentResult.error)}</p>
                        )}
                      </div>
                    </div>
                  )}

                  {/* Result — only when status is ok */}
                  {!agentLoading && agentResult?.status === "ok" && (
                    <div className="mt-4 space-y-3">

                      {/* Detected document type */}
                      {mergedContextual?._document_type && (
                        <div className="flex items-center gap-2 text-xs">
                          <span className="text-muted-foreground">{t("agent_doc_type")} :</span>
                          <span className="px-2 py-0.5 rounded-full font-semibold"
                            style={{ background: "hsl(262 60% 55% / 0.12)", color: "hsl(262 60% 55%)" }}>
                            {String(mergedContextual._document_type)}
                          </span>
                        </div>
                      )}

                      {/* Formatted JSON + copy / edit buttons */}
                      <div className="relative">
                        <div className="absolute top-2 right-2 z-10 flex items-center gap-1.5">
                          {!contextualEditing ? (
                            <>
                              <button
                                onClick={() => {
                                  navigator.clipboard.writeText(
                                    JSON.stringify(mergedContextual, null, 2)
                                  );
                                  setAgentCopied(true);
                                  setTimeout(() => setAgentCopied(false), 2000);
                                }}
                                className="flex items-center gap-1 px-2.5 py-1 rounded-md text-[10px] font-medium transition-colors"
                                style={{
                                  background: agentCopied ? "hsl(152 60% 40% / 0.15)" : "hsl(var(--muted))",
                                  color: agentCopied ? "hsl(152 60% 40%)" : "hsl(var(--muted-foreground))",
                                }}
                              >
                                <Copy className="w-2.5 h-2.5" />
                                {agentCopied ? t("agent_copied") : t("agent_copy")}
                              </button>
                              <button
                                onClick={handleEditContextual}
                                title={t("agent_edit_json")}
                                className="flex items-center justify-center w-6 h-6 rounded-md transition-colors"
                                style={{ background: "hsl(var(--muted))", color: "hsl(var(--muted-foreground))" }}
                              >
                                <Pencil className="w-2.5 h-2.5" />
                              </button>
                            </>
                          ) : (
                            <>
                              <button
                                onClick={handleSaveContextual}
                                disabled={reanalyzing}
                                title={t("agent_save_json")}
                                className="flex items-center gap-1 px-2.5 py-1 rounded-md text-[10px] font-medium transition-colors disabled:opacity-50"
                                style={{ background: "hsl(152 60% 40% / 0.15)", color: "hsl(152 60% 40%)" }}
                              >
                                {reanalyzing ? <Loader2 className="w-2.5 h-2.5 animate-spin" /> : <Save className="w-2.5 h-2.5" />}
                                {t("agent_save_json")}
                              </button>
                              <button
                                onClick={handleCancelContextual}
                                disabled={reanalyzing}
                                title={t("agent_cancel_json")}
                                className="flex items-center justify-center w-6 h-6 rounded-md transition-colors disabled:opacity-50"
                                style={{ background: "hsl(0 72% 50% / 0.1)", color: "hsl(0 72% 50%)" }}
                              >
                                <X className="w-2.5 h-2.5" />
                              </button>
                            </>
                          )}
                        </div>

                        {!contextualEditing ? (
                          <pre
                            className="text-xs font-mono rounded-lg p-4 pr-20 overflow-auto leading-relaxed"
                            style={{
                              background: "hsl(262 60% 55% / 0.04)",
                              border: "1px solid hsl(262 60% 55% / 0.15)",
                              maxHeight: 420,
                              color: "hsl(var(--foreground))",
                            }}
                          >
                            {JSON.stringify(mergedContextual, null, 2)}
                          </pre>
                        ) : (
                          <textarea
                            value={contextualDraft}
                            onChange={(e) => setContextualDraft(e.target.value)}
                            className="w-full text-xs font-mono rounded-lg p-4 pt-9 leading-relaxed resize-y"
                            style={{
                              background: "hsl(262 60% 55% / 0.04)",
                              border: "1px solid hsl(262 60% 55% / 0.3)",
                              minHeight: 420,
                              color: "hsl(var(--foreground))",
                            }}
                            spellCheck={false}
                          />
                        )}

                        {contextualError && (
                          <p className="text-[11px] mt-1.5" style={{ color: "hsl(0 72% 50%)" }}>
                            {contextualError}
                          </p>
                        )}
                      </div>

                      {/* File type badge */}
                      {agentResult.file_type && (
                        <p className="text-[10px] text-muted-foreground text-right">
                          {t("agent_file_type_label")} <span className="font-mono">{agentResult.file_type}</span>
                        </p>
                      )}
                    </div>
                  )}
                </div>
              )}
            </div>

            {/* ── Rapport d'Audit ── */}
            <div className="glass-card rounded-lg overflow-hidden">
              <div className="flex items-center justify-between px-5 py-4">
                <div className="flex items-center gap-3">
                  <div className="p-1.5 rounded-lg" style={{ background: "hsl(152 60% 40% / 0.12)" }}>
                    <Shield className="w-4 h-4" style={{ color: "hsl(152 60% 40%)" }} />
                  </div>
                  <div>
                    <p className="text-sm font-semibold text-foreground">{t("audit_title")}</p>
                    <p className="text-[11px] text-muted-foreground">
                      {docTypeGlm === "traites" ? t("audit_sub_traite") : t("audit_sub_facture")}
                    </p>
                  </div>
                  {agentLoading && (
                    <span className="flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold"
                      style={{ background: "hsl(var(--muted))", color: "hsl(var(--muted-foreground))" }}>
                      <Loader2 className="w-2.5 h-2.5 animate-spin" /> {t("agent_in_progress")}
                    </span>
                  )}
                  {!agentLoading && agentResult?.audit?.status_validite && (
                    <AuditStatusBadge status={agentResult.audit.status_validite} />
                  )}
                </div>
                {!agentLoading && agentResult && (
                  <button
                    onClick={handleRerunAgents}
                    title="Re-run the analysis with the current corrections"
                    className="p-1.5 rounded-md hover:bg-muted transition-colors"
                    style={{ color: "hsl(var(--muted-foreground))" }}
                  >
                    <RefreshCw className="w-3.5 h-3.5" />
                  </button>
                )}
              </div>

              {!agentLoading && agentResult?.audit && (
                <div className="px-5 pb-5 border-t border-border">
                  {/* KPIs Traite */}
                  {docTypeGlm === "traites" ? (
                    <div className="mt-4 grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
                      <AuditCheckCard
                        title={t("audit_kpi_montant_lettres")}
                        data={agentResult.audit.check_montant_traite
                          ? {
                              status: agentResult.audit.check_montant_traite.status,
                              detail: agentResult.audit.check_montant_traite.detail,
                              ecart:  agentResult.audit.check_montant_traite.ecart,
                            }
                          : null}
                      />
                      <AuditCheckCard
                        title={t("audit_kpi_echeance")}
                        data={agentResult.audit.check_echeance
                          ? {
                              status: agentResult.audit.check_echeance.status === "OK"     ? "OK"
                                    : agentResult.audit.check_echeance.status === "PROCHE"  ? "DOUBLON"
                                    : agentResult.audit.check_echeance.status === "DEPASSEE"? "ERREUR"
                                    : "INCOMPLET",
                              detail: agentResult.audit.check_echeance.detail,
                            }
                          : null}
                      />
                      <AuditCheckCard
                        title={t("audit_kpi_rib")}
                        data={agentResult.audit.check_rib
                          ? {
                              status: agentResult.audit.check_rib.status === "OK" ? "OK"
                                    : agentResult.audit.check_rib.status === "INCOMPLET" ? "INCOMPLET"
                                    : "ERREUR",
                              detail: agentResult.audit.check_rib.detail,
                            }
                          : null}
                      />
                      <AuditCheckCard
                        title={t("audit_kpi_governance")}
                        data={agentResult.audit.gouvernance
                          ? { status: agentResult.audit.gouvernance.status, champs_manquants: agentResult.audit.gouvernance.champs_manquants }
                          : null}
                      />
                      <AuditCheckCard
                        title={t("audit_kpi_doublon")}
                        data={agentResult.audit.alerte_doublon
                          ? {
                              status    : agentResult.audit.alerte_doublon.status,
                              detail    : agentResult.audit.alerte_doublon.detail,
                              first_seen: agentResult.audit.alerte_doublon.first_seen,
                            }
                          : null}
                      />
                    </div>
                  ) : (
                    /* KPIs Facture */
                    <div className="mt-4 grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
                      <AuditCheckCard
                        title={t("audit_kpi_arithmetic")}
                        data={agentResult.audit.nb_erreurs_calcul !== undefined ? {
                          status: agentResult.audit.nb_erreurs_calcul === 0 ? "OK" : "ERREUR",
                          detail: `${agentResult.audit.nb_articles ?? 0} line(s), ${agentResult.audit.nb_erreurs_calcul} error(s)`,
                        } : null}
                      />
                      <AuditCheckCard
                        title={t("audit_kpi_lettres")}
                        data={agentResult.audit.check_lettres_vs_net
                          ? { status: agentResult.audit.check_lettres_vs_net.status, ecart: agentResult.audit.check_lettres_vs_net.ecart }
                          : null}
                      />
                      <AuditCheckCard
                        title={t("audit_kpi_doublon")}
                        data={agentResult.audit.alerte_doublon
                          ? {
                              status    : agentResult.audit.alerte_doublon.status,
                              detail    : agentResult.audit.alerte_doublon.detail,
                              first_seen: agentResult.audit.alerte_doublon.first_seen,
                            }
                          : null}
                      />
                      <AuditCheckCard
                        title={t("audit_kpi_governance")}
                        data={agentResult.audit.gouvernance
                          ? { status: agentResult.audit.gouvernance.status, champs_manquants: agentResult.audit.gouvernance.champs_manquants }
                          : null}
                      />
                    </div>
                  )}
                  {agentResult.audit.document_incomplet && (
                    <div className="mt-3 flex items-center gap-2 px-3 py-2 rounded-lg text-xs font-medium"
                      style={{ background: "hsl(38 92% 50% / 0.08)", color: "hsl(38 92% 50%)", border: "1px solid hsl(38 92% 50% / 0.3)" }}>
                      <AlertCircle className="w-3.5 h-3.5 shrink-0" />
                      {t("audit_incomplete_totals")}
                    </div>
                  )}
                  {(agentResult.audit.doc_number || agentResult.audit.fournisseur) && (
                    <div className="mt-3 flex flex-wrap gap-4 text-xs text-muted-foreground">
                      {agentResult.audit.doc_number  && <span>N° <span className="font-mono text-foreground">{agentResult.audit.doc_number}</span></span>}
                      {agentResult.audit.fournisseur && (
                        <span>
                          {docTypeGlm === "traites" ? t("audit_actor_tireur") : t("audit_actor_fournisseur")} :{" "}
                          <span className="font-medium text-foreground">{agentResult.audit.fournisseur}</span>
                        </span>
                      )}
                      {agentResult.audit.doc_type    && <span>Type : <span className="font-medium text-foreground">{agentResult.audit.doc_type}</span></span>}
                    </div>
                  )}
                </div>
              )}

              {!agentLoading && !agentResult?.audit && !agentError && agentResult?.status !== "error" && (
                <div className="px-5 pb-4 border-t border-border">
                  <p className="text-xs text-muted-foreground mt-3">{t("agent_waiting")}</p>
                </div>
              )}
              {!agentLoading && agentResult?.status === "error" && (
                <div className="px-5 pb-4 border-t border-border">
                  <p className="text-xs mt-3" style={{ color: "hsl(0 72% 50%)" }}>
                    {t("audit_unavailable")}
                  </p>
                </div>
              )}
            </div>

            {/* ── Analyse Comportementale ── */}
            <div className="glass-card rounded-lg overflow-hidden">
              <div className="flex items-center justify-between px-5 py-4">
                <div className="flex items-center gap-3">
                  <div className="p-1.5 rounded-lg" style={{ background: "hsl(220 60% 55% / 0.12)" }}>
                    <TrendingUp className="w-4 h-4" style={{ color: "hsl(220 60% 55%)" }} />
                  </div>
                  <div>
                    <p className="text-sm font-semibold text-foreground">{t("analyst_title")}</p>
                    <p className="text-[11px] text-muted-foreground">
                      {docTypeGlm === "traites" ? t("analyst_sub_traite") : t("analyst_sub_facture")}
                    </p>
                  </div>
                  {agentLoading && (
                    <span className="flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold"
                      style={{ background: "hsl(var(--muted))", color: "hsl(var(--muted-foreground))" }}>
                      <Loader2 className="w-2.5 h-2.5 animate-spin" /> {t("agent_in_progress")}
                    </span>
                  )}
                  {!agentLoading && agentResult?.analyse?.alert_level && (
                    <AnalystAlertBadge level={agentResult.analyse.alert_level} />
                  )}
                </div>
                {!agentLoading && agentResult && (
                  <button
                    onClick={handleRerunAgents}
                    title="Re-run the analysis with the current corrections"
                    className="p-1.5 rounded-md hover:bg-muted transition-colors"
                    style={{ color: "hsl(var(--muted-foreground))" }}
                  >
                    <RefreshCw className="w-3.5 h-3.5" />
                  </button>
                )}
              </div>

              {!agentLoading && agentResult?.analyse && (
                <div className="px-5 pb-5 border-t border-border">

                  {/* Insights LLM */}
                  {agentResult.analyse.insights && (
                    <div className="mt-4 p-4 rounded-lg"
                      style={{ background: "hsl(220 60% 55% / 0.05)", border: "1px solid hsl(220 60% 55% / 0.15)" }}>
                      <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider mb-2">{t("analyst_llm_title")}</p>
                      <p className="text-sm text-foreground leading-relaxed">{agentResult.analyse.insights}</p>
                    </div>
                  )}

                  {/* Anomalies + Stats */}
                  <div className="mt-4 grid grid-cols-1 sm:grid-cols-2 gap-4">

                    {/* Anomalies */}
                    <div>
                      <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider mb-2">
                        {t("analyst_anomalies")} ({agentResult.analyse.nb_anomalies ?? 0})
                      </p>
                      {agentResult.analyse.anomalies && agentResult.analyse.anomalies.length > 0 ? (
                        <div className="space-y-2">
                          {agentResult.analyse.anomalies.map((a, i) => {
                            const isAlerte = a.niveau === "ALERTE";
                            const color  = isAlerte ? "hsl(0 72% 50%)"           : "hsl(38 90% 52%)";
                            const bg     = isAlerte ? "hsl(0 72% 50% / 0.08)"    : "hsl(38 90% 52% / 0.08)";
                            const border = isAlerte ? "hsl(0 72% 50% / 0.2)"     : "hsl(38 90% 52% / 0.2)";
                            const Icon   = isAlerte ? XCircle : AlertTriangle;
                            return (
                              <div key={i} className="flex items-start gap-2 p-2 rounded-lg"
                                style={{ background: bg, border: `1px solid ${border}` }}>
                                <Icon className="w-3.5 h-3.5 shrink-0 mt-0.5" style={{ color }} />
                                <div>
                                  <p className="text-[10px] font-semibold" style={{ color }}>
                                    {a.type.replace(/_/g, " ")}
                                  </p>
                                  <p className="text-[11px] text-muted-foreground mt-0.5">{a.message}</p>
                                </div>
                              </div>
                            );
                          })}
                        </div>
                      ) : (
                        <div className="flex items-center gap-2 p-2 rounded-lg text-[11px] text-muted-foreground"
                          style={{ background: "hsl(152 60% 40% / 0.05)", border: "1px solid hsl(152 60% 40% / 0.15)" }}>
                          <CheckCircle2 className="w-3 h-3 shrink-0" style={{ color: "hsl(152 60% 40%)" }} />
                          {t("analyst_no_anomaly")}
                        </div>
                      )}
                    </div>

                    {/* Stats */}
                    <div>
                      <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider mb-2">
                        {t("analyst_stats")}
                      </p>
                      <div className="space-y-2">
                        {agentResult.analyse.stats_fournisseur && (
                          <div className="p-3 rounded-lg" style={{ background: "hsl(var(--muted) / 0.4)", border: "1px solid hsl(var(--border))" }}>
                            <p className="text-[10px] font-semibold text-muted-foreground mb-1.5">
                              {docTypeGlm === "traites" ? t("audit_actor_tireur") : t("audit_actor_fournisseur")}
                            </p>
                            <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs">
                              <span className="font-medium">{agentResult.analyse.stats_fournisseur.nb_documents} doc(s)</span>
                              {agentResult.analyse.stats_fournisseur.montant_moyen != null && (
                                <span className="text-muted-foreground">moy. {agentResult.analyse.stats_fournisseur.montant_moyen.toFixed(3)} DT</span>
                              )}
                              {agentResult.analyse.stats_fournisseur.montant_total != null && (
                                <span className="text-muted-foreground">total {agentResult.analyse.stats_fournisseur.montant_total.toFixed(3)} DT</span>
                              )}
                            </div>
                          </div>
                        )}
                        {agentResult.analyse.stats_globales && (
                          <div className="p-3 rounded-lg" style={{ background: "hsl(var(--muted) / 0.4)", border: "1px solid hsl(var(--border))" }}>
                            <p className="text-[10px] font-semibold text-muted-foreground mb-1.5">{t("analyst_global_base")}</p>
                            <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs">
                              <span className="font-medium">{agentResult.analyse.stats_globales.nb_documents_total} document(s)</span>
                              <span className="text-muted-foreground">{agentResult.analyse.stats_globales.nb_fournisseurs} {t("analyst_suppliers")}</span>
                              {agentResult.analyse.stats_globales.montant_moyen_global != null && (
                                <span className="text-muted-foreground">moy. {agentResult.analyse.stats_globales.montant_moyen_global.toFixed(3)} DT</span>
                              )}
                            </div>
                          </div>
                        )}
                      </div>
                    </div>
                  </div>
                </div>
              )}

              {!agentLoading && !agentResult?.analyse && !agentError && agentResult?.status !== "error" && (
                <div className="px-5 pb-4 border-t border-border">
                  <p className="text-xs text-muted-foreground mt-3">{t("agent_waiting")}</p>
                </div>
              )}
              {!agentLoading && agentResult?.status === "error" && (
                <div className="px-5 pb-4 border-t border-border">
                  <p className="text-xs mt-3" style={{ color: "hsl(0 72% 50%)" }}>
                    {t("analyst_unavailable")}
                  </p>
                </div>
              )}
            </div>

            {/* ── Actions : corrections + stockage + export ── */}
            <div className="glass-card rounded-lg px-5 py-4 flex flex-wrap items-center gap-3">
              <Button
                size="sm"
                onClick={handleSaveCorrections}
                disabled={correctedCount === 0}
                style={correctedCount > 0 ? { background: "hsl(38 90% 52%)", color: "white" } : undefined}
              >
                <Save className="w-3.5 h-3.5 mr-1.5" />
                {savedCorrections
                  ? t("corrections_saved")
                  : correctedCount > 0
                  ? `${t("corrections_validate")} ${correctedCount} ${t("correction_word")}${correctedCount > 1 ? "s" : ""}`
                  : t("no_corrections")}
              </Button>

              <Button
                size="sm"
                onClick={handleSaveToDB}
                disabled={dbStatus === "saving"}
                style={{
                  background: dbStatus === "ok"    ? "hsl(152 60% 40%)"
                            : dbStatus === "error" ? "hsl(0 72% 50%)"
                            : "hsl(262 60% 55%)",
                  color: "white",
                }}
              >
                {dbStatus === "saving" ? (
                  <Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" />
                ) : (
                  <Database className="w-3.5 h-3.5 mr-1.5" />
                )}
                {dbStatus === "saving" ? t("db_saving")
                : dbStatus === "ok"    ? t("db_saved")
                : dbStatus === "error" ? t("db_error")
                : t("db_save")}
              </Button>

              {dbError && (
                <span className="text-xs text-red-500 max-w-xs truncate" title={dbError}>
                  ⚠ {dbError}
                </span>
              )}

              <Button variant="outline" size="sm" onClick={handleExport}>
                {t("upload_export")}
              </Button>
            </div>
            </>
            )}

          </motion.div>
        )}
      </AnimatePresence>

      {/* ── Modal zoom image ── */}
      {imageZoomOpen && imageUrl && (
        <div
          className="fixed inset-0 z-50 flex flex-col items-center justify-center"
          style={{ background: "rgba(0,0,0,0.88)" }}
          onClick={closeImageZoom}
        >
          {/* Control bar */}
          <div
            className="flex items-center gap-2 mb-3 px-4 py-2 rounded-xl select-none"
            style={{ background: "rgba(255,255,255,0.1)", backdropFilter: "blur(8px)" }}
            onClick={e => e.stopPropagation()}
          >
            <button
              onClick={() => setImageZoomLevel(l => Math.max(0.25, +(l - 0.25).toFixed(2)))}
              className="p-1.5 rounded-md text-white hover:bg-white/20 transition-colors"
              title="Minimise"
            >
              <ZoomOut className="w-4 h-4" />
            </button>
            <span className="text-white text-xs font-mono w-10 text-center">
              {Math.round(imageZoomLevel * 100)}%
            </span>
            <button
              onClick={() => setImageZoomLevel(l => Math.min(6, +(l + 0.25).toFixed(2)))}
              className="p-1.5 rounded-md text-white hover:bg-white/20 transition-colors"
              title="Agrandir"
            >
              <ZoomIn className="w-4 h-4" />
            </button>
            <button
              onClick={() => setImageZoomLevel(1)}
              className="px-2.5 py-1 rounded-md text-white text-[10px] font-semibold hover:bg-white/20 transition-colors"
              title="Ajuster"
            >
              1:1
            </button>
            <div className="w-px h-4 mx-1" style={{ background: "rgba(255,255,255,0.25)" }} />
            <button
              onClick={closeImageZoom}
              className="p-1.5 rounded-md text-white hover:bg-white/20 transition-colors"
              title="Close (Esc)"
            >
              <X className="w-4 h-4" />
            </button>
          </div>

          {/* Image scrollable */}
          <div
            className="overflow-auto rounded-lg"
            style={{ maxWidth: "92vw", maxHeight: "82vh" }}
            onClick={e => e.stopPropagation()}
          >
            <img
              src={imageUrl}
              alt="analysed document"
              style={{
                display: "block",
                width:    imageZoomLevel === 1 ? "auto" : `${imageZoomLevel * 100}%`,
                maxWidth: imageZoomLevel === 1 ? "88vw" : "none",
                maxHeight:imageZoomLevel === 1 ? "78vh" : "none",
                height:   "auto",
              }}
            />
          </div>
        </div>
      )}
    </div>
  );
};

export default UploadPage;
