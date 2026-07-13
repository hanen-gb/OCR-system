import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import {
  FileText, Users, Building2, CheckCircle2, Clock, BarChart2,
  Receipt, Landmark,
} from "lucide-react";
import {
  XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, PieChart, Pie, Cell, AreaChart, Area,
} from "recharts";
import { type PredictResult } from "@/lib/api";
import { getSession, getHistoryKey } from "@/lib/auth";
import { useApp } from "@/contexts/AppContext";

interface HistoryEntry {
  id: string;
  filename: string;
  date: string;
  result: PredictResult;
  inferenceMs: number;
}

const fade = (delay = 0) => ({
  initial: { opacity: 0, y: 16 },
  animate: { opacity: 1, y: 0 },
  transition: { delay, duration: 0.35 },
});

const TOOLTIP_STYLE = {
  background: "hsl(222 30% 14%)",
  border: "1px solid hsl(222 22% 22%)",
  borderRadius: "6px",
  color: "hsl(210 20% 88%)",
  fontSize: 12,
};

interface KpiCardProps {
  label: string;
  value: string | number;
  sub?: string;
  icon: React.ElementType;
  delay?: number;
  accent?: string;
}

const KpiCard = ({ label, value, sub, icon: Icon, delay = 0, accent }: KpiCardProps) => (
  <motion.div {...fade(delay)} className="glass-card rounded-xl p-5 hover-lift group cursor-default">
    <div className="flex items-start justify-between">
      <div className="min-w-0 flex-1">
        <p className="text-xs font-medium text-muted-foreground mb-1 transition-colors duration-200 group-hover:text-foreground/70">{label}</p>
        <p
          className="text-2xl font-bold led-text truncate transition-all duration-300 group-hover:scale-105 origin-left"
          style={{ color: accent ?? "hsl(var(--primary))", display: "block" }}
        >
          {value}
        </p>
        {sub && <p className="text-xs text-muted-foreground mt-0.5">{sub}</p>}
      </div>
      <div className="p-2.5 rounded-xl bg-primary/10 shrink-0 ml-3 icon-box">
        <Icon className="w-5 h-5 text-primary" />
      </div>
    </div>
  </motion.div>
);

// Détecte si un document historique est une traite ou une facture.
// Le classificateur (MobileNet/Modal) peut se tromper sur doc_type — on laisse
// les signaux les plus fiables (labels d'entités réellement extraites, puis nom
// de fichier) corriger une éventuelle mauvaise classification avant de se fier
// au doc_type brut, qui n'est consulté qu'en dernier recours.
const _isTraite = (entry: HistoryEntry): boolean => {
  // Priorité 1 : labels d'entités réellement présentes (le plus fiable)
  const labels = entry.result.entities.map((e) => e.label);
  if (["TIREUR", "TIRE", "RIB", "DOMICILIATION", "NUMERO_TRAITE"].some((l) => labels.includes(l))) return true;

  // Priorité 2 : doc_type explicite retourné par le GLM/API
  const dt = (entry.result.doc_type ?? "").toLowerCase();
  if (dt.includes("traite") || dt.includes("lettre") || dt.includes("change")) return true;

  // Priorité 3 : nom du fichier — peut corriger un doc_type="factures" erroné
  const fn = entry.filename.toLowerCase();
  if (fn.includes("traite") || fn.includes("lettre") || fn.includes("ldc") || fn.includes("billet")) return true;

  return false;
};

// Mini donut pour un type de document
interface DonutCardProps {
  title: string;
  labels: { lbl: string; color: string }[];
  subset: HistoryEntry[];
  totalDocs: number;
  delay?: number;
  accentColor: string;
}

const _detectionRate = (subset: HistoryEntry[], lbl: string) => {
  if (subset.length === 0) return 0;
  const n = subset.filter((e) =>
    e.result.entities.some((en) => en.label === lbl && en.text && en.text !== "N/A")
  ).length;
  return Math.round((n / subset.length) * 100);
};

