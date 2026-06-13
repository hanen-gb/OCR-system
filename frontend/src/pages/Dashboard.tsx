import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import {
  FileText, Users, Building2, CheckCircle2, Clock, BarChart2,
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
  accent?: string; // couleur optionnelle pour la valeur
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

  // ── Calculs depuis les données réelles ──────────────────────────────────────
  const totalDocs = history.length;

  const uniqueSuppliers = new Set(
    history
      .flatMap((e) => e.result.entities)
      .filter((en) => en.label === "FOURNISSEUR" && en.text && en.text !== "N/A")
      .map((en) => en.text.trim().toLowerCase()),
  ).size;

  const uniqueClients = new Set(
    history
      .flatMap((e) => e.result.entities)
      .filter((en) => en.label === "CLIENT" && en.text && en.text !== "N/A")
      .map((en) => en.text.trim().toLowerCase()),
  ).size;

  const completeDocs = history.filter((e) => e.result.entities.length >= 4).length;
  const completionRate = totalDocs > 0 ? Math.round((completeDocs / totalDocs) * 100) : 0;

  // Taux de détection par entité — calculé sur le sous-ensemble pertinent par type
  const factures = history.filter((e) =>
    !e.result.entities.some((en) => ["TIREUR", "TIRE", "RIB"].includes(en.label))
  );
  const traites = history.filter((e) =>
    e.result.entities.some((en) => ["TIREUR", "TIRE", "RIB"].includes(en.label))
  );

  const FACTURE_LABELS: { lbl: string; color: string }[] = [
    { lbl: "CLIENT",         color: "hsl(215 80% 58%)" },
    { lbl: "FOURNISSEUR",    color: "hsl(180 55% 45%)" },
    { lbl: "NUMERO_FACTURE", color: "hsl(262 60% 60%)" },
    { lbl: "DATE_FACTURE",   color: "hsl(38 90% 52%)"  },
    { lbl: "MONTANT_TTC",    color: "hsl(152 60% 45%)" },
  ];
  const TRAITE_LABELS: { lbl: string; color: string }[] = [
    { lbl: "TIREUR",        color: "hsl(215 80% 58%)" },
    { lbl: "TIRE",          color: "hsl(180 55% 45%)" },
    { lbl: "RIB",           color: "hsl(262 60% 60%)" },
    { lbl: "DATE_ECHEANCE", color: "hsl(38 90% 52%)"  },
    { lbl: "MONTANT",       color: "hsl(152 60% 45%)" },
  ];

  const _detectionRate = (subset: typeof history, lbl: string) => {
    if (subset.length === 0) return 0;
    const n = subset.filter((e) =>
      e.result.entities.some((en) => en.label === lbl && en.text && en.text !== "N/A")
    ).length;
    return Math.round((n / subset.length) * 100);
  };

  // Donut : factures si majoritaires, sinon traites, sinon mélange sur les 5 labels facture
  const activeSubset  = factures.length >= traites.length ? factures : traites;
  const activeLabels  = factures.length >= traites.length ? FACTURE_LABELS : TRAITE_LABELS;
  const activeCount   = activeSubset.length;

  const entityDetection = activeLabels.map(({ lbl, color }) => ({
    name  : lbl.replace(/_/g, " "),
    value : _detectionRate(activeSubset, lbl),
    fill  : color,
    count : activeCount,
  }));

  const avgMs = totalDocs > 0
    ? Math.round(history.reduce((a, e) => a + e.inferenceMs, 0) / totalDocs)
    : 0;

  const lastDate = history.length > 0 ? history[0].date : null;

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
      label: t("dash_suppliers"),
      value: uniqueSuppliers || "—",
      sub: totalDocs > 0 ? t("dash_suppliers_sub").replace("{n}", String(totalDocs)) : "—",
      icon: Building2,
      delay: 0.05,
      accent: "hsl(180 55% 45%)",
    },
    {
      label: t("dash_clients"),
      value: uniqueClients || "—",
      sub: totalDocs > 0 ? t("dash_clients_sub") : "—",
      icon: Users,
      delay: 0.1,
      accent: "hsl(262 60% 60%)",
    },
    {
      label: t("dash_completion"),
      value: totalDocs > 0 ? `${completionRate}%` : "—",
      sub: t("dash_completion_sub"),
      icon: CheckCircle2,
      delay: 0.15,
      accent: completionRate >= 80 ? "hsl(152 60% 45%)" : "hsl(38 90% 52%)",
    },
    {
      label: t("dash_avg_inference"),
      value: totalDocs > 0 ? `${(avgMs / 1000).toFixed(0)}s` : "—",
      sub: "GPU T4 · Modal serverless",
      icon: Clock,
      delay: 0.2,
    },
    {
      label: t("dash_last_analysis"),
      value: lastDate ?? t("dash_never"),
      sub: lastDate ? history[0].filename : "—",
      icon: BarChart2,
      delay: 0.25,
    },
  ];

  return (
    <div className="p-6 lg:p-8 space-y-6 max-w-screen-xl mx-auto">
      <motion.div {...fade(0)}>
        <h1 className="text-xl font-bold text-foreground">{t("dash_title")}</h1>
      </motion.div>

      {/* KPIs — 3 colonnes sur md, 6 sur xl */}
      <div className="grid grid-cols-2 sm:grid-cols-3 xl:grid-cols-6 gap-4">
        {kpis.map((kpi) => (
          <KpiCard key={kpi.label} {...kpi} />
        ))}
      </div>

      {/* Graphiques */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
        {/* Temps inférence */}
        <motion.div {...fade(0.3)} className="lg:col-span-2 glass-card rounded-xl p-5">
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

        {/* Détection par entité — données réelles */}
        <motion.div {...fade(0.35)} className="glass-card rounded-xl p-5">
          <h3 className="text-sm font-semibold text-foreground mb-4">
            Détection par entité
          </h3>
          {totalDocs === 0 ? (
            <div className="h-[160px] flex items-center justify-center">
              <p className="text-xs text-muted-foreground">{t("dash_no_data")}</p>
            </div>
          ) : (
            <ResponsiveContainer width="100%" height={160}>
              <PieChart>
                <Pie
                  data={entityDetection}
                  cx="50%" cy="50%"
                  innerRadius={40} outerRadius={68}
                  paddingAngle={3} dataKey="value"
                >
                  {entityDetection.map((entry, i) => (
                    <Cell key={i} fill={entry.fill} />
                  ))}
                </Pie>
                <Tooltip contentStyle={TOOLTIP_STYLE} formatter={(v) => `${v}%`} />
              </PieChart>
            </ResponsiveContainer>
          )}
          <div className="space-y-1.5 mt-1">
            {entityDetection.map((item) => (
              <div key={item.name} className="flex items-center justify-between text-xs">
                <div className="flex items-center gap-2">
                  <div className="w-2 h-2 rounded-full shrink-0" style={{ background: item.fill }} />
                  <span className="text-muted-foreground">{item.name}</span>
                </div>
                <span className="font-semibold text-foreground">
                  {totalDocs > 0 ? `${item.value}%` : "—"}
                </span>
              </div>
            ))}
          </div>
        </motion.div>
      </div>

      {/* Historique récent */}
      <motion.div {...fade(0.5)} className="glass-card rounded-xl overflow-hidden">
        <div className="flex items-center justify-between px-5 py-3.5" style={{ borderBottom: "1px solid hsl(var(--border))" }}>
          <h3 className="text-sm font-semibold text-foreground">{t("dash_recent")}</h3>
          <span className="text-xs text-muted-foreground">
            {totalDocs} {totalDocs !== 1 ? t("common_docs") : t("common_doc")}
          </span>
        </div>
        {history.length === 0 ? (
          <div className="px-5 py-10 text-center text-sm text-muted-foreground">
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
                  <th>DATE</th>
                  <th>MONTANT</th>
                  <th>{t("dash_inference")}</th>
                </tr>
              </thead>
              <tbody>
                {history.slice(0, 6).map((entry) => {
                  const em: Record<string, string> = {};
                  for (const e of entry.result.entities) em[e.label] = e.text;
                  return (
                    <tr key={entry.id}>
                      <td>
                        <div className="flex items-center gap-2">
                          <FileText className="w-3.5 h-3.5 text-muted-foreground shrink-0" />
                          <span className="font-medium truncate max-w-[140px]">{entry.filename}</span>
                        </div>
                      </td>
                      <td className="text-xs">{em.CLIENT ?? "—"}</td>
                      <td className="text-xs">{em.FOURNISSEUR ?? "—"}</td>
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
    </div>
  );
};

export default Dashboard;
