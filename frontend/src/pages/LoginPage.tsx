import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import { Eye, EyeOff, Loader2, LogIn, UserPlus, Languages } from "lucide-react";
import { Button } from "@/components/ui/button";
import { login, register } from "@/lib/auth";
import { t as translate, type Lang } from "@/lib/i18n";
import odsinetLogo from "@/assets/odsinet-logo.png";

const LoginPage = () => {
  const [mode, setMode] = useState<"login" | "register">("login");
  const [lang, setLang] = useState<Lang>("fr");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPwd, setConfirmPwd] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [email, setEmail] = useState("");
  const [showPwd, setShowPwd] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const navigate = useNavigate();

  const tl = (key: Parameters<typeof translate>[1]) => translate(lang, key);

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(""); setSuccess("");
    setLoading(true);
    await new Promise((r) => setTimeout(r, 600));
    const user = login(username.trim(), password);
    setLoading(false);
    if (!user) { setError(tl("auth_error")); return; }
    navigate("/");
  };

  const handleRegister = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(""); setSuccess("");
    if (password !== confirmPwd) { setError(tl("prof_pwd_mismatch")); return; }
    setLoading(true);
    await new Promise((r) => setTimeout(r, 400));
    const res = register(username.trim(), password, displayName.trim(), email.trim());
    setLoading(false);
    if (!res.ok) { setError(res.error ?? "Erreur"); return; }
    setSuccess(lang === "fr" ? "Compte créé ! Vous pouvez vous connecter." : "Account created! You can now sign in.");
    setMode("login");
    setPassword(""); setConfirmPwd("");
  };

  const switchMode = (m: "login" | "register") => {
    setMode(m); setError(""); setSuccess("");
  };

  return (
    <div className="min-h-screen flex items-center justify-center p-4" style={{ background: "hsl(var(--background))" }}>
      {/* Grille de fond */}
      <div
        className="absolute inset-0 opacity-[0.04] pointer-events-none"
        style={{
          backgroundImage:
            "linear-gradient(hsl(215 80% 40%) 1px, transparent 1px), linear-gradient(90deg, hsl(215 80% 40%) 1px, transparent 1px)",
          backgroundSize: "40px 40px",
        }}
      />

      {/* Bouton langue — coin haut droit */}
      <button
        onClick={() => setLang(lang === "fr" ? "en" : "fr")}
        className="absolute top-4 right-4 flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition-colors hover:bg-accent"
        style={{ color: "hsl(var(--muted-foreground))", border: "1px solid hsl(var(--border))" }}
      >
        <Languages className="w-3.5 h-3.5" />
        {lang === "fr" ? "EN" : "FR"}
      </button>

      <motion.div
        initial={{ opacity: 0, y: 24 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4 }}
        className="relative w-full max-w-sm"
      >
        {/* Logo + nom */}
        <div className="text-center mb-8">
          <img src={odsinetLogo} alt="ODSINET" className="w-20 h-20 mx-auto mb-3 object-contain" />
          <h1
            className="text-2xl font-bold"
            style={{ fontFamily: "'Orbitron', sans-serif", color: "hsl(215 80% 60%)" }}
          >
            ODSI<span style={{ color: "hsl(var(--foreground))" }}>NET</span>
          </h1>
        </div>

        {/* Card */}
        <div className="glass-card rounded-xl p-6">
          {/* Onglets */}
          <div className="flex rounded-lg overflow-hidden mb-5" style={{ background: "hsl(var(--muted))" }}>
            {(["login", "register"] as const).map((m) => (
              <button
                key={m}
                onClick={() => switchMode(m)}
                className="flex-1 py-2 text-sm font-medium transition-colors"
                style={{
                  background: mode === m ? "hsl(var(--primary))" : "transparent",
                  color: mode === m ? "white" : "hsl(var(--muted-foreground))",
                  borderRadius: "0.375rem",
                }}
              >
                {m === "login" ? tl("auth_login") : tl("auth_register")}
              </button>
            ))}
          </div>

          <AnimatePresence mode="wait">
            {mode === "login" ? (
              <motion.form
                key="login"
                initial={{ opacity: 0, x: -16 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: 16 }}
                transition={{ duration: 0.2 }}
                onSubmit={handleLogin}
                className="space-y-4"
              >
                <div>
                  <label className="text-xs font-medium text-muted-foreground mb-1.5 block">
                    {tl("auth_username")}
                  </label>
                  <input
                    type="text"
                    value={username}
                    onChange={(e) => setUsername(e.target.value)}
                    placeholder="admin"
                    autoComplete="username"
                    required
                    className="input-base"
                  />
                </div>

                <div>
                  <label className="text-xs font-medium text-muted-foreground mb-1.5 block">
                    {tl("auth_password")}
                  </label>
                  <div className="relative">
                    <input
                      type={showPwd ? "text" : "password"}
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      placeholder="••••••••"
                      autoComplete="current-password"
                      required
                      className="input-base pr-10"
                    />
                    <button
                      type="button"
                      onClick={() => setShowPwd(!showPwd)}
                      className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground transition-colors"
                    >
                      {showPwd ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                    </button>
                  </div>
                </div>

                {error && (
                  <motion.div
                    initial={{ opacity: 0, y: -4 }} animate={{ opacity: 1, y: 0 }}
                    className="px-3 py-2 rounded-lg text-xs"
                    style={{ background: "hsl(var(--danger-bg))", color: "hsl(var(--danger))" }}
                  >
                    {error}
                  </motion.div>
                )}
                {success && (
                  <motion.div
                    initial={{ opacity: 0, y: -4 }} animate={{ opacity: 1, y: 0 }}
                    className="px-3 py-2 rounded-lg text-xs"
                    style={{ background: "hsl(var(--success-bg))", color: "hsl(var(--success))" }}
                  >
                    {success}
                  </motion.div>
                )}

                <Button type="submit" className="w-full" disabled={loading}>
                  {loading ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <LogIn className="w-4 h-4 mr-2" />}
                  {loading ? tl("auth_signing") : tl("auth_signin")}
                </Button>

                <p className="text-center text-xs text-muted-foreground">
                  {tl("auth_no_account")}{" "}
                  <button type="button" onClick={() => switchMode("register")} className="text-primary hover:underline font-semibold">
                    {tl("auth_register")}
                  </button>
                </p>
              </motion.form>
            ) : (
              <motion.form
                key="register"
                initial={{ opacity: 0, x: 16 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -16 }}
                transition={{ duration: 0.2 }}
                onSubmit={handleRegister}
                className="space-y-3"
              >
                <div>
                  <label className="text-xs font-medium text-muted-foreground mb-1.5 block">
                    {tl("auth_username")}
                  </label>
                  <input
                    type="text"
                    value={username}
                    onChange={(e) => setUsername(e.target.value)}
                    placeholder="mon_username"
                    autoComplete="username"
                    required
                    className="input-base"
                  />
                </div>

                <div>
                  <label className="text-xs font-medium text-muted-foreground mb-1.5 block">
                    {tl("auth_display_name")}
                  </label>
                  <input
                    type="text"
                    value={displayName}
                    onChange={(e) => setDisplayName(e.target.value)}
                    placeholder="Prénom Nom"
                    className="input-base"
                  />
                </div>

                <div>
                  <label className="text-xs font-medium text-muted-foreground mb-1.5 block">
                    {tl("auth_email")}
                  </label>
                  <input
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="email@exemple.com"
                    className="input-base"
                  />
                </div>

                <div>
                  <label className="text-xs font-medium text-muted-foreground mb-1.5 block">
                    {tl("auth_password")}
                  </label>
                  <div className="relative">
                    <input
                      type={showPwd ? "text" : "password"}
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      placeholder="••••••••"
                      autoComplete="new-password"
                      required
                      className="input-base pr-10"
                    />
                    <button
                      type="button"
                      onClick={() => setShowPwd(!showPwd)}
                      className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground transition-colors"
                    >
                      {showPwd ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                    </button>
                  </div>
                </div>

                <div>
                  <label className="text-xs font-medium text-muted-foreground mb-1.5 block">
                    {tl("auth_confirm_password")}
                  </label>
                  <input
                    type={showPwd ? "text" : "password"}
                    value={confirmPwd}
                    onChange={(e) => setConfirmPwd(e.target.value)}
                    placeholder="••••••••"
                    autoComplete="new-password"
                    required
                    className="input-base"
                  />
                </div>

                {error && (
                  <motion.div
                    initial={{ opacity: 0, y: -4 }} animate={{ opacity: 1, y: 0 }}
                    className="px-3 py-2 rounded-lg text-xs"
                    style={{ background: "hsl(var(--danger-bg))", color: "hsl(var(--danger))" }}
                  >
                    {error}
                  </motion.div>
                )}

                <Button type="submit" className="w-full" disabled={loading}>
                  {loading ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <UserPlus className="w-4 h-4 mr-2" />}
                  {loading ? tl("common_loading") : tl("auth_create")}
                </Button>

                <p className="text-center text-xs text-muted-foreground">
                  {tl("auth_have_account")}{" "}
                  <button type="button" onClick={() => switchMode("login")} className="text-primary hover:underline font-semibold">
                    {tl("auth_login")}
                  </button>
                </p>
              </motion.form>
            )}
          </AnimatePresence>
        </div>
      </motion.div>
    </div>
  );
};

export default LoginPage;