const DonutCard = ({ title, labels, subset, totalDocs, delay = 0, accentColor }: DonutCardProps) => {
  const data = labels.map(({ lbl, color }) => ({
    name: lbl.replace(/_/g, " "),
    value: _detectionRate(subset, lbl),
    fill: color,
  }));

  // Quand tout est 0%, on affiche quand même les couleurs avec parts égales
  const allZero = data.every((d) => d.value === 0);
  const pieData = allZero ? data.map((d) => ({ ...d, value: 1 })) : data;
  const badgeBg = accentColor.replace(")", " / 0.15)").replace("hsl(", "hsl(");

  return (
    <motion.div {...fade(delay)} className="glass-card rounded-xl p-5">
      <div className="flex items-center justify-between mb-1">
        <h3 className="text-sm font-semibold text-foreground">{title}</h3>
        <span
          className="text-xs font-bold px-2 py-0.5 rounded-full"
          style={{ background: badgeBg, color: accentColor }}
        >
          {subset.length}
        </span>
      </div>
      {totalDocs === 0 || subset.length === 0 ? (
        <div className="h-[130px] flex flex-col items-center justify-center gap-1">
          <p className="text-xs text-muted-foreground">Aucune donnée</p>
        </div>
      ) : (
        <>
          <ResponsiveContainer width="100%" height={130}>
            <PieChart>
              <Pie
                data={pieData}
                cx="50%" cy="50%"
                innerRadius={32} outerRadius={55}
                paddingAngle={3}
                dataKey="value"
              >
                {pieData.map((entry, i) => (
                  <Cell key={i} fill={entry.fill} />
                ))}
              </Pie>
              <Tooltip
                contentStyle={TOOLTIP_STYLE}
                formatter={(_v, name) => {
                  const real = data.find((d) => d.name === name)?.value ?? 0;
                  return [`${real}%`, name];
                }}
              />
            </PieChart>
          </ResponsiveContainer>
          {allZero && (
            <p className="text-[10px] text-center text-muted-foreground -mt-1 mb-1">
              En attente de détections
            </p>
          )}
        </>
      )}
      <div className="space-y-1 mt-1">
        {data.map((item) => (
          <div key={item.name} className="flex items-center justify-between text-xs">
            <div className="flex items-center gap-2">
              <div className="w-2 h-2 rounded-full shrink-0" style={{ background: item.fill }} />
              <span className="text-muted-foreground truncate max-w-[90px]">{item.name}</span>
            </div>
            <span className="font-semibold text-foreground">
              {subset.length > 0 ? `${item.value}%` : "—"}
            </span>
          </div>
        ))}
      </div>
    </motion.div>
  );
};

