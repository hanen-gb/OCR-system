import { useState, useEffect } from "react";
import { motion } from "framer-motion";
import { DayPicker } from "react-day-picker";
import "react-day-picker/dist/style.css";
import { FileText, Clock, ChevronDown, ChevronUp } from "lucide-react";
import { getSession, getHistoryKey } from "@/lib/auth";
import { type PredictResult, TARGET_LABELS } from "@/lib/api";
import { useApp } from "@/contexts/AppContext";

interface HistoryEntry {
  id: string;
  filename: string;
  date: string; // ISO: "YYYY-MM-DD"
  result: PredictResult;
  inferenceMs: number;
}

/** Normalise une date vers "YYYY-MM-DD" */
function toIso(d: Date): string {
  return d.toISOString().slice(0, 10);
}

/**
 * Convertit le format stocké dans l'historique vers "YYYY-MM-DD".
 * Supporte :
 *   - "15/04/2026 14:30:00"  (toLocaleString fr-FR)
 *   - "2026-04-15T..."       (ISO)
 *   - "2026-04-15"           (ISO court)
 */
function entryDateToIso(dateStr: string): string {
  if (!dateStr) return "";
  // Format fr-FR : "DD/MM/YYYY ..."
  if (dateStr.includes("/")) {
    const [datePart] = dateStr.split(" ");
    const [dd, mm, yyyy] = datePart.split("/");
    if (dd && mm && yyyy) return `${yyyy}-${mm.padStart(2, "0")}-${dd.padStart(2, "0")}`;
  }
  // Format ISO : retourne les 10 premiers caractères
  return dateStr.slice(0, 10);
}

