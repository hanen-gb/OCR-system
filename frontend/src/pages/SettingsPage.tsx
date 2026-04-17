import { useState, useEffect } from "react";
import { motion } from "framer-motion";
import {
  Cpu, Globe, Info, Zap, CheckCircle2, AlertCircle,
  Loader2, Save, RefreshCw, Sun, Moon, Languages, Users, Trash2,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { getApiUrl, setApiUrl, DEFAULT_API_URL, checkHealth } from "@/lib/api";
import { getSession, getAllUsers, deleteUser } from "@/lib/auth";
import { useApp } from "@/contexts/AppContext";

type HealthStatus = "idle" | "checking" | "ok" | "error";

const SettingsPage = () => {
  const { t, theme, toggleTheme, lang, setLang } = useApp();
  const [apiUrl, setApiUrlState] = useState(getApiUrl());
  const [healthStatus, setHealthStatus] = useState<HealthStatus>("idle");
  const [healthInfo, setHealthInfo] = useState<{ model?: string; gpu?: string } | null>(null);
  const [saved, setSaved] = useState(false);
  const [users, setUsers] = useState(getAllUsers());
  const session = getSession();

  useEffect(() => { setApiUrlState(getApiUrl()); }, []);

  const handleSave = () => {
    const url = apiUrl.trim().replace(/\/$/, "");
    setApiUrl(url);
    setApiUrlState(url);
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  };

  const handleReset = () => {
    setApiUrlState(DEFAULT_API_URL);
    setApiUrl(DEFAULT_API_URL);
  };

  const handleCheckHealth = async () => {
    setHealthStatus("checking"); setHealthInfo(null);
    try {
      const res = await checkHealth();
      if (res.status === "ok") { setHealthStatus("ok"); setHealthInfo({ model: res.model, gpu: res.gpu }); }
      else { setHealthStatus("error"); }
    } catch { setHealthStatus("error"); }
  };

  const handleDeleteUser = (username: string) => {
    deleteUser(username);
    setUsers(getAllUsers());
  };

  const fade = (delay = 0) => ({
    initial: { opacity: 0, y: 12 },
    animate: { opacity: 1, y: 0 },
    transition: { delay, duration: 0.3 },
  });

  return (
    <div className="p-6 lg:p-8 space-y-5 max-w-screen-xl mx-auto">
      <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }}>
        <h1 className="text-xl font-bold text-foreground">{t("set_title")}</h1>
      </motion.div>

      {/* Apparence */}
      <motion.div {...fade(0.04)} className="glass-card rounded-lg p-5">
        <div className="flex items-start gap-3 mb-4">
          <div className="p-2 rounded-lg bg-primary/10 mt-0.5">
            {theme === "dark" ? <Moon className="w-4 h-4 text-primary" /> : <Sun className="w-4 h-4 text-primary" />}
          </div>
          <div>
            <h3 className="text-sm font-semibold text-foreground">{t("set_theme")}</h3>
            <p className="text-xs text-muted-foreground mt-0.5">{t("set_theme_desc")}</p>
          </div>
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => theme !== "dark" && toggleTheme()}
            className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all"
            style={{
              background: theme === "dark" ? "hsl(var(--primary))" : "hsl(var(--muted))",
              color: theme === "dark" ? "white" : "hsl(var(--muted-foreground))",
            }}
          >
            <Moon className="w-4 h-4" /> {t("set_dark")}
          </button>
          <button
            onClick={() => theme !== "light" && toggleTheme()}
            className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all"
            style={{
              background: theme === "light" ? "hsl(var(--primary))" : "hsl(var(--muted))",
              color: theme === "light" ? "white" : "hsl(var(--muted-foreground))",
            }}
          >
            <Sun className="w-4 h-4" /> {t("set_light")}
          </button>
        </div>
      </motion.div>

      {/* Langue */}
      <motion.div {...fade(0.08)} className="glass-card rounded-lg p-5">
        <div className="flex items-start gap-3 mb-4">
          <div className="p-2 rounded-lg bg-primary/10 mt-0.5">
            <Languages className="w-4 h-4 text-primary" />
          </div>
          <div>
            <h3 className="text-sm font-semibold text-foreground">{t("set_language")}</h3>
            <p className="text-xs text-muted-foreground mt-0.5">{t("set_language_desc")}</p>
          </div>
        </div>
        <div className="flex gap-2">
          {(["fr", "en"] as const).map((l) => (
            <button
              key={l}
              onClick={() => setLang(l)}
              className="px-4 py-2 rounded-lg text-sm font-semibold transition-all"
              style={{
                background: lang === l ? "hsl(var(--primary))" : "hsl(var(--muted))",
                color: lang === l ? "white" : "hsl(var(--muted-foreground))",
              }}
            >
              {l === "fr" ? "Français" : "English"}
            </button>
          ))}
        </div>
      </motion.div>

      {/* Backend URL */}
      <motion.div {...fade(0.12)} className="glass-card rounded-lg p-5">
        <div className="flex items-start gap-3 mb-4">
          <div className="p-2 rounded-lg bg-primary/10 mt-0.5">
            <Globe className="w-4 h-4 text-primary" />
          </div>
          <div>
            <h3 className="text-sm font-semibold text-foreground">{t("set_api_url")}</h3>
            <p className="text-xs text-muted-foreground mt-0.5">{t("set_api_desc")}</p>
          </div>
        </div>
        <div className="space-y-3">
          <div className="flex gap-2">
            <input
              type="url"
              value={apiUrl}
              onChange={(e) => setApiUrlState(e.target.value)}
              placeholder="https://..."
              className="input-base font-mono flex-1"
            />
            <Button variant="outline" size="sm" onClick={handleReset} title="Rétablir défaut">
              <RefreshCw className="w-3.5 h-3.5" />
            </Button>
          </div>
          <div className="flex gap-2">
            <Button size="sm" onClick={handleSave}>
              <Save className="w-3.5 h-3.5 mr-1.5" />
              {saved ? t("set_saved") : t("set_save")}
            </Button>
            <Button variant="outline" size="sm" onClick={handleCheckHealth} disabled={healthStatus === "checking"}>
              {healthStatus === "checking"
                ? <Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" />
                : <Zap className="w-3.5 h-3.5 mr-1.5" />}
              {healthStatus === "checking" ? t("set_testing") : t("set_test")}
            </Button>
          </div>
          {healthStatus === "ok" && healthInfo && (
            <div className="flex items-center gap-2 px-3 py-2 rounded-lg text-xs"
              style={{ background: "hsl(var(--success-bg))", color: "hsl(var(--success))", border: "1px solid hsl(var(--success) / 0.3)" }}>
              <CheckCircle2 className="w-4 h-4 shrink-0" />
              {t("set_ok")} · <span className="font-mono font-semibold">{healthInfo.model}</span> · GPU: {healthInfo.gpu}
            </div>
          )}
          {healthStatus === "error" && (
            <div className="flex items-center gap-2 px-3 py-2 rounded-lg text-xs"
              style={{ background: "hsl(var(--danger-bg))", color: "hsl(var(--danger))", border: "1px solid hsl(var(--danger) / 0.3)" }}>
              <AlertCircle className="w-4 h-4 shrink-0" />
              {t("set_error")}
            </div>
          )}
          <p className="text-xs text-muted-foreground font-mono">{DEFAULT_API_URL}</p>
        </div>
      </motion.div>

      {/* Modèle */}
      <motion.div {...fade(0.16)} className="glass-card rounded-lg p-5">
        <div className="flex items-start gap-3 mb-4">
          <div className="p-2 rounded-lg bg-primary/10 mt-0.5">
            <Cpu className="w-4 h-4 text-primary" />
          </div>
          <div>
            <h3 className="text-sm font-semibold text-foreground">{t("set_model")}</h3>
            <p className="text-xs text-muted-foreground mt-0.5">{t("set_model_desc")}</p>
          </div>
        </div>
        <div className="space-y-1.5 text-sm">
          {[
            { label: "HuggingFace", value: "Goubaa/glmocr-factures" },
            { label: "Base", value: "zai-org/GLM-OCR" },
            { label: "Fine-tuning", value: "LoRA merged · float16" },
            { label: "GPU", value: "T4 · CUDA 12.1" },
            { label: "Cold-start", value: "~40s" },
            { label: "Inférence (warm)", value: "~65s" },
          ].map(({ label, value }) => (
            <div key={label} className="flex items-center justify-between py-1.5 border-b border-border/40 last:border-0">
              <span className="text-xs text-muted-foreground">{label}</span>
              <span className="font-mono text-xs font-semibold text-foreground">{value}</span>
            </div>
          ))}
        </div>
      </motion.div>

      {/* Entités */}
      <motion.div {...fade(0.2)} className="glass-card rounded-lg p-5">
        <div className="flex items-start gap-3 mb-4">
          <div className="p-2 rounded-lg bg-primary/10 mt-0.5">
            <Info className="w-4 h-4 text-primary" />
          </div>
          <div>
            <h3 className="text-sm font-semibold text-foreground">{t("set_entities")}</h3>
            <p className="text-xs text-muted-foreground mt-0.5">{t("set_entities_desc")}</p>
          </div>
        </div>
        <div className="flex flex-wrap gap-2">
          {["CLIENT", "FOURNISSEUR", "NUMERO_FACTURE", "DATE_FACTURE", "MONTANT_TTC"].map((label) => (
            <div key={label} className="px-3 py-1.5 rounded-lg text-xs font-mono font-semibold bg-primary/10 text-primary">
              {label}
            </div>
          ))}
        </div>
      </motion.div>

      {/* Session */}
      <motion.div {...fade(0.24)} className="glass-card rounded-lg p-5">
        <div className="flex items-start gap-3 mb-4">
          <div className="p-2 rounded-lg bg-primary/10 mt-0.5">
            <Info className="w-4 h-4 text-primary" />
          </div>
          <div>
            <h3 className="text-sm font-semibold text-foreground">{t("set_session")}</h3>
            <p className="text-xs text-muted-foreground mt-0.5">{t("set_session_desc")}</p>
          </div>
        </div>
        <div className="space-y-1.5 text-sm">
          {[
            { label: "Username", value: session?.username ?? "—" },
            { label: t("prof_display_name"), value: session?.displayName ?? "—" },
            { label: t("prof_role"), value: session?.role ?? "—" },
          ].map(({ label, value }) => (
            <div key={label} className="flex items-center justify-between py-1.5 border-b border-border/40 last:border-0">
              <span className="text-xs text-muted-foreground">{label}</span>
              <span className="text-xs font-semibold text-foreground">{value}</span>
            </div>
          ))}
        </div>
      </motion.div>

      {/* Gestion utilisateurs (admin seulement) */}
      {session?.role === "admin" && (
        <motion.div {...fade(0.28)} className="glass-card rounded-lg p-5">
          <div className="flex items-start gap-3 mb-4">
            <div className="p-2 rounded-lg bg-primary/10 mt-0.5">
              <Users className="w-4 h-4 text-primary" />
            </div>
            <div>
              <h3 className="text-sm font-semibold text-foreground">{t("set_manage_users")}</h3>
              <p className="text-xs text-muted-foreground mt-0.5">{t("set_manage_users_desc")}</p>
            </div>
          </div>
          <div className="space-y-2">
            {users.map((u) => {
              const isProtected = u.username === "admin" || u.username === "user";
              return (
                <div
                  key={u.username}
                  className="flex items-center justify-between px-3 py-2.5 rounded-lg"
                  style={{ background: "hsl(var(--muted))" }}
                >
                  <div className="flex items-center gap-3">
                    <div
                      className="w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold text-white shrink-0"
                      style={{ background: u.avatarColor }}
                    >
                      {u.displayName.split(" ").map((w) => w[0]).slice(0, 2).join("").toUpperCase()}
                    </div>
                    <div>
                      <p className="text-sm font-medium text-foreground">{u.displayName}</p>
                      <p className="text-xs text-muted-foreground">@{u.username} · {u.role}</p>
                    </div>
                  </div>
                  {!isProtected ? (
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => handleDeleteUser(u.username)}
                      className="text-red-400 hover:text-red-500"
                      title={t("set_delete_user")}
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </Button>
                  ) : (
                    <span className="text-[10px] px-2 py-0.5 rounded-full bg-primary/10 text-primary font-semibold">
                      protégé
                    </span>
                  )}
                </div>
              );
            })}
          </div>
          <p className="text-xs text-muted-foreground mt-3">
            {users.length} {t("set_user_count")}
          </p>
        </motion.div>
      )}
    </div>
  );
};

export default SettingsPage;
