import { useState } from "react";
import { motion } from "framer-motion";
import { Sun, Moon, Languages, Users, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { getSession, getAllUsers, deleteUser } from "@/lib/auth";
import { useApp } from "@/contexts/AppContext";

const SettingsPage = () => {
  const { t, theme, toggleTheme, lang, setLang } = useApp();
  const [users, setUsers] = useState(getAllUsers());
  const session = getSession();

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
            {theme === "dark"
              ? <Moon className="w-4 h-4 text-primary" />
              : <Sun  className="w-4 h-4 text-primary" />}
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
              color:      theme === "dark" ? "white"               : "hsl(var(--muted-foreground))",
            }}
          >
            <Moon className="w-4 h-4" /> {t("set_dark")}
          </button>
          <button
            onClick={() => theme !== "light" && toggleTheme()}
            className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all"
            style={{
              background: theme === "light" ? "hsl(var(--primary))" : "hsl(var(--muted))",
              color:      theme === "light" ? "white"               : "hsl(var(--muted-foreground))",
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
                color:      lang === l ? "white"               : "hsl(var(--muted-foreground))",
              }}
            >
              {l === "fr" ? "Français" : "English"}
            </button>
          ))}
        </div>
      </motion.div>

      {/* User management — admin only */}
      {session?.role === "admin" && (
        <motion.div {...fade(0.12)} className="glass-card rounded-lg p-5">
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
              const isProtected = u.username === "admin";
              return (
                <div
                  key={u.username}
                  className="flex items-center justify-between px-3 py-2.5 rounded-lg"
                  style={{ background: "hsl(var(--muted))" }}
                >
                  <div className="flex items-center gap-3">
                    {u.photo ? (
                      <img
                        src={u.photo}
                        alt={u.displayName}
                        className="w-7 h-7 rounded-full object-cover shrink-0"
                      />
                    ) : (
                      <div
                        className="w-7 h-7 rounded-full flex items-center justify-center
                                   text-xs font-bold text-white shrink-0"
                        style={{ background: u.avatarColor }}
                      >
                        {u.displayName.split(" ").map((w) => w[0]).slice(0, 2).join("").toUpperCase()}
                      </div>
                    )}
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
                      {t("set_protected")}
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
