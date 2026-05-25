import { useState, useCallback, useEffect, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Upload, FileImage, FileText, Loader2, CheckCircle2,
  Tag, Hash, Calendar, User, DollarSign, Building2,
  X, Clock, Brain, AlertCircle, AlertTriangle, XCircle, Shield,
  Pencil, Save, RotateCcw, Database, Camera,
  Sparkles, Copy, ChevronDown, ChevronUp, ServerOff,
  TrendingUp,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { predictInvoice, analyseDocument, AGENT_API_URL, TARGET_LABELS, type PredictResult, type AgentAnalysisResult } from "@/lib/api";
import { useChatbot } from "@/contexts/ChatbotContext";
import { getSession, getHistoryKey } from "@/lib/auth";
import { useApp } from "@/contexts/AppContext";

const ENTITY_ICONS: Record<string, React.ElementType> = {
  NUMERO_FACTURE: Hash,
  DATE_FACTURE:   Calendar,
  CLIENT:         User,
  FOURNISSEUR:    Building2,
  MONTANT_TTC:    DollarSign,
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

// ── Composant entité éditable ───────────────────────────────────────────────
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
      {/* Icône */}
      <div
        className="p-1.5 rounded-md shrink-0"
        style={{ background: isModified ? "hsl(38 90% 52% / 0.15)" : "hsl(var(--primary) / 0.1)" }}
      >
        <Icon className="w-3.5 h-3.5" style={{ color: isModified ? "hsl(38 90% 52%)" : "hsl(var(--primary))" }} />
      </div>

      {/* Label + valeur */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-1.5 mb-0.5">
          <p className="text-[10px] font-mono text-muted-foreground">{label}</p>
          {isModified && (
            <span className="text-[9px] font-semibold px-1.5 py-0.5 rounded-full"
              style={{ background: "hsl(38 90% 52% / 0.15)", color: "hsl(38 90% 52%)" }}>
              corrigé
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
            {value && value !== "N/A" ? value : "Non détecté"}
          </p>
        )}

        {/* Valeur originale si modifiée */}
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
            title="Rétablir valeur originale"
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

// ── Composant entité lecture seule (affichage GLM brut) ─────────────────────
function EntityReadOnlyRow({ label, value }: { label: string; value: string }) {
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
          {found ? value : "Non détecté"}
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
} | null;

function AuditCheckCard({ title, data }: { title: string; data: AuditCheckData }) {
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
        {isOk ? (data.status === "NOUVEAU" ? "Nouveau" : "✓ OK") : data.status.replace(/_/g, " ")}
      </p>
      {data.detail && <p className="text-[10px] text-muted-foreground mt-0.5 truncate">{data.detail}</p>}
      {typeof data.ecart === "number" && Math.abs(data.ecart) > 0.001 && (
        <p className="text-[10px] text-muted-foreground mt-0.5">écart : {data.ecart.toFixed(3)}</p>
      )}
      {data.champs_manquants && data.champs_manquants.length > 0 && (
        <p className="text-[10px] text-muted-foreground mt-0.5 truncate">{data.champs_manquants.join(", ")}</p>
      )}
    </div>
  );
}

// ── Badge niveau alerte analyste ────────────────────────────────────────────
function AnalystAlertBadge({ level }: { level: string }) {
  const cfg: Record<string, { bg: string; text: string; icon: React.ElementType; label: string }> = {
    NORMAL:    { bg: "hsl(152 60% 40% / 0.1)", text: "hsl(152 60% 40%)", icon: CheckCircle2,  label: "Normal"   },
    ATTENTION: { bg: "hsl(38 90% 52% / 0.1)",  text: "hsl(38 90% 52%)",  icon: AlertTriangle, label: "Attention" },
    ALERTE:    { bg: "hsl(0 72% 50% / 0.1)",   text: "hsl(0 72% 50%)",   icon: XCircle,       label: "Alerte"   },
  };
  const c = cfg[level] ?? cfg.NORMAL;
  const Icon = c.icon;
  return (
    <span className="flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold"
      style={{ background: c.bg, color: c.text, border: `1px solid ${c.text}40` }}>
      <Icon className="w-3 h-3" /> {c.label}
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

  // Human-in-the-loop : valeurs éditables + originales
  const [editedMap, setEditedMap]       = useState<Record<string, string>>({});
  const [originalMap, setOriginalMap]   = useState<Record<string, string>>({});
  const [savedCorrections, setSavedCorrections] = useState(false);
  const [dbStatus, setDbStatus]               = useState<"idle"|"saving"|"ok"|"error">("idle");

  // Agent Extracteur — Analyse Contextuelle et Complémentaire
  const [agentResult, setAgentResult]   = useState<AgentAnalysisResult | null>(null);
  const [agentLoading, setAgentLoading] = useState(false);
  const [agentError, setAgentError]     = useState<string | null>(null);
  const [agentExpanded, setAgentExpanded] = useState(true);
  const [agentCopied, setAgentCopied]   = useState(false);

  // Statut du serveur agent (ping /health au chargement de la page)
  const [agentStatus, setAgentStatus]   = useState<"checking" | "online" | "offline">("checking");

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

  // Ping automatique au chargement de la page
  useEffect(() => { checkAgentHealth(); }, [checkAgentHealth]);

  // Mise à jour du contexte chatbot global quand l'analyse est disponible
  useEffect(() => {
    if (agentResult?.status === "ok") {
      setDocContext({
        entities : agentResult.analyse_contextuelle,
        audit    : agentResult.audit,
        analyst  : agentResult.analyse,
      });
    }
  }, [agentResult, setDocContext]);

  const LOCAL_API = "http://localhost:8001";

  useEffect(() => {
    return () => { if (imageUrl) URL.revokeObjectURL(imageUrl); };
  }, [imageUrl]);

  const handleFile = useCallback(async (f: File) => {
    const allowed = ["image/jpeg", "image/jpg", "image/png", "image/bmp", "image/tiff"];
    if (!allowed.includes(f.type)) { setError("Format non supporté — JPG, PNG, BMP, TIFF"); return; }
    if (f.size > 20 * 1024 * 1024) { setError(t("upload_max")); return; }

    const url = URL.createObjectURL(f);
    setImageUrl(url);
    setError(null); setFile(f);
    setStep(1); setProcessing(true); setPipelineStep(0);
    setSavedCorrections(false);

    // Réinitialise l'état de l'agent pour ce nouveau document
    setAgentResult(null);
    setAgentError(null);
    setAgentLoading(true);
    setAgentExpanded(true);

    // ── Lance l'agent en PARALLÈLE (sans attendre le GLM) ────────────────────
    analyseDocument(f)
      .then((res) => {
        setAgentResult(res);
        setAgentStatus("online"); // serveur répond = il est en ligne
      })
      .catch(() => {
        // Seulement ici si le serveur est vraiment inaccessible (erreur réseau)
        setAgentError(t("agent_unavailable"));
        setAgentStatus("offline");
      })
      .finally(() => setAgentLoading(false));

    const t0 = Date.now();
    try {
      const res = await predictInvoice(f, (s) => setPipelineStep(s));
      const ms = Date.now() - t0;
      setElapsedMs(ms);
      setResult(res);

      // Afficher le résultat de classification sur le step 2
      if (res.doc_type) {
        const label = res.doc_type === "factures" ? t("classify_facture") : t("classify_traite");
        setClassificationLabel(label);
      }

      // Initialiser les maps pour l'édition
      const map: Record<string, string> = {};
      for (const e of res.entities) map[e.label] = e.text;
      for (const lbl of TARGET_LABELS) if (!map[lbl]) map[lbl] = "";
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
      // Backend GLM indisponible — on avance quand même à l'étape 2
      // pour afficher les résultats de l'agent (qui tourne en parallèle)
      const ms = Date.now() - t0;
      setElapsedMs(ms);
      setError(`Backend GLM hors ligne — résultats agent uniquement`);
      const stubResult: PredictResult = {
        entities: [],
        full_text: `(Backend GLM indisponible : ${err instanceof Error ? err.message : String(err)})`,
        timing: { inference_ms: 0, total_ms: ms },
      };
      setResult(stubResult);
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
    setClassificationLabel(null);
    setAgentResult(null); setAgentLoading(false); setAgentError(null);
    setAgentCopied(false);
    setDocContext({});
  };

  const handleEntityChange = (label: string, value: string) => {
    setEditedMap((prev) => ({ ...prev, [label]: value }));
    setSavedCorrections(false);
  };

  const correctedCount = Object.keys(editedMap).filter(
    (k) => editedMap[k] !== originalMap[k]
  ).length;

  const handleSaveCorrections = () => {
    if (!result) return;
    // Reconstruire les entités avec les valeurs corrigées
    const updatedEntities = TARGET_LABELS
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

    // Construire le payload final
    const finalEntities: Record<string, string> = {};
    for (const lbl of TARGET_LABELS) {
      const v = editedMap[lbl];
      finalEntities[lbl] = v && v.trim() !== "" ? v.trim() : "N/A";
    }

    const corrections: Record<string, { original: string; corrected: string }> = {};
    for (const lbl of TARGET_LABELS) {
      if (editedMap[lbl] !== originalMap[lbl]) {
        corrections[lbl] = { original: originalMap[lbl] ?? "", corrected: editedMap[lbl] ?? "" };
      }
    }

    const payload = {
      filename:    file?.name ?? "inconnu",
      entities:    finalEntities,
      corrections: Object.keys(corrections).length > 0 ? corrections : undefined,
      full_text:   result.full_text,
      timing:      result.timing,
    };

    try {
      const res = await fetch(`${LOCAL_API}/factures`, {
        method:  "POST",
        headers: { "Content-Type": "application/json" },
        body:    JSON.stringify(payload),
      });
      if (!res.ok) throw new Error(await res.text());
      setDbStatus("ok");
      setTimeout(() => setDbStatus("idle"), 4000);
    } catch (err) {
      console.error(err);
      setDbStatus("error");
      setTimeout(() => setDbStatus("idle"), 4000);
    }
  };

  const handleExport = () => {
    // Entités finales : toutes les valeurs non vides (N/A inclus → champ traité mais non trouvé)
    const finalEntities: Record<string, string> = {};
    for (const lbl of TARGET_LABELS) {
      const v = editedMap[lbl];
      if (v && v.trim() !== "") {
        finalEntities[lbl] = v.trim();
      } else {
        // Champ non détecté → N/A explicite pour la BDD
        finalEntities[lbl] = "N/A";
      }
    }

    // Diff corrections : uniquement les champs qui ont changé
    const corrections: Record<string, { original: string; corrected: string }> = {};
    for (const lbl of TARGET_LABELS) {
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

      {/* En-tête avec titre + badge statut agent */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-xl font-bold text-foreground">{t("upload_title")}</h1>

        {/* Badge statut Agent IA — toujours visible */}
        <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg border border-border bg-card">
          {/* Indicateur coloré */}
          <div className={`w-2 h-2 rounded-full shrink-0 ${
            agentStatus === "online"   ? "bg-green-500" :
            agentStatus === "checking" ? "bg-yellow-400 animate-pulse" :
                                         "bg-red-400"
          }`} />

          {/* Icône agent */}
          <Sparkles className="w-3.5 h-3.5 shrink-0" style={{
            color: agentStatus === "online"   ? "hsl(152 60% 40%)" :
                   agentStatus === "checking" ? "hsl(38 90% 52%)"  :
                                                "hsl(var(--muted-foreground))"
          }} />

          {/* Texte statut */}
          <span className="text-xs font-medium">
            {agentStatus === "online"   && <span style={{ color: "hsl(152 60% 40%)" }}>Agent IA — actif ✓</span>}
            {agentStatus === "offline"  && <span className="text-muted-foreground">Agent IA — hors ligne</span>}
            {agentStatus === "checking" && <span className="text-muted-foreground">Agent IA — vérification…</span>}
          </span>

          {/* Bouton re-vérifier */}
          <button
            onClick={checkAgentHealth}
            title="Vérifier à nouveau"
            className="ml-1 text-[10px] text-muted-foreground hover:text-foreground transition-colors px-1.5 py-0.5 rounded hover:bg-muted"
          >
            {agentStatus === "checking" ? "…" : "↺"}
          </button>

          {/* Commande à lancer si hors ligne */}
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
              {/* Input caméra — ouvre l'appareil photo directement sur mobile */}
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

        {/* ── STEP 2 : Résultats ── */}
        {step === 2 && result && (
          <motion.div key="results" initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} className="space-y-5">

            {/* Barre succès + actions */}
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

            {/* Avertissement backend GLM hors ligne */}
            {error && (
              <div className="flex items-center gap-2 px-4 py-3 rounded-lg text-sm"
                style={{ background: "hsl(38 90% 52% / 0.08)", color: "hsl(38 90% 52%)", border: "1px solid hsl(38 90% 52% / 0.3)" }}>
                <AlertCircle className="w-4 h-4 shrink-0" />
                {error}
              </div>
            )}

            {/* Métriques rapides */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              {[
                { label: t("upload_metric_entities"), value: `${result.entities.length}/${TARGET_LABELS.length}`, color: "text-primary" },
                { label: t("upload_metric_type"),     value: classificationLabel ?? "—", color: "text-primary" },
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

            {/* Image + Entités + Texte brut */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">

              {/* Image */}
              {imageUrl && (
                <div className="glass-card rounded-lg p-5">
                  <h3 className="text-sm font-semibold text-foreground mb-3 flex items-center gap-2">
                    <FileImage className="w-4 h-4 text-primary" />
                    {t("upload_image")}
                  </h3>
                  <img src={imageUrl} alt="facture analysée"
                    className="w-full rounded-lg object-contain border border-border"
                    style={{ maxHeight: 320, background: "hsl(var(--muted))" }} />
                </div>
              )}

              {/* Entités GLM — Human in the loop */}
              <div className="glass-card rounded-lg p-5">
                <div className="flex items-center justify-between mb-3">
                  <h3 className="text-sm font-semibold text-foreground flex items-center gap-2">
                    <Tag className="w-4 h-4 text-primary" />
                    {t("upload_entities")}
                  </h3>
                  <div className="flex items-center gap-1 text-[10px] font-semibold px-2 py-0.5 rounded-full"
                    style={{ background: "hsl(var(--primary) / 0.1)", color: "hsl(var(--primary))" }}>
                    <Pencil className="w-2.5 h-2.5" />
                    Éditable
                  </div>
                </div>

                <div className="space-y-2">
                  {TARGET_LABELS.map((label) => (
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
                    <Pencil className="w-2.5 h-2.5" /> Cliquer ✏ pour éditer
                  </span>
                  <span className="flex items-center gap-1">
                    <RotateCcw className="w-2.5 h-2.5" /> Rétablir original
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
                    {(result.timing.inference_ms / 1000).toFixed(1)}s inférence
                  </span>
                  <span>{(result.timing.total_ms / 1000).toFixed(1)}s total</span>
                </div>
              </div>
            </div>
            {/* ── Analyse Contextuelle et Complémentaire (Agent LangGraph) ── */}
            <div className="glass-card rounded-lg overflow-hidden">

              {/* En-tête du bloc */}
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
                    <p className="text-[11px] text-muted-foreground">{t("agent_section_sub")}</p>
                  </div>
                  {/* Badge statut */}
                  {agentLoading && (
                    <span className="flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold"
                      style={{ background: "hsl(262 60% 55% / 0.12)", color: "hsl(262 60% 55%)" }}>
                      <Loader2 className="w-2.5 h-2.5 animate-spin" /> En cours
                    </span>
                  )}
                  {!agentLoading && agentResult?.status === "ok" && (
                    <span className="flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-success/10 text-success">
                      <CheckCircle2 className="w-2.5 h-2.5" />
                      {Object.keys(agentResult.analyse_contextuelle || {}).filter(k => agentResult.analyse_contextuelle[k] !== null).length} champs
                    </span>
                  )}
                  {!agentLoading && agentResult?.status === "error" && !agentError && (
                    <span className="flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold"
                      style={{ background: "hsl(0 72% 50% / 0.1)", color: "hsl(0 72% 50%)" }}>
                      <AlertCircle className="w-2.5 h-2.5" /> Erreur serveur
                    </span>
                  )}
                  {!agentLoading && agentError && (
                    <span className="flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold"
                      style={{ background: "hsl(0 72% 50% / 0.1)", color: "hsl(0 72% 50%)" }}>
                      <ServerOff className="w-2.5 h-2.5" /> Hors ligne
                    </span>
                  )}
                </div>
                {agentExpanded ? <ChevronUp className="w-4 h-4 text-muted-foreground" /> : <ChevronDown className="w-4 h-4 text-muted-foreground" />}
              </button>

              {/* Corps du bloc */}
              {agentExpanded && (
                <div className="px-5 pb-5 border-t border-border">

                  {/* Chargement */}
                  {agentLoading && (
                    <div className="flex items-center gap-3 py-6">
                      <Loader2 className="w-5 h-5 animate-spin shrink-0" style={{ color: "hsl(262 60% 55%)" }} />
                      <p className="text-sm text-muted-foreground">{t("agent_loading")}</p>
                    </div>
                  )}

                  {/* Erreur réseau / Agent hors ligne */}
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

                  {/* Erreur serveur (500 / extraction échouée) */}
                  {!agentLoading && !agentError && agentResult?.status === "error" && (
                    <div className="flex items-start gap-3 py-4 px-4 mt-4 rounded-lg"
                      style={{ background: "hsl(0 72% 50% / 0.06)", border: "1px solid hsl(0 72% 50% / 0.2)" }}>
                      <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" style={{ color: "hsl(0 72% 50%)" }} />
                      <div>
                        <p className="text-sm font-medium" style={{ color: "hsl(0 72% 50%)" }}>
                          Erreur lors de l'extraction — vérifier les logs du serveur
                        </p>
                        {agentResult.error && (
                          <p className="text-[11px] font-mono text-muted-foreground mt-1 break-all">{String(agentResult.error)}</p>
                        )}
                      </div>
                    </div>
                  )}

                  {/* Résultat — uniquement si status ok */}
                  {!agentLoading && agentResult?.status === "ok" && (
                    <div className="mt-4 space-y-3">

                      {/* Type de document détecté */}
                      {agentResult.analyse_contextuelle?._document_type && (
                        <div className="flex items-center gap-2 text-xs">
                          <span className="text-muted-foreground">{t("agent_doc_type")} :</span>
                          <span className="px-2 py-0.5 rounded-full font-semibold"
                            style={{ background: "hsl(262 60% 55% / 0.12)", color: "hsl(262 60% 55%)" }}>
                            {String(agentResult.analyse_contextuelle._document_type)}
                          </span>
                        </div>
                      )}

                      {/* JSON formaté + bouton copier */}
                      <div className="relative">
                        <div className="absolute top-2 right-2 z-10">
                          <button
                            onClick={() => {
                              navigator.clipboard.writeText(
                                JSON.stringify(agentResult.analyse_contextuelle, null, 2)
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
                        </div>
                        <pre
                          className="text-xs font-mono rounded-lg p-4 pr-20 overflow-auto leading-relaxed"
                          style={{
                            background: "hsl(262 60% 55% / 0.04)",
                            border: "1px solid hsl(262 60% 55% / 0.15)",
                            maxHeight: 420,
                            color: "hsl(var(--foreground))",
                          }}
                        >
                          {JSON.stringify(agentResult.analyse_contextuelle, null, 2)}
                        </pre>
                      </div>

                      {/* File type badge */}
                      {agentResult.file_type && (
                        <p className="text-[10px] text-muted-foreground text-right">
                          fichier détecté : <span className="font-mono">{agentResult.file_type}</span>
                        </p>
                      )}
                    </div>
                  )}
                </div>
              )}
            </div>

            {/* ── Rapport d'Audit — Agent 2 ── */}
            <div className="glass-card rounded-lg overflow-hidden">
              <div className="flex items-center justify-between px-5 py-4">
                <div className="flex items-center gap-3">
                  <div className="p-1.5 rounded-lg" style={{ background: "hsl(152 60% 40% / 0.12)" }}>
                    <Shield className="w-4 h-4" style={{ color: "hsl(152 60% 40%)" }} />
                  </div>
                  <div>
                    <p className="text-sm font-semibold text-foreground">Rapport d'Audit — Agent 2</p>
                    <p className="text-[11px] text-muted-foreground">Arithmétique · TVA · Net à payer · Doublon · Gouvernance</p>
                  </div>
                  {agentLoading && (
                    <span className="flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold"
                      style={{ background: "hsl(var(--muted))", color: "hsl(var(--muted-foreground))" }}>
                      <Loader2 className="w-2.5 h-2.5 animate-spin" /> En cours
                    </span>
                  )}
                  {!agentLoading && agentResult?.audit?.status_validite && (
                    <AuditStatusBadge status={agentResult.audit.status_validite} />
                  )}
                </div>
              </div>

              {!agentLoading && agentResult?.audit && (
                <div className="px-5 pb-5 border-t border-border">
                  <div className="mt-4 grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
                    <AuditCheckCard
                      title="Arithmétique"
                      data={agentResult.audit.nb_erreurs_calcul !== undefined ? {
                        status: agentResult.audit.nb_erreurs_calcul === 0 ? "OK" : "ERREUR",
                        detail: `${agentResult.audit.nb_articles ?? 0} ligne(s), ${agentResult.audit.nb_erreurs_calcul} erreur(s)`,
                      } : null}
                    />
                    <AuditCheckCard
                      title="TVA"
                      data={agentResult.audit.validation_tva_globale
                        ? { status: agentResult.audit.validation_tva_globale.status, ecart: agentResult.audit.validation_tva_globale.ecart }
                        : null}
                    />
                    <AuditCheckCard
                      title="Net à payer"
                      data={agentResult.audit.conformite_net_a_payer
                        ? { status: agentResult.audit.conformite_net_a_payer.status, ecart: agentResult.audit.conformite_net_a_payer.ecart }
                        : null}
                    />
                    <AuditCheckCard
                      title="Doublon"
                      data={agentResult.audit.alerte_doublon
                        ? { status: agentResult.audit.alerte_doublon.status }
                        : null}
                    />
                    <AuditCheckCard
                      title="Gouvernance"
                      data={agentResult.audit.gouvernance
                        ? { status: agentResult.audit.gouvernance.status, champs_manquants: agentResult.audit.gouvernance.champs_manquants }
                        : null}
                    />
                  </div>
                  {(agentResult.audit.doc_number || agentResult.audit.fournisseur) && (
                    <div className="mt-3 flex flex-wrap gap-4 text-xs text-muted-foreground">
                      {agentResult.audit.doc_number  && <span>N° <span className="font-mono text-foreground">{agentResult.audit.doc_number}</span></span>}
                      {agentResult.audit.fournisseur && <span>Fournisseur : <span className="font-medium text-foreground">{agentResult.audit.fournisseur}</span></span>}
                      {agentResult.audit.doc_type    && <span>Type : <span className="font-medium text-foreground">{agentResult.audit.doc_type}</span></span>}
                    </div>
                  )}
                </div>
              )}

              {!agentLoading && !agentResult?.audit && !agentError && agentResult?.status !== "error" && (
                <div className="px-5 pb-4 border-t border-border">
                  <p className="text-xs text-muted-foreground mt-3">En attente des résultats de l'agent…</p>
                </div>
              )}
              {!agentLoading && agentResult?.status === "error" && (
                <div className="px-5 pb-4 border-t border-border">
                  <p className="text-xs mt-3" style={{ color: "hsl(0 72% 50%)" }}>
                    Audit non disponible — l'extraction a échoué.
                  </p>
                </div>
              )}
            </div>

            {/* ── Analyse Comportementale — Agent 3 ── */}
            <div className="glass-card rounded-lg overflow-hidden">
              <div className="flex items-center justify-between px-5 py-4">
                <div className="flex items-center gap-3">
                  <div className="p-1.5 rounded-lg" style={{ background: "hsl(220 60% 55% / 0.12)" }}>
                    <TrendingUp className="w-4 h-4" style={{ color: "hsl(220 60% 55%)" }} />
                  </div>
                  <div>
                    <p className="text-sm font-semibold text-foreground">Analyse Comportementale — Agent 3</p>
                    <p className="text-[11px] text-muted-foreground">Historique · Anomalies · Recommandations LLM</p>
                  </div>
                  {agentLoading && (
                    <span className="flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold"
                      style={{ background: "hsl(var(--muted))", color: "hsl(var(--muted-foreground))" }}>
                      <Loader2 className="w-2.5 h-2.5 animate-spin" /> En cours
                    </span>
                  )}
                  {!agentLoading && agentResult?.analyse?.alert_level && (
                    <AnalystAlertBadge level={agentResult.analyse.alert_level} />
                  )}
                </div>
              </div>

              {!agentLoading && agentResult?.analyse && (
                <div className="px-5 pb-5 border-t border-border">

                  {/* Insights LLM */}
                  {agentResult.analyse.insights && (
                    <div className="mt-4 p-4 rounded-lg"
                      style={{ background: "hsl(220 60% 55% / 0.05)", border: "1px solid hsl(220 60% 55% / 0.15)" }}>
                      <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider mb-2">Analyse LLM</p>
                      <p className="text-sm text-foreground leading-relaxed">{agentResult.analyse.insights}</p>
                    </div>
                  )}

                  {/* Anomalies + Stats */}
                  <div className="mt-4 grid grid-cols-1 sm:grid-cols-2 gap-4">

                    {/* Anomalies */}
                    <div>
                      <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider mb-2">
                        Anomalies ({agentResult.analyse.nb_anomalies ?? 0})
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
                          Aucune anomalie détectée
                        </div>
                      )}
                    </div>

                    {/* Stats */}
                    <div>
                      <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider mb-2">
                        Statistiques
                      </p>
                      <div className="space-y-2">
                        {agentResult.analyse.stats_fournisseur && (
                          <div className="p-3 rounded-lg" style={{ background: "hsl(var(--muted) / 0.4)", border: "1px solid hsl(var(--border))" }}>
                            <p className="text-[10px] font-semibold text-muted-foreground mb-1.5">Fournisseur</p>
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
                            <p className="text-[10px] font-semibold text-muted-foreground mb-1.5">Base globale</p>
                            <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs">
                              <span className="font-medium">{agentResult.analyse.stats_globales.nb_documents_total} document(s)</span>
                              <span className="text-muted-foreground">{agentResult.analyse.stats_globales.nb_fournisseurs} fournisseur(s)</span>
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
                  <p className="text-xs text-muted-foreground mt-3">En attente des résultats de l'agent…</p>
                </div>
              )}
              {!agentLoading && agentResult?.status === "error" && (
                <div className="px-5 pb-4 border-t border-border">
                  <p className="text-xs mt-3" style={{ color: "hsl(0 72% 50%)" }}>
                    Analyse non disponible — l'extraction a échoué.
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
                  ? "Corrections enregistrées ✓"
                  : correctedCount > 0
                  ? `Valider ${correctedCount} correction${correctedCount > 1 ? "s" : ""}`
                  : "Aucune correction"}
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
                {dbStatus === "saving" ? "Enregistrement…"
                : dbStatus === "ok"    ? "Enregistré en BDD ✓"
                : dbStatus === "error" ? "Erreur — API locale hors ligne"
                : "Enregistrer en BDD"}
              </Button>

              <Button variant="outline" size="sm" onClick={handleExport}>
                {t("upload_export")}
              </Button>
            </div>

          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
};

export default UploadPage;
