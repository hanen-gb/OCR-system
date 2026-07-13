import { useState, useEffect, useCallback } from "react";
import { motion } from "framer-motion";
import {
  Search, Download, FileText, Trash2, Brain, Clock,
  CheckCircle2, ChevronDown, ChevronUp, Database, RefreshCw,
  AlertCircle, FileCheck, FileX,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { TARGET_LABELS, AGENT_API_URL, type PredictResult } from "@/lib/api";
import { getSession, getHistoryKey } from "@/lib/auth";
import { useApp } from "@/contexts/AppContext";

// ── Types ────────────────────────────────────────────────────────────────────

interface HistoryEntry {
  id: string;
  filename: string;
  date: string;
  result: PredictResult;
  inferenceMs: number;
}

interface DbDocument {
  id: number;
  filename: string;
  doc_type: "FACTURE" | "TRAITE";
  status: "PROCESSING" | "PENDING" | "VALIDATED";
  audit_status: string;
  owner_username: string | null;
  created_at: string;
  processing_time_s: number | null;
  numero: string | null;
  fournisseur: string | null;
  montant: number | null;
  client: string | null;
  date_echeance: string | null;
}

// ── Helpers ──────────────────────────────────────────────────────────────────

function statusColor(status: string) {
  switch (status) {
    case "VALIDATED": return { bg: "hsl(152 60% 40% / 0.1)", text: "hsl(152 60% 40%)", border: "hsl(152 60% 40% / 0.3)" };
    case "PENDING":   return { bg: "hsl(38 90% 52% / 0.1)",  text: "hsl(38 90% 52%)",  border: "hsl(38 90% 52% / 0.3)"  };
    default:          return { bg: "hsl(220 12% 50% / 0.1)", text: "hsl(220 12% 50%)", border: "hsl(220 12% 50% / 0.3)" };
  }
}

function auditBadgeColor(auditStatus: string) {
  if (auditStatus === "VALIDÉ")   return "hsl(152 60% 40%)";
  if (auditStatus.startsWith("ERREUR") || auditStatus === "ECHEANCE_DEPASSEE") return "hsl(0 72% 50%)";
  if (auditStatus === "DOUBLON" || auditStatus === "SIGNATURE_MANQUANTE")       return "hsl(38 90% 52%)";
  return "hsl(220 12% 50%)";
}

function formatDate(iso: string) {
  try {
    return new Date(iso).toLocaleString("fr-FR", {
      day: "2-digit", month: "2-digit", year: "numeric",
      hour: "2-digit", minute: "2-digit",
    });
  } catch { return iso; }
}

// ── Page principale ──────────────────────────────────────────────────────────

const DocumentsPage = () => {
  const { t } = useApp();

  // Onglet actif
  const [activeTab, setActiveTab] = useState<"local" | "db">("db");

  // ── Historique local (localStorage) ────────────────────────────────────────
  const [history, setHistory]   = useState<HistoryEntry[]>([]);
  const [search, setSearch]     = useState("");
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
    const data = { filename: entry.filename, date: entry.date, inferenceMs: entry.inferenceMs, entities: entitiesMap, full_text: entry.result.full_text };
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a"); a.href = url; a.download = `${entry.filename}.json`; a.click();
    URL.revokeObjectURL(url);
  };

  const filtered = history.filter(
    (e) => e.filename.toLowerCase().includes(search.toLowerCase()) ||
      e.result.entities.some((en) => en.text.toLowerCase().includes(search.toLowerCase())),
  );

  // ── Base de données PostgreSQL ─────────────────────────────────────────────
  const [dbDocs, setDbDocs]           = useState<DbDocument[]>([]);
  const [dbLoading, setDbLoading]     = useState(false);
  const [dbError, setDbError]         = useState<string | null>(null);
  const [dbSearch, setDbSearch]       = useState("");
  const [clearingDb, setClearingDb]   = useState(false);
  const session = getSession();
  const isAdmin = session?.role === "admin";

  const handleClearDocuments = async () => {
    if (!confirm("Vider la base PostgreSQL (documents + factures + traites) ? Cette action est irréversible.")) return;
    setClearingDb(true);
    try {
      const token = localStorage.getItem("odsinet_agent_token");
      const res = await fetch(`${AGENT_API_URL}/admin/clear-documents`, {
        method: "DELETE",
        headers: token ? { Authorization: `Bearer ${token}` } : {},
        signal: AbortSignal.timeout(5_000),
      });
      const data = await res.json();
      alert(data.message ?? "Base PostgreSQL vidée");
      fetchDbDocs();
    } catch (err) {
      alert("Erreur : " + (err instanceof Error ? err.message : String(err)));
    } finally {
      setClearingDb(false);
    }
  };

  const fetchDbDocs = useCallback(async () => {
    setDbLoading(true);
    setDbError(null);
    try {
      const res = await fetch(`${AGENT_API_URL}/pg/documents?limit=100`, {
        signal: AbortSignal.timeout(8_000),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setDbDocs(data.documents ?? []);
    } catch (err) {
      setDbError(err instanceof Error ? err.message : "Erreur de connexion au serveur agent (port 8002)");
    } finally {
      setDbLoading(false);
    }
  }, []);

  useEffect(() => {
    if (activeTab === "db") fetchDbDocs();
  }, [activeTab, fetchDbDocs]);

  const filteredDb = dbDocs.filter((d) =>
    (d.filename ?? "").toLowerCase().includes(dbSearch.toLowerCase()) ||
    (d.fournisseur ?? "").toLowerCase().includes(dbSearch.toLowerCase()) ||
    (d.numero ?? "").toLowerCase().includes(dbSearch.toLowerCase()),
  );

  return (
    <div className="p-6 lg:p-8 space-y-5 max-w-screen-xl mx-auto">
      <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }}>
        <h1 className="text-xl font-bold text-foreground">{t("hist_title")}</h1>
        <p className="text-sm text-muted-foreground mt-0.5">{t("hist_sub")}</p>
      </motion.div>

      {/* ── Onglets ── */}
      <div className="flex gap-1 p-1 rounded-lg w-fit" style={{ background: "hsl(var(--muted))" }}>
        <button
          onClick={() => setActiveTab("db")}
          className={`flex items-center gap-1.5 px-4 py-1.5 rounded-md text-sm font-medium transition-all ${
            activeTab === "db"
              ? "bg-card text-foreground shadow-sm"
              : "text-muted-foreground hover:text-foreground"
          }`}
        >
          <Database className="w-3.5 h-3.5" />
          Base de données
          {dbDocs.length > 0 && (
            <span className="ml-1 px-1.5 py-0.5 rounded-full text-[10px] font-bold"
              style={{ background: "hsl(var(--primary) / 0.12)", color: "hsl(var(--primary))" }}>
              {dbDocs.length}
            </span>
          )}
        </button>
        <button
          onClick={() => setActiveTab("local")}
          className={`flex items-center gap-1.5 px-4 py-1.5 rounded-md text-sm font-medium transition-all ${
            activeTab === "local"
              ? "bg-card text-foreground shadow-sm"
              : "text-muted-foreground hover:text-foreground"
          }`}
        >
          <Brain className="w-3.5 h-3.5" />
          {t("hist_title")} local
          {history.length > 0 && (
            <span className="ml-1 px-1.5 py-0.5 rounded-full text-[10px] font-bold"
              style={{ background: "hsl(var(--primary) / 0.12)", color: "hsl(var(--primary))" }}>
              {history.length}
            </span>
          )}
        </button>
      </div>

      {/* ══ ONGLET BASE DE DONNÉES ══════════════════════════════════════════════ */}
      {activeTab === "db" && (
        <div className="space-y-4">
          {/* Barre recherche + refresh */}
          <div className="flex flex-wrap items-center gap-3">
            <div className="relative flex-1 min-w-48">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
              <input
                type="text"
                placeholder="Rechercher par fichier, fournisseur, numéro…"
                value={dbSearch}
                onChange={(e) => setDbSearch(e.target.value)}
                className="input-base pl-9"
              />
            </div>
            <Button variant="outline" size="sm" onClick={fetchDbDocs} disabled={dbLoading}>
              <RefreshCw className={`w-3.5 h-3.5 mr-1.5 ${dbLoading ? "animate-spin" : ""}`} />
              Actualiser
            </Button>
            {isAdmin && (
              <Button
                variant="outline"
                size="sm"
                onClick={handleClearDocuments}
                disabled={clearingDb}
                style={{ color: "hsl(0 72% 50%)", borderColor: "hsl(0 72% 50% / 0.4)" }}
                title="Vide entièrement la base PostgreSQL (documents, factures, traites)"
              >
                <Trash2 className="w-3.5 h-3.5 mr-1.5" />
                {clearingDb ? "Nettoyage…" : "Vider la base"}
              </Button>
            )}
          </div>

          {/* Erreur serveur agent */}
          {dbError && (
            <div className="flex items-start gap-3 px-4 py-3 rounded-lg text-sm"
              style={{ background: "hsl(0 72% 50% / 0.06)", border: "1px solid hsl(0 72% 50% / 0.2)", color: "hsl(0 72% 50%)" }}>
              <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
              <div>
                <p className="font-medium">Serveur agent non disponible</p>
                <p className="text-[11px] mt-0.5 opacity-80">{dbError}</p>
                <p className="text-[11px] mt-0.5 font-mono opacity-60">cd assistant → uvicorn api.main:app --port 8002</p>
              </div>
            </div>
          )}

          {/* Chargement */}
          {dbLoading && (
            <div className="flex items-center justify-center py-12">
              <RefreshCw className="w-5 h-5 animate-spin text-primary mr-2" />
              <span className="text-sm text-muted-foreground">Chargement depuis PostgreSQL…</span>
            </div>
          )}

          {/* Vide */}
          {!dbLoading && !dbError && filteredDb.length === 0 && (
            <div className="glass-card rounded-lg p-16 flex flex-col items-center justify-center text-center">
              <div className="p-4 rounded-2xl bg-primary/10 mb-4">
                <Database className="w-8 h-8 text-primary" />
              </div>
              <p className="font-semibold text-foreground">
                {dbDocs.length === 0 ? "Aucun document en base" : "Aucun résultat"}
              </p>
              <p className="text-sm text-muted-foreground mt-1">
                {dbDocs.length === 0
                  ? "Analysez un document puis cliquez « Enregistrer en BDD »."
                  : `Aucun résultat pour « ${dbSearch} »`}
              </p>
            </div>
          )}

          {/* Tableau des documents PostgreSQL */}
          {!dbLoading && !dbError && filteredDb.length > 0 && (
            <div className="glass-card rounded-lg overflow-hidden">
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr style={{ borderBottom: "1px solid hsl(var(--border))", background: "hsl(var(--muted) / 0.5)" }}>
                      {["#", "Fichier", "Type", "N°", "Fournisseur / Tireur", "Montant", "Statut audit", "Workflow", "Date traitement", "Durée"].map((h) => (
                        <th key={h} className="px-4 py-2.5 text-left text-[11px] font-semibold text-muted-foreground uppercase tracking-wider whitespace-nowrap">
                          {h}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {filteredDb.map((doc, i) => {
                      const sc = statusColor(doc.status);
                      const auditColor = auditBadgeColor(doc.audit_status);
                      return (
                        <tr
                          key={doc.id}
                          style={{ borderBottom: "1px solid hsl(var(--border) / 0.5)", background: i % 2 === 0 ? "transparent" : "hsl(var(--muted) / 0.15)" }}
                        >
                          <td className="px-4 py-2.5 font-mono text-xs text-muted-foreground">{doc.id}</td>
                          <td className="px-4 py-2.5 max-w-[160px]">
                            <p className="truncate font-medium text-foreground text-xs">{doc.filename}</p>
                          </td>
                          <td className="px-4 py-2.5">
                            <span className={`flex items-center gap-1 w-fit px-2 py-0.5 rounded-full text-[10px] font-semibold ${
                              doc.doc_type === "FACTURE"
                                ? "text-blue-600 bg-blue-500/10"
                                : "text-emerald-600 bg-emerald-500/10"
                            }`}>
                              {doc.doc_type === "FACTURE"
                                ? <><FileCheck className="w-2.5 h-2.5" /> Facture</>
                                : <><FileX className="w-2.5 h-2.5" /> Traite</>}
                            </span>
                          </td>
                          <td className="px-4 py-2.5 font-mono text-xs text-foreground whitespace-nowrap">
                            {doc.numero ?? "—"}
                          </td>
                          <td className="px-4 py-2.5 text-xs text-foreground max-w-[160px]">
                            <p className="truncate">{doc.fournisseur ?? "—"}</p>
                          </td>
                          <td className="px-4 py-2.5 text-xs font-mono text-foreground whitespace-nowrap">
                            {doc.montant != null ? `${Number(doc.montant).toFixed(3)} DT` : "—"}
                          </td>
                          <td className="px-4 py-2.5">
                            <span className="text-[10px] font-semibold" style={{ color: auditColor }}>
                              {(doc.audit_status ?? "—").replace(/_/g, " ")}
                            </span>
                          </td>
                          <td className="px-4 py-2.5">
                            <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold"
                              style={{ background: sc.bg, color: sc.text, border: `1px solid ${sc.border}` }}>
                              {doc.status}
                            </span>
                          </td>
                          <td className="px-4 py-2.5 text-[10px] text-muted-foreground whitespace-nowrap">
                            {formatDate(doc.created_at)}
                          </td>
                          <td className="px-4 py-2.5 text-[10px] text-muted-foreground whitespace-nowrap">
                            {doc.processing_time_s != null
                              ? `${doc.processing_time_s}s`
                              : "—"}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
              <div className="px-4 py-2 border-t border-border flex items-center justify-between">
                <p className="text-[11px] text-muted-foreground">
                  {filteredDb.length} document{filteredDb.length !== 1 ? "s" : ""}
                  {dbSearch && ` · filtre : « ${dbSearch} »`}
                </p>
                <div className="flex items-center gap-3 text-[11px] text-muted-foreground">
                  <span>{dbDocs.filter(d => d.status === "VALIDATED").length} validés</span>
                  <span>{dbDocs.filter(d => d.status === "PENDING").length} en attente</span>
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* ══ ONGLET HISTORIQUE LOCAL ═════════════════════════════════════════════ */}
      {activeTab === "local" && (
        <div className="space-y-4">
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

          {history.length === 0 && (
            <div className="glass-card rounded-lg p-16 flex flex-col items-center justify-center text-center">
              <div className="p-4 rounded-2xl bg-primary/10 mb-4">
                <FileText className="w-8 h-8 text-primary" />
              </div>
              <p className="font-semibold text-foreground">{t("hist_empty")}</p>
              <p className="text-sm text-muted-foreground mt-1">
                {t("hist_empty_sub")} <span className="text-primary font-semibold">{t("nav_upload")}</span>
              </p>
            </div>
          )}

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
                <motion.div key={entry.id} initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: i * 0.04 }} className="glass-card rounded-lg overflow-hidden">
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
                    <div className="hidden sm:flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-semibold shrink-0"
                      style={{
                        background: detectedCount >= 4 ? "hsl(var(--success-bg))" : "hsl(38 95% 50% / 0.1)",
                        color: detectedCount >= 4 ? "hsl(var(--success))" : "hsl(38 95% 40%)",
                      }}>
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
                  <div className="flex flex-wrap gap-2 px-4 pb-3 sm:px-5">
                    {TARGET_LABELS.map((label) => {
                      const val = entitiesMap[label];
                      const found = !!val && val !== "N/A";
                      return (
                        <div key={label} className="flex items-center gap-1.5 px-2 py-1 rounded text-[10px] font-mono"
                          style={{
                            background: found ? "hsl(215 90% 50% / 0.08)" : "hsl(0 0% 50% / 0.06)",
                            color: found ? "hsl(215 90% 70%)" : "hsl(220 12% 50%)",
                          }}>
                          <span className="font-semibold">{label}:</span>
                          <span>{found ? val : "—"}</span>
                        </div>
                      );
                    })}
                  </div>
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
      )}
    </div>
  );
};

export default DocumentsPage;