const CalendarPage = () => {
  const { t, lang } = useApp();
  const [history, setHistory] = useState<HistoryEntry[]>([]);
  const [selected, setSelected] = useState<Date | undefined>(new Date());
  const [expandedId, setExpandedId] = useState<string | null>(null);

  useEffect(() => {
    const session = getSession();
    const key = session ? getHistoryKey(session.username) : "odsinet_history_guest";
    const raw = localStorage.getItem(key);
    if (raw) {
      try { setHistory(JSON.parse(raw)); } catch { /* ignore */ }
    }
  }, []);

  // Dates qui ont des analyses (pour les mettre en évidence)
  const activeDates = new Set(history.map((e) => entryDateToIso(e.date)));

  // Analyses du jour sélectionné
  const selectedIso = selected ? toIso(selected) : null;
  const dayEntries = selectedIso
    ? history.filter((e) => entryDateToIso(e.date) === selectedIso)
    : [];

  // Modifier les styles du rdp pour indiquer les jours actifs
  const modifiers = {
    hasAnalysis: history
      .map((e) => {
        const iso = entryDateToIso(e.date);
        const [y, m, d] = iso.split("-").map(Number);
        return new Date(y, m - 1, d);
      })
      .filter((d) => !isNaN(d.getTime())),
  };

  const modifiersStyles = {
    hasAnalysis: {
      fontWeight: "700",
      border: "2px solid hsl(215 80% 55%)",
      borderRadius: "50%",
    },
  };

  return (
    <div className="p-6 lg:p-8 max-w-screen-lg mx-auto space-y-6">
      <motion.div initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }}>
        <h1 className="text-xl font-bold text-foreground">{t("cal_title")}</h1>
        <p className="text-sm text-muted-foreground mt-0.5">{t("cal_sub")}</p>
      </motion.div>

      <div className="grid grid-cols-1 md:grid-cols-[auto_1fr] gap-6">
        {/* Calendrier */}
        <motion.div
          initial={{ opacity: 0, y: 14 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.05 }}
          className="glass-card rounded-xl p-4 w-fit mx-auto md:mx-0"
        >
          <DayPicker
            mode="single"
            selected={selected}
            onSelect={setSelected}
            modifiers={modifiers}
            modifiersStyles={modifiersStyles}
            locale={lang === "fr" ? undefined : undefined}
          />
          <p className="text-xs text-muted-foreground text-center mt-2">
            {activeDates.size} {t("cal_analyses")} — {history.length} {t("common_docs")}
          </p>
        </motion.div>

        {/* Liste du jour */}
        <motion.div
          initial={{ opacity: 0, y: 14 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
          className="space-y-3"
        >
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-semibold text-foreground">
              {selectedIso
                ? new Date(selectedIso + "T12:00:00").toLocaleDateString(lang === "fr" ? "fr-FR" : "en-US", {
                    weekday: "long", year: "numeric", month: "long", day: "numeric",
                  })
                : t("cal_select")}
            </h2>
            {dayEntries.length > 0 && (
              <span className="text-xs font-semibold px-2 py-0.5 rounded-full bg-primary/10 text-primary">
                {dayEntries.length} {t("cal_analyses")}
              </span>
            )}
          </div>

          {!selectedIso && (
            <div className="glass-card rounded-xl p-10 text-center text-sm text-muted-foreground">
              {t("cal_select")}
            </div>
          )}

          {selectedIso && dayEntries.length === 0 && (
            <div className="glass-card rounded-xl p-10 text-center">
              <div className="p-3 rounded-2xl bg-primary/10 w-fit mx-auto mb-3">
                <FileText className="w-6 h-6 text-primary" />
              </div>
              <p className="text-sm text-muted-foreground">{t("cal_no_analysis")}</p>
            </div>
          )}

          {dayEntries.map((entry, i) => {
            const entitiesMap: Record<string, string> = {};
            for (const e of entry.result.entities) entitiesMap[e.label] = e.text;
            const isExpanded = expandedId === entry.id;

            return (
              <motion.div
                key={entry.id}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: i * 0.04 }}
                className="glass-card rounded-lg overflow-hidden"
              >
                <div className="flex items-center gap-3 px-4 py-3">
                  <div className="p-2 rounded-lg bg-primary/10 shrink-0">
                    <FileText className="w-4 h-4 text-primary" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="font-medium text-sm text-foreground truncate">{entry.filename}</p>
                    <span className="flex items-center gap-1 text-xs text-muted-foreground mt-0.5">
                      <Clock className="w-3 h-3" />
                      {(entry.inferenceMs / 1000).toFixed(1)}s
                    </span>
                  </div>
                  <button
                    onClick={() => setExpandedId(isExpanded ? null : entry.id)}
                    className="p-1 rounded-md hover:bg-accent transition-colors"
                    style={{ color: "hsl(var(--muted-foreground))" }}
                  >
                    {isExpanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                  </button>
                </div>

                {/* Entités résumé */}
                <div className="flex flex-wrap gap-1.5 px-4 pb-3">
                  {TARGET_LABELS.map((label) => {
                    const val = entitiesMap[label];
                    const found = !!val && val !== "N/A";
                    return (
                      <div
                        key={label}
                        className="px-2 py-0.5 rounded text-[10px] font-mono"
                        style={{
                          background: found ? "hsl(215 90% 50% / 0.08)" : "hsl(0 0% 50% / 0.06)",
                          color: found ? "hsl(215 90% 70%)" : "hsl(220 12% 50%)",
                        }}
                      >
                        <span className="font-semibold">{label}:</span> {found ? val : "—"}
                      </div>
                    );
                  })}
                </div>

                {isExpanded && (
                  <div className="px-4 pb-4 pt-2" style={{ borderTop: "1px solid hsl(var(--border))" }}>
                    <p className="text-xs font-semibold text-muted-foreground mb-2">{t("hist_raw")}</p>
                    <pre className="text-xs font-mono bg-muted/60 rounded-lg p-3 overflow-auto max-h-32 text-foreground whitespace-pre-wrap leading-relaxed">
                      {entry.result.full_text}
                    </pre>
                  </div>
                )}
              </motion.div>
            );
          })}
        </motion.div>
      </div>
    </div>
  );
};

export default CalendarPage;