const Dashboard = () => {
  const { t } = useApp();
  const [history, setHistory] = useState<HistoryEntry[]>([]);

  useEffect(() => {
    const session = getSession();
    const key = session ? getHistoryKey(session.username) : "odsinet_history_guest";
    const raw = localStorage.getItem(key);
    if (raw) {
      try { setHistory(JSON.parse(raw)); } catch { /* ignore */ }
    }
  }, []);

  // ── Calculs ─────────────────────────────────────────────────────────────────
  const totalDocs = history.length;

  const traites  = history.filter(_isTraite);
  const factures = history.filter((e) => !_isTraite(e));

  const uniqueSuppliers = new Set(
    history
      .flatMap((e) => e.result.entities)
      .filter((en) => (en.label === "FOURNISSEUR" || en.label === "TIRE") && en.text && en.text !== "N/A")
      .map((en) => en.text.trim().toLowerCase()),
  ).size;

  const uniqueClients = new Set(
    history
      .flatMap((e) => e.result.entities)
      .filter((en) => (en.label === "CLIENT" || en.label === "TIREUR") && en.text && en.text !== "N/A")
      .map((en) => en.text.trim().toLowerCase()),
  ).size;

  const completeDocs = history.filter((e) => e.result.entities.length >= 4).length;
  const completionRate = totalDocs > 0 ? Math.round((completeDocs / totalDocs) * 100) : 0;

  const avgMs = totalDocs > 0
    ? Math.round(history.reduce((a, e) => a + e.inferenceMs, 0) / totalDocs)
    : 0;

  const lastDate = history.length > 0 ? history[0].date : null;

  const FACTURE_LABELS: { lbl: string; color: string }[] = [
    { lbl: "CLIENT",         color: "hsl(215 80% 58%)" },
    { lbl: "FOURNISSEUR",    color: "hsl(180 55% 45%)" },
    { lbl: "NUMERO_FACTURE", color: "hsl(262 60% 60%)" },
    { lbl: "DATE_FACTURE",   color: "hsl(38 90% 52%)"  },
    { lbl: "MONTANT_TTC",    color: "hsl(152 60% 45%)" },
  ];
  const TRAITE_LABELS: { lbl: string; color: string }[] = [
    { lbl: "TIREUR",        color: "hsl(328 70% 55%)" },
    { lbl: "TIRE",          color: "hsl(280 55% 55%)" },
    { lbl: "RIB",           color: "hsl(195 65% 48%)" },
    { lbl: "DATE_ECHEANCE", color: "hsl(38 90% 52%)"  },
    { lbl: "MONTANT",       color: "hsl(152 60% 45%)" },
  ];

  // Graphique temps d'inférence (10 dernières)
  const inferenceData = history.slice(0, 10).map((e, i) => ({
    doc: `#${i + 1}`,
    s: Math.round(e.inferenceMs / 1000),
  })).reverse();

  const kpis: KpiCardProps[] = [
    {
      label: t("dash_docs"),
      value: totalDocs,
      sub: t("dash_docs_sub"),
      icon: FileText,
      delay: 0,
    },
    {
      label: t("dash_factures"),
      value: totalDocs === 0 ? "—" : factures.length,
      sub: t("dash_factures_sub"),
      icon: Receipt,
      delay: 0.05,
      accent: "hsl(215 80% 58%)",
    },
    {
      label: t("dash_traites"),
      value: totalDocs === 0 ? "—" : traites.length,
      sub: t("dash_traites_sub"),
      icon: Landmark,
      delay: 0.1,
      accent: "hsl(328 70% 55%)",
    },
    {
      label: t("dash_suppliers"),
      value: uniqueSuppliers || "—",
      sub: totalDocs > 0 ? t("dash_suppliers_sub").replace("{n}", String(totalDocs)) : "—",
      icon: Building2,
      delay: 0.15,
      accent: "hsl(180 55% 45%)",
    },
    {
      label: t("dash_clients"),
      value: uniqueClients || "—",
      sub: totalDocs > 0 ? t("dash_clients_sub") : "—",
      icon: Users,
      delay: 0.2,
      accent: "hsl(262 60% 60%)",
    },
    {
      label: t("dash_completion"),
      value: totalDocs > 0 ? `${completionRate}%` : "—",
      sub: t("dash_completion_sub"),
      icon: CheckCircle2,
      delay: 0.25,
      accent: completionRate >= 80 ? "hsl(152 60% 45%)" : "hsl(38 90% 52%)",
    },
    {
      label: t("dash_avg_inference"),
      value: totalDocs > 0 ? `${(avgMs / 1000).toFixed(0)}s` : "—",
      sub: "GPU T4 · Modal serverless",
      icon: Clock,
      delay: 0.3,
    },
    {
      label: t("dash_last_analysis"),
      value: lastDate ?? t("dash_never"),
      sub: lastDate ? history[0].filename : "—",
      icon: BarChart2,
      delay: 0.35,
    },
  ];

  return (
    <div className="p-6 lg:p-8 space-y-6 max-w-screen-xl mx-auto">
      <motion.div {...fade(0)}>
        <h1 className="text-xl font-bold text-foreground">{t("dash_title")}</h1>
      </motion.div>

      {/* KPIs — 4 colonnes */}
      <div className="grid grid-cols-2 sm:grid-cols-4 xl:grid-cols-4 gap-4">
        {kpis.map((kpi) => (
          <KpiCard key={kpi.label} {...kpi} />
        ))}
      </div>

      {/* Graphiques */}
      <div className="grid grid-cols-1 lg:grid-cols-4 gap-5">
        {/* Temps inférence */}
        <motion.div {...fade(0.4)} className="lg:col-span-2 glass-card rounded-xl p-5">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-semibold text-foreground">{t("dash_chart_time")}</h3>
            {totalDocs === 0 && (
              <span className="text-xs text-muted-foreground italic">{t("dash_no_data")}</span>
            )}
          </div>
          {totalDocs > 0 ? (
            <ResponsiveContainer width="100%" height={220}>
              <AreaChart data={inferenceData}>
                <defs>
                  <linearGradient id="inferGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="hsl(215 80% 55%)" stopOpacity={0.3} />
                    <stop offset="95%" stopColor="hsl(215 80% 55%)" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="hsl(222 22% 22%)" vertical={false} />
                <XAxis dataKey="doc" tick={{ fontSize: 11, fill: "hsl(215 15% 55%)" }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fontSize: 11, fill: "hsl(215 15% 55%)" }} axisLine={false} tickLine={false} />
                <Tooltip contentStyle={TOOLTIP_STYLE} formatter={(v: number) => [`${v}s`, "Inférence"]} />
                <Area type="monotone" dataKey="s" stroke="hsl(215 80% 58%)" strokeWidth={2} fill="url(#inferGrad)" />
              </AreaChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-[220px] flex items-center justify-center rounded-lg" style={{ background: "hsl(222 25% 12%)" }}>
              <p className="text-sm text-muted-foreground">{t("dash_no_data")}</p>
            </div>
          )}
        </motion.div>

        {/* Donut Factures */}
        <DonutCard
          title={t("dash_detection_factures")}
          labels={FACTURE_LABELS}
          subset={factures}
          totalDocs={totalDocs}
          delay={0.45}
          accentColor="hsl(215, 80%, 58%)"
        />

        {/* Donut Lettres de change */}
        <DonutCard
          title={t("dash_detection_traites")}
          labels={TRAITE_LABELS}
          subset={traites}
          totalDocs={totalDocs}
          delay={0.5}
          accentColor="hsl(328, 70%, 55%)"
        />
      </div>

      {/* Tableau Factures */}
      <motion.div {...fade(0.55)} className="glass-card rounded-xl overflow-hidden">
        <div className="flex items-center justify-between px-5 py-3.5" style={{ borderBottom: "1px solid hsl(var(--border))" }}>
          <div className="flex items-center gap-2">
            <span className="w-2.5 h-2.5 rounded-full" style={{ background: "hsl(215 80% 58%)" }} />
            <h3 className="text-sm font-semibold text-foreground">{t("dash_factures")} — {t("dash_recent")}</h3>
          </div>
          <span className="text-xs text-muted-foreground">{factures.length} doc{factures.length !== 1 ? "s" : ""}</span>
        </div>
        {factures.length === 0 ? (
          <div className="px-5 py-8 text-center text-sm text-muted-foreground">
            {t("dash_no_analysis")} <span className="text-primary font-semibold">{t("dash_analyze_link")}</span>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full data-table">
              <thead>
                <tr>
                  <th>{t("common_file")}</th>
                  <th>CLIENT</th>
                  <th>FOURNISSEUR</th>
                  <th>N° FACTURE</th>
                  <th>DATE</th>
                  <th>MONTANT TTC</th>
                  <th>{t("dash_inference")}</th>
                </tr>
              </thead>
              <tbody>
                {factures.slice(0, 5).map((entry) => {
                  const em: Record<string, string> = {};
                  for (const e of entry.result.entities) em[e.label] = e.text;
                  return (
                    <tr key={entry.id}>
                      <td>
                        <div className="flex items-center gap-2">
                          <FileText className="w-3.5 h-3.5 text-muted-foreground shrink-0" />
                          <span className="font-medium truncate max-w-[130px]">{entry.filename}</span>
                        </div>
                      </td>
                      <td className="text-xs">{em.CLIENT ?? "—"}</td>
                      <td className="text-xs">{em.FOURNISSEUR ?? "—"}</td>
                      <td className="text-xs font-mono">{em.NUMERO_FACTURE ?? "—"}</td>
                      <td className="text-xs font-mono">{em.DATE_FACTURE ?? "—"}</td>
                      <td className="font-mono text-xs font-semibold text-primary">{em.MONTANT_TTC ?? "—"}</td>
                      <td>
                        <span className={`text-xs font-mono font-semibold ${entry.inferenceMs < 70000 ? "text-success" : "text-warning"}`}>
                          {(entry.inferenceMs / 1000).toFixed(1)}s
                        </span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </motion.div>

      {/* Tableau Lettres de change */}
      <motion.div {...fade(0.6)} className="glass-card rounded-xl overflow-hidden">
        <div className="flex items-center justify-between px-5 py-3.5" style={{ borderBottom: "1px solid hsl(var(--border))" }}>
          <div className="flex items-center gap-2">
            <span className="w-2.5 h-2.5 rounded-full" style={{ background: "hsl(328 70% 55%)" }} />
            <h3 className="text-sm font-semibold text-foreground">{t("dash_traites")} — {t("dash_recent")}</h3>
          </div>
          <span className="text-xs text-muted-foreground">{traites.length} doc{traites.length !== 1 ? "s" : ""}</span>
        </div>
        {traites.length === 0 ? (
          <div className="px-5 py-8 text-center text-sm text-muted-foreground">
            {t("dash_no_analysis")} <span className="text-primary font-semibold">{t("dash_analyze_link")}</span>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full data-table">
              <thead>
                <tr>
                  <th>{t("common_file")}</th>
                  <th>TIREUR</th>
                  <th>TIRÉ</th>
                  <th>N° TRAITE</th>
                  <th>ÉCHÉANCE</th>
                  <th>MONTANT</th>
                  <th>RIB / DOMICILIATION</th>
                  <th>{t("dash_inference")}</th>
                </tr>
              </thead>
              <tbody>
                {traites.slice(0, 5).map((entry) => {
                  const em: Record<string, string> = {};
                  for (const e of entry.result.entities) em[e.label] = e.text;
                  return (
                    <tr key={entry.id}>
                      <td>
                        <div className="flex items-center gap-2">
                          <FileText className="w-3.5 h-3.5 text-muted-foreground shrink-0" />
                          <span className="font-medium truncate max-w-[120px]">{entry.filename}</span>
                        </div>
                      </td>
                      <td className="text-xs">{em.TIREUR ?? "—"}</td>
                      <td className="text-xs">{em.TIRE ?? "—"}</td>
                      <td className="text-xs font-mono">{em.NUMERO_TRAITE ?? "—"}</td>
                      <td className="text-xs font-mono">{em.DATE_ECHEANCE ?? "—"}</td>
                      <td className="font-mono text-xs font-semibold" style={{ color: "hsl(328 70% 65%)" }}>
                        {em.MONTANT ?? "—"}
                      </td>
                      <td className="text-xs text-muted-foreground">
                        {em.RIB ?? em.DOMICILIATION ?? "—"}
                      </td>
                      <td>
                        <span className={`text-xs font-mono font-semibold ${entry.inferenceMs < 70000 ? "text-success" : "text-warning"}`}>
                          {(entry.inferenceMs / 1000).toFixed(1)}s
                        </span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </motion.div>
    </div>
  );
};

export default Dashboard;
