import { useState, useEffect } from "react";
import { motion } from "framer-motion";
import {
  Search, Download, FileText, Trash2, Brain, Clock,
  CheckCircle2, ChevronDown, ChevronUp,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { TARGET_LABELS, type PredictResult } from "@/lib/api";
import { getSession, getHistoryKey } from "@/lib/auth";
import { useApp } from "@/contexts/AppContext";

interface HistoryEntry {
  id: string;
  filename: string;
  date: string;
  result: PredictResult;
  inferenceMs: number;
}

const DocumentsPage = () => {
  const { t } = useApp();
  const [history, setHistory] = useState<HistoryEntry[]>([]);
  const [search, setSearch] = useState("");
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const getKey = () => {
    const session = getSession();
    return session ? getHistoryKey(session.username) : "odsinet_history_guest";
  };

  useEffect(() => {
    const raw = localStorage.getItem(getKey());
    if (raw) {
      try { setHistory(JSON.parse(raw)); } catch { setHistory([]); }
    }
  }, []);

  const filtered = history.filter(
    (e) =>
      e.filename.toLowerCase().includes(search.toLowerCase()) ||
      e.result.entities.some((en) =>
        en.text.toLowerCase().includes(search.toLowerCase()),
      ),
  );

  const deleteEntry = (id: string) => {
    const updated = history.filter((e) => e.id !== id);
    setHistory(updated);
    localStorage.setItem(getKey(), JSON.stringify(updated));
  };

  const clearAll = () => {
    setHistory([]);
    localStorage.removeItem(getKey());
  };

  const exportEntry = (entry: HistoryEntry) => {
    const entitiesMap: Record<string, string> = {};
    for (const e of entry.result.entities) entitiesMap[e.label] = e.text;
    const data = {
      filename: entry.filename,
      date: entry.date,
      inferenceMs: entry.inferenceMs,
      entities: entitiesMap,
      full_text: entry.result.full_text,
    };
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url; a.download = `${entry.filename}.json`; a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="p-6 lg:p-8 space-y-5 max-w-screen-xl mx-auto">
      <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }}>
        <h1 className="text-xl font-bold text-foreground">{t("hist_title")}</h1>
        <p className="text-sm text-muted-foreground mt-0.5">
          {t("hist_sub")} · {history.length} {history.length !== 1 ? t("common_docs") : t("common_doc")}
        </p>
      </motion.div>

      {/* Barre de recherche + actions */}
      <div className="flex flex-wrap items-center gap-3">
        <div className="relative flex-1 min-w-48">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
          <input
            type="text"
            placeholder={t("hist_search")}
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="input-base pl-9"
          />
        </div>
        {history.length > 0 && (
          <Button variant="outline" size="sm" onClick={clearAll} className="text-red-500 hover:text-red-600">
            <Trash2 className="w-3.5 h-3.5 mr-1.5" /> {t("hist_clear")}
          </Button>
        )}
      </div>

      {/* Liste vide */}
      {history.length === 0 && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className="glass-card rounded-lg p-16 flex flex-col items-center justify-center text-center"
        >
          <div className="p-4 rounded-2xl bg-primary/10 mb-4">
            <FileText className="w-8 h-8 text-primary" />
          </div>
          <p className="font-semibold text-foreground">{t("hist_empty")}</p>
          <p className="text-sm text-muted-foreground mt-1">
            {t("hist_empty_sub")} <span className="text-primary font-semibold">{t("nav_upload")}</span>
          </p>
        </motion.div>
      )}

      {/* Aucun résultat pour la recherche */}
      {filtered.length === 0 && history.length > 0 && (
        <div className="text-center text-sm text-muted-foreground py-8">
          {t("hist_no_result")} "<span className="font-semibold">{search}</span>"
        </div>
      )}

      <div className="space-y-3">
        {filtered.map((entry, i) => {
          const entitiesMap: Record<string, string> = {};
          for (const e of entry.result.entities) entitiesMap[e.label] = e.text;
          const detectedCount = entry.result.entities.length;
          const isExpanded = expandedId === entry.id;

          return (
            <motion.div
              key={entry.id}
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.04 }}
              className="glass-card rounded-lg overflow-hidden"
            >
              {/* Header */}
              <div className="flex items-center gap-3 px-4 py-3.5 sm:gap-4 sm:px-5">
                <div className="p-2 rounded-lg bg-primary/10 shrink-0">
                  <Brain className="w-4 h-4 text-primary" />
                </div>

                <div className="flex-1 min-w-0">
                  <p className="font-medium text-foreground text-sm truncate">{entry.filename}</p>
                  <div className="flex items-center gap-3 mt-0.5">
                    <span className="text-xs text-muted-foreground">{entry.date}</span>
                    <span className="flex items-center gap-1 text-xs text-muted-foreground">
                      <Clock className="w-3 h-3" />
                      {(entry.inferenceMs / 1000).toFixed(1)}s
                    </span>
                  </div>
                </div>

                <div
                  className="hidden sm:flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-semibold shrink-0"
                  style={{
                    background: detectedCount >= 4 ? "hsl(var(--success-bg))" : "hsl(38 95% 50% / 0.1)",
                    color: detectedCount >= 4 ? "hsl(var(--success))" : "hsl(38 95% 40%)",
                  }}
                >
                  <CheckCircle2 className="w-3 h-3" />
                  {detectedCount}/{TARGET_LABELS.length}
                </div>

                <div className="flex items-center gap-1 shrink-0">
                  <Button variant="ghost" size="sm" onClick={() => exportEntry(entry)} title={t("hist_export")}>
                    <Download className="w-3.5 h-3.5" />
                  </Button>
                  <Button variant="ghost" size="sm" onClick={() => deleteEntry(entry.id)} title={t("hist_delete")} className="text-red-400 hover:text-red-500">
                    <Trash2 className="w-3.5 h-3.5" />
                  </Button>
                  <Button variant="ghost" size="sm" onClick={() => setExpandedId(isExpanded ? null : entry.id)}>
                    {isExpanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                  </Button>
                </div>
              </div>

              {/* Entités en ligne */}
              <div className="flex flex-wrap gap-2 px-4 pb-3 sm:px-5">
                {TARGET_LABELS.map((label) => {
                  const val = entitiesMap[label];
                  const found = !!val && val !== "N/A";
                  return (
                    <div
                      key={label}
                      className="flex items-center gap-1.5 px-2 py-1 rounded text-[10px] font-mono"
                      style={{
                        background: found ? "hsl(215 90% 50% / 0.08)" : "hsl(0 0% 50% / 0.06)",
                        color: found ? "hsl(215 90% 70%)" : "hsl(220 12% 50%)",
                      }}
                    >
                      <span className="font-semibold">{label}:</span>
                      <span>{found ? val : "—"}</span>
                    </div>
                  );
                })}
              </div>

              {/* Texte brut (expandable) */}
              {isExpanded && (
                <div className="px-4 pb-5 pt-2 sm:px-5" style={{ borderTop: "1px solid hsl(var(--border))" }}>
                  <p className="text-xs font-semibold text-muted-foreground mb-2">{t("hist_raw")}</p>
                  <pre className="text-xs font-mono bg-muted/60 rounded-lg p-4 overflow-auto max-h-40 text-foreground whitespace-pre-wrap leading-relaxed">
                    {entry.result.full_text}
                  </pre>
                </div>
              )}
            </motion.div>
          );
        })}
      </div>
    </div>
  );
};

export default DocumentsPage;
