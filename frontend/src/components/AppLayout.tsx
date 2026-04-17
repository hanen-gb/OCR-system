import { useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import {
  LayoutDashboard, Upload, FileText, Settings,
  ChevronLeft, ChevronRight, LogOut, User,
  Sun, Moon, Languages, CalendarDays, Menu, X,
} from "lucide-react";
import { logout, getSession } from "@/lib/auth";
import { useApp } from "@/contexts/AppContext";
import odsinetLogo from "@/assets/odsinet-logo.png";

const useNavSections = (t: (k: string) => string) => [
  {
    label: t("nav_section_main"),
    items: [
      { path: "/",          icon: LayoutDashboard, labelKey: "nav_dashboard" },
      { path: "/upload",    icon: Upload,          labelKey: "nav_upload" },
      { path: "/documents", icon: FileText,        labelKey: "nav_history" },
      { path: "/calendar",  icon: CalendarDays,    labelKey: "nav_calendar" },
    ],
  },
  {
    label: t("nav_section_system"),
    items: [
      { path: "/profile",  icon: User,     labelKey: "nav_profile" },
      { path: "/settings", icon: Settings, labelKey: "nav_settings" },
    ],
  },
];

interface AppLayoutProps { children: React.ReactNode; }

/* ── Avatar initiales ── */
function Avatar({ user }: { user: { displayName: string; avatarColor?: string } }) {
  const initials = user.displayName
    .split(" ")
    .map((w) => w[0])
    .slice(0, 2)
    .join("")
    .toUpperCase();
  return (
    <div
      className="w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold text-white shrink-0"
      style={{ background: user.avatarColor ?? "hsl(215 80% 55%)" }}
    >
      {initials}
    </div>
  );
}

/* ── Contenu de la sidebar ── */
function SidebarContent({
  collapsed,
  onClose,
}: {
  collapsed: boolean;
  onClose?: () => void;
}) {
  const { t, theme, toggleTheme, lang, setLang } = useApp();
  const location = useLocation();
  const navigate  = useNavigate();
  const session   = getSession();
  const navSections = useNavSections(t);

  const handleLogout = () => {
    logout();
    onClose?.();
    navigate("/login");
  };

  return (
    <div className="flex flex-col h-full" style={{ background: "hsl(var(--sidebar-background))" }}>
      {/* Logo — même hauteur que la topbar (h-14 = 56px) */}
      <div
        className="flex items-center gap-2.5 px-3 h-14 shrink-0"
        style={{ borderBottom: "1px solid hsl(var(--sidebar-border))" }}
      >
        <img
          src={odsinetLogo}
          alt="ODSINET"
          className="object-contain shrink-0"
          style={{ width: collapsed ? 36 : 40, height: collapsed ? 36 : 40, transition: "all 0.25s" }}
        />
        <AnimatePresence>
          {!collapsed && (
            <motion.p
              initial={{ opacity: 0, x: -8 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -8 }}
              className="text-sm font-bold tracking-widest whitespace-nowrap"
              style={{ fontFamily: "'Orbitron', sans-serif", color: "hsl(215 80% 65%)", letterSpacing: "0.15em" }}
            >
              ODSI<span style={{ color: "hsl(var(--sidebar-accent-foreground))" }}>NET</span>
            </motion.p>
          )}
        </AnimatePresence>
      </div>

      {/* Nav */}
      <nav className="flex-1 overflow-y-auto py-3 px-2 space-y-4">
        {navSections.map((section) => (
          <div key={section.label}>
            <AnimatePresence>
              {!collapsed && (
                <motion.p
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  exit={{ opacity: 0 }}
                  className="section-header px-2 mb-1.5"
                >
                  {section.label}
                </motion.p>
              )}
            </AnimatePresence>
            <div className="space-y-0.5">
              {section.items.map((item) => {
                const isActive = location.pathname === item.path;
                return (
                  <Link
                    key={item.path}
                    to={item.path}
                    title={collapsed ? t(item.labelKey as never) : undefined}
                    onClick={onClose}
                    className={`nav-item ${isActive ? "active" : ""} ${collapsed ? "justify-center px-0" : ""}`}
                  >
                    {isActive && (
                      <motion.div
                        layoutId="active-nav"
                        className="absolute left-0 top-1/2 -translate-y-1/2 w-[3px] h-5 rounded-r-full"
                        style={{ background: "hsl(var(--sidebar-primary))", boxShadow: "0 0 8px hsl(var(--sidebar-primary))" }}
                      />
                    )}
                    <item.icon style={{ width: 18, height: 18 }} className="shrink-0" />
                    <AnimatePresence>
                      {!collapsed && (
                        <motion.span
                          initial={{ opacity: 0 }}
                          animate={{ opacity: 1 }}
                          exit={{ opacity: 0 }}
                          className="truncate"
                        >
                          {t(item.labelKey as never)}
                        </motion.span>
                      )}
                    </AnimatePresence>
                  </Link>
                );
              })}
            </div>
          </div>
        ))}
      </nav>

      {/* Toggles theme + langue */}
      <div
        className="px-2 py-2 flex items-center gap-1"
        style={{ borderTop: "1px solid hsl(var(--sidebar-border))" }}
      >
        <button
          onClick={toggleTheme}
          title={theme === "dark" ? t("set_light") : t("set_dark")}
          className="flex items-center justify-center rounded-lg p-2 transition-colors hover:bg-accent"
          style={{ color: "hsl(var(--sidebar-foreground))" }}
        >
          {theme === "dark"
            ? <Sun style={{ width: 15, height: 15 }} />
            : <Moon style={{ width: 15, height: 15 }} />}
        </button>
        <button
          onClick={() => setLang(lang === "fr" ? "en" : "fr")}
          title={lang === "fr" ? "Switch to English" : "Passer en français"}
          className="flex items-center justify-center rounded-lg p-2 transition-colors hover:bg-accent gap-1"
          style={{ color: "hsl(var(--sidebar-foreground))" }}
        >
          <Languages style={{ width: 15, height: 15 }} />
          <AnimatePresence>
            {!collapsed && (
              <motion.span
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                className="text-xs font-semibold"
              >
                {lang === "fr" ? "EN" : "FR"}
              </motion.span>
            )}
          </AnimatePresence>
        </button>
      </div>

      {/* User + logout */}
      <div style={{ borderTop: "1px solid hsl(var(--sidebar-border))" }}>
        <AnimatePresence>
          {!collapsed && session && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="px-3 py-2.5 flex items-center gap-2"
            >
              <Avatar user={session} />
              <div className="min-w-0">
                <p className="text-xs font-semibold truncate" style={{ color: "hsl(var(--sidebar-accent-foreground))" }}>
                  {session.displayName}
                </p>
                <p className="text-[10px] truncate" style={{ color: "hsl(var(--sidebar-foreground))", opacity: 0.6 }}>
                  {session.email || session.username}
                </p>
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        <div className="flex items-center" style={{ borderTop: "1px solid hsl(var(--sidebar-border))" }}>
          {collapsed && session && (
            <div className="flex items-center justify-center w-full py-2">
              <Avatar user={session} />
            </div>
          )}
          {!collapsed && (
            <button
              onClick={handleLogout}
              title={t("nav_logout")}
              className="flex items-center justify-center gap-1.5 w-full h-9 text-xs transition-colors hover:text-red-400"
              style={{ color: "hsl(var(--sidebar-foreground))" }}
            >
              <LogOut style={{ width: 14, height: 14 }} />
              <span>{t("nav_logout")}</span>
            </button>
          )}
          {collapsed && (
            <button
              onClick={handleLogout}
              title={t("nav_logout")}
              className="flex items-center justify-center w-full h-9 transition-colors hover:text-red-400"
              style={{ color: "hsl(var(--sidebar-foreground))" }}
            >
              <LogOut style={{ width: 14, height: 14 }} />
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

/* ── Layout principal ── */
const AppLayout = ({ children }: AppLayoutProps) => {
  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const { t, theme } = useApp();

  return (
    <div className="flex h-screen overflow-hidden bg-background">

      {/* ── DESKTOP sidebar ── */}
      <motion.aside
        animate={{ width: collapsed ? 60 : 252 }}
        transition={{ duration: 0.25, ease: "easeInOut" }}
        className="hidden lg:flex flex-col shrink-0 overflow-hidden relative"
        style={{ borderRight: "1px solid hsl(var(--sidebar-border))" }}
      >
        <SidebarContent collapsed={collapsed} />
        {/* Bouton collapse */}
        <button
          onClick={() => setCollapsed(!collapsed)}
          className="absolute -right-3 top-20 z-10 w-6 h-6 rounded-full flex items-center justify-center transition-colors"
          style={{
            background: "hsl(var(--sidebar-background))",
            border: "1px solid hsl(var(--sidebar-border))",
            color: "hsl(var(--sidebar-foreground))",
          }}
        >
          {collapsed
            ? <ChevronRight style={{ width: 12, height: 12 }} />
            : <ChevronLeft style={{ width: 12, height: 12 }} />}
        </button>
      </motion.aside>

      {/* ── MOBILE drawer overlay ── */}
      <AnimatePresence>
        {mobileOpen && (
          <>
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="fixed inset-0 z-40 bg-black/50 lg:hidden"
              onClick={() => setMobileOpen(false)}
            />
            <motion.aside
              initial={{ x: -280 }}
              animate={{ x: 0 }}
              exit={{ x: -280 }}
              transition={{ duration: 0.25, ease: "easeInOut" }}
              className="fixed left-0 top-0 bottom-0 z-50 w-64 lg:hidden"
              style={{ borderRight: "1px solid hsl(var(--sidebar-border))" }}
            >
              <SidebarContent collapsed={false} onClose={() => setMobileOpen(false)} />
              <button
                onClick={() => setMobileOpen(false)}
                className="absolute top-3 right-3 p-1 rounded-md"
                style={{ color: "hsl(var(--sidebar-foreground))" }}
              >
                <X style={{ width: 16, height: 16 }} />
              </button>
            </motion.aside>
          </>
        )}
      </AnimatePresence>

      {/* ── Contenu principal ── */}
      <div className="flex-1 flex flex-col overflow-hidden min-w-0">

        {/* Topbar */}
        <header className="topbar flex items-center h-14 px-4 sm:px-6 shrink-0 gap-3">
          {/* Hamburger mobile */}
          <button
            onClick={() => setMobileOpen(true)}
            className="lg:hidden p-2 rounded-lg transition-colors shrink-0"
            style={{ color: "hsl(var(--muted-foreground))" }}
          >
            <Menu style={{ width: 20, height: 20 }} />
          </button>

          {/* Badge backend — collé à gauche sur desktop */}
          <div
            className="flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-medium led-glow"
            style={{ background: "hsl(var(--success-bg))", color: "hsl(var(--success))" }}
          >
            <div className="w-1.5 h-1.5 rounded-full animate-pulse" style={{ background: "hsl(var(--success))" }} />
            {t("common_backend_active")}
          </div>
        </header>

        {/* Contenu page */}
        <main className="flex-1 overflow-auto bg-background">
          {children}
        </main>
      </div>
    </div>
  );
};

export default AppLayout;
