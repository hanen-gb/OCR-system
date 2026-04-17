import { useState, useCallback, useEffect, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Upload, FileImage, FileText, Loader2, CheckCircle2,
  Tag, Hash, Calendar, User, DollarSign, Building2,
  X, Clock, Brain, AlertCircle, Pencil, Save, RotateCcw, Database,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { predictInvoice, TARGET_LABELS, type PredictResult } from "@/lib/api";
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
  label, icon: Icon, done, active,
}: { label: string; icon: React.ElementType; done: boolean; active: boolean }) => (
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

// ── Page principale ─────────────────────────────────────────────────────────
const UploadPage = () => {
  const { t } = useApp();
  const pipelineSteps = usePipelineSteps(t);

  const [file, setFile]                 = useState<File | null>(null);
  const [imageUrl, setImageUrl]         = useState<string | null>(null);
  const [dragActive, setDragActive]     = useState(false);
  const [processing, setProcessing]     = useState(false);
  const [result, setResult]             = useState<PredictResult | null>(null);
  const [step, setStep]                 = useState(0);
  const [pipelineStep, setPipelineStep] = useState(-1);
  const [error, setError]               = useState<string | null>(null);
  const [elapsedMs, setElapsedMs]       = useState(0);
  const [historyId, setHistoryId]       = useState<string>("");

  // Human-in-the-loop : valeurs éditables + originales
  const [editedMap, setEditedMap]       = useState<Record<string, string>>({});
  const [originalMap, setOriginalMap]   = useState<Record<string, string>>({});
  const [savedCorrections, setSavedCorrections] = useState(false);
  const [dbStatus, setDbStatus]               = useState<"idle"|"saving"|"ok"|"error">("idle");

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

    const t0 = Date.now();
    try {
      const res = await predictInvoice(f, (s) => setPipelineStep(s));
      const ms = Date.now() - t0;
      setElapsedMs(ms);
      setResult(res);

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
      setError(`Erreur backend : ${err instanceof Error ? err.message : String(err)}`);
      setStep(0);
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
      <h1 className="text-xl font-bold text-foreground">{t("upload_title")}</h1>

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
              <div className="p-4 rounded-2xl bg-primary/10 mb-4">
                <Upload className="w-8 h-8 text-primary" />
              </div>
              <p className="text-foreground font-semibold text-lg text-center">{t("upload_drop")}</p>
              <p className="text-sm text-muted-foreground mt-1">{t("upload_click")}</p>
              <p className="text-xs text-muted-foreground mt-3 opacity-60">{t("upload_max")}</p>
            </div>

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
                      done={pipelineStep > i} active={pipelineStep === i} />
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

            {/* Métriques rapides */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              {[
                { label: "Entités détectées", value: `${result.entities.length}/${TARGET_LABELS.length}`, color: "text-primary" },
                { label: "Corrections",       value: correctedCount > 0 ? `${correctedCount}` : "—",
                  color: correctedCount > 0 ? "text-warning" : "text-muted-foreground" },
                { label: "GPU",               value: "T4",   color: "text-success" },
                { label: "Durée",             value: `${(elapsedMs / 1000).toFixed(1)}s`,
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

              {/* Entités — Human in the loop */}
              <div className="glass-card rounded-lg p-5 flex flex-col">
                <div className="flex items-center justify-between mb-3">
                  <h3 className="text-sm font-semibold text-foreground flex items-center gap-2">
                    <Tag className="w-4 h-4 text-primary" />
                    {t("upload_entities")}
                  </h3>
                  {/* Badge indiquant le mode édition */}
                  <div className="flex items-center gap-1 text-[10px] font-semibold px-2 py-0.5 rounded-full"
                    style={{ background: "hsl(var(--primary) / 0.1)", color: "hsl(var(--primary))" }}>
                    <Pencil className="w-2.5 h-2.5" />
                    Éditable
                  </div>
                </div>

                <div className="space-y-2 flex-1">
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

                {/* Boutons en bas */}
                <div className="mt-4 space-y-2">
                  {/* Valider corrections */}
                  <Button
                    size="sm"
                    className="w-full"
                    onClick={handleSaveCorrections}
                    disabled={correctedCount === 0}
                    style={correctedCount > 0 ? {
                      background: "hsl(38 90% 52%)",
                      color: "white",
                    } : undefined}
                  >
                    <Save className="w-3.5 h-3.5 mr-1.5" />
                    {savedCorrections
                      ? "Corrections enregistrées ✓"
                      : correctedCount > 0
                      ? `Valider ${correctedCount} correction${correctedCount > 1 ? "s" : ""}`
                      : "Aucune correction"}
                  </Button>
                  {/* Enregistrer en BDD */}
                  <Button
                    size="sm"
                    className="w-full"
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

                  {/* Exporter JSON */}
                  <Button variant="outline" size="sm" className="w-full" onClick={handleExport}>
                    {t("upload_export")}
                  </Button>
                </div>

                {/* Légende */}
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
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
};

export default UploadPage;
