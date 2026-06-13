import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import { Eye, EyeOff, Loader2 } from "lucide-react";
import { login, register } from "@/lib/auth";
import { fetchToken } from "@/lib/api";
import heroScanner from "@/assets/image_facture.png";
import odsinetLogoBanner from "@/assets/odsinet-logo-bunner .png";

/* ── Brand icons ─────────────────────────────────────────────────── */
const GoogleIcon = () => (
  <svg viewBox="0 0 24 24" className="w-4 h-4 shrink-0" fill="none">
    <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" fill="#4285F4"/>
    <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853"/>
    <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l3.66-2.84z" fill="#FBBC05"/>
    <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335"/>
  </svg>
);

const GitHubIcon = () => (
  <svg viewBox="0 0 24 24" className="w-4 h-4 shrink-0" fill="currentColor">
    <path d="M12 .297c-6.63 0-12 5.373-12 12 0 5.303 3.438 9.8 8.205 11.385.6.113.82-.258.82-.577 0-.285-.01-1.04-.015-2.04-3.338.724-4.042-1.61-4.042-1.61C4.422 18.07 3.633 17.7 3.633 17.7c-1.087-.744.084-.729.084-.729 1.205.084 1.838 1.236 1.838 1.236 1.07 1.835 2.809 1.305 3.495.998.108-.776.417-1.305.76-1.605-2.665-.3-5.466-1.332-5.466-5.93 0-1.31.465-2.38 1.235-3.22-.135-.303-.54-1.523.105-3.176 0 0 1.005-.322 3.3 1.23.96-.267 1.98-.399 3-.405 1.02.006 2.04.138 3 .405 2.28-1.552 3.285-1.23 3.285-1.23.645 1.653.24 2.873.12 3.176.765.84 1.23 1.91 1.23 3.22 0 4.61-2.805 5.625-5.475 5.92.42.36.81 1.096.81 2.22 0 1.606-.015 2.896-.015 3.286 0 .315.21.69.825.57C20.565 22.092 24 17.592 24 12.297c0-6.627-5.373-12-12-12"/>
  </svg>
);

const MicrosoftIcon = () => (
  <svg viewBox="0 0 21 21" className="w-4 h-4 shrink-0" fill="none">
    <path d="M0 0h10v10H0z" fill="#F25022"/>
    <path d="M11 0h10v10H11z" fill="#7FBA00"/>
    <path d="M0 11h10v10H0z" fill="#00A4EF"/>
    <path d="M11 11h10v10H11z" fill="#FFB900"/>
  </svg>
);

/* ── Input with left icon ─────────────────────────────────────────── */
const IconInput = ({
  icon, type = "text", value, onChange, placeholder,
  autoComplete, required, rightSlot,
}: {
  icon: React.ReactNode;
  type?: string;
  value: string;
  onChange: (e: React.ChangeEvent<HTMLInputElement>) => void;
  placeholder: string;
  autoComplete?: string;
  required?: boolean;
  rightSlot?: React.ReactNode;
}) => (
  <div className="relative">
    <span className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none">
      {icon}
    </span>
    <input
      type={type} value={value} onChange={onChange}
      placeholder={placeholder} autoComplete={autoComplete} required={required}
      className="w-full rounded-lg pl-9 py-2.5 text-sm outline-none transition-all placeholder:text-slate-500"
      style={{
        paddingRight: rightSlot ? "2.5rem" : "0.75rem",
        background: "rgba(255,255,255,0.05)",
        border: "1px solid rgba(255,255,255,0.1)",
        color: "#f1f5f9",
      }}
      onFocus={(e) => {
        e.currentTarget.style.borderColor = "rgba(56,189,248,0.5)";
        e.currentTarget.style.background  = "rgba(255,255,255,0.07)";
      }}
      onBlur={(e) => {
        e.currentTarget.style.borderColor = "rgba(255,255,255,0.1)";
        e.currentTarget.style.background  = "rgba(255,255,255,0.05)";
      }}
    />
    {rightSlot && (
      <span className="absolute right-3 top-1/2 -translate-y-1/2">{rightSlot}</span>
    )}
  </div>
);

const PersonIcon = () => (
  <svg viewBox="0 0 20 20" fill="currentColor" className="w-4 h-4">
    <path d="M10 10a4 4 0 1 0 0-8 4 4 0 0 0 0 8zm-6 8a6 6 0 1 1 12 0H4z"/>
  </svg>
);
const MailIcon = () => (
  <svg viewBox="0 0 20 20" fill="currentColor" className="w-4 h-4">
    <path d="M2 4a2 2 0 0 1 2-2h12a2 2 0 0 1 2 2v.5L10 11 2 4.5V4zm0 2.5V16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V6.5l-8 6.5-8-6.5z"/>
  </svg>
);
const LockIcon = () => (
  <svg viewBox="0 0 20 20" fill="currentColor" className="w-4 h-4">
    <path fillRule="evenodd" d="M5 8V6a5 5 0 0 1 10 0v2h1a1 1 0 0 1 1 1v8a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V9a1 1 0 0 1 1-1h1zm2 0h6V6a3 3 0 0 0-6 0v2zm3 4a1 1 0 0 0-1 1v2a1 1 0 0 0 2 0v-2a1 1 0 0 0-1-1z" clipRule="evenodd"/>
  </svg>
);

/* ── Feedback & submit button ─────────────────────────────────────── */
const Feedback = ({ type, children }: { type: "error" | "success"; children: React.ReactNode }) => (
  <motion.p
    initial={{ opacity: 0, y: -4 }} animate={{ opacity: 1, y: 0 }}
    className="text-xs px-3 py-2 rounded-lg"
    style={
      type === "error"
        ? { background: "rgba(239,68,68,0.12)", color: "#f87171" }
        : { background: "rgba(34,197,94,0.12)",  color: "#4ade80" }
    }
  >
    {children}
  </motion.p>
);

const SubmitBtn = ({ loading, children }: { loading: boolean; children: React.ReactNode }) => (
  <button
    type="submit" disabled={loading}
    className="w-full py-2.5 rounded-lg text-sm font-semibold flex items-center justify-center gap-2 transition-all duration-200 disabled:opacity-60 hover:scale-[1.02] hover:shadow-[0_0_20px_rgba(56,189,248,0.3)]"
    style={{
      background: "linear-gradient(135deg, #1e3a5f, #1a4a7a)",
      color: "#e2e8f0",
      border: "1px solid rgba(56,189,248,0.3)",
    }}
  >
    {loading && <Loader2 className="w-4 h-4 animate-spin"/>}
    {children}
  </button>
);

/* ═══════════════════════════════════════════════════════════════════
   LoginPage
═══════════════════════════════════════════════════════════════════ */
const BG = "#12172a";

const LoginPage = () => {
  const [mode, setMode]             = useState<"login" | "register">("register");
  const [firstName,   setFirstName] = useState("");
  const [lastName,    setLastName]  = useState("");
  const [regEmail,    setRegEmail]  = useState("");
  const [regPwd,      setRegPwd]    = useState("");
  const [confirmPwd,  setConfirmPwd]= useState("");
  const [showRegPwd,     setShowRegPwd]     = useState(false);
  const [showConfirmPwd, setShowConfirmPwd] = useState(false);
  const [loginUser,   setLoginUser] = useState("");
  const [loginPwd,    setLoginPwd]  = useState("");
  const [showLoginPwd, setShowLoginPwd]     = useState(false);
  const [loading,  setLoading]  = useState(false);
  const [error,    setError]    = useState("");
  const [success,  setSuccess]  = useState("");
  const navigate = useNavigate();

  const switchMode = (m: "login" | "register") => { setMode(m); setError(""); setSuccess(""); };

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(""); setSuccess(""); setLoading(true);
    await new Promise((r) => setTimeout(r, 600));
    const user = login(loginUser.trim(), loginPwd);
    setLoading(false);
    if (!user) { setError("Invalid username or password."); return; }
    // Obtenir un JWT FastAPI pour les appels protégés (silencieux si agent hors ligne)
    fetchToken(user.username, user.role).catch(() => {});
    navigate("/");
  };

  const handleRegister = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(""); setSuccess("");
    if (regPwd !== confirmPwd) { setError("Passwords do not match."); return; }
    if (regPwd.length < 4)     { setError("Password must be at least 4 characters."); return; }
    setLoading(true);
    await new Promise((r) => setTimeout(r, 400));
    const displayName = `${firstName.trim()} ${lastName.trim()}`.trim();
    const res = register(regEmail.trim().toLowerCase(), regPwd, displayName, regEmail.trim());
    setLoading(false);
    if (!res.ok) { setError(res.error ?? "Registration failed. Please try again."); return; }
    setSuccess("Account created! You can now sign in.");
    setLoginUser(regEmail.trim().toLowerCase());
    switchMode("login");
    setRegPwd(""); setConfirmPwd("");
  };

  return (
    <div className="min-h-screen flex flex-col lg:flex-row relative overflow-hidden" style={{ background: BG, color: "#f1f5f9" }}>

      {/* ── Decorative background orbs ── */}
      <div className="login-orb" style={{ width: 420, height: 420, background: "hsl(215 80% 55%)", top: "-120px", left: "-100px", animationDelay: "0s" }} />
      <div className="login-orb" style={{ width: 300, height: 300, background: "hsl(262 60% 55%)", bottom: "60px", right: "30%", animationDelay: "1.5s", animationDuration: "5s" }} />
      <div className="login-orb" style={{ width: 200, height: 200, background: "hsl(38 90% 52%)", bottom: "-60px", left: "20%", animationDelay: "3s", animationDuration: "4s", opacity: 0.1 }} />

      {/* ════════════════════════════════════════════
          LEFT PANEL — hero scanner image  (~45 %)
          Hidden on mobile, shown on lg+
      ════════════════════════════════════════════ */}
      <div className="hidden lg:flex lg:w-1/2 shrink-0 items-stretch justify-center p-5 self-stretch">

        {/* Image card with rounded corners */}
        <div
          className="relative w-full h-full rounded-2xl overflow-hidden"
          style={{ boxShadow: "0 0 0 1px rgba(56,189,248,0.15), 0 25px 60px rgba(0,0,0,0.55), 0 0 40px rgba(56,189,248,0.08)" }}
        >
          {/* Hero photo — fully visible, covers the card */}
          <img
            src={heroScanner}
            alt=""
            className="w-full h-full object-cover object-center transition-transform duration-700 hover:scale-105"
          />

          {/* Animated scan line */}
          <div
            className="absolute left-0 right-0 h-[2px] pointer-events-none animate-scan"
            style={{ background: "linear-gradient(90deg, transparent, rgba(56,189,248,0.6), transparent)", top: "10%" }}
          />

          {/* Subtle bottom gradient for text readability only */}
          <div
            className="absolute inset-x-0 bottom-0 h-2/5 pointer-events-none"
            style={{
              background:
                "linear-gradient(to bottom, transparent 0%, rgba(10,14,26,0.75) 60%, rgba(10,14,26,0.97) 100%)",
            }}
          />

          {/* Bottom text */}
          <div className="absolute bottom-0 left-0 right-0 p-7 z-10">
            <div className="flex gap-3 mb-3">
              <div className="w-7 h-0.5 rounded-full" style={{ background: "rgba(255,255,255,0.7)" }}/>
              <div className="w-7 h-0.5 rounded-full" style={{ background: "rgba(255,255,255,0.7)" }}/>
            </div>
            <h2 className="text-3xl font-bold text-white mb-1.5 leading-tight drop-shadow-lg">
              Digitize your vision.
            </h2>
            <p className="text-sm italic drop-shadow" style={{ color: "rgba(255,255,255,0.6)" }}>
              Optical document system for INET.
            </p>
          </div>
        </div>
      </div>

      {/* ════════════════════════════════════════════
          RIGHT PANEL — auth form  (~60 %)
          Full width on mobile
      ════════════════════════════════════════════ */}
      <div
        className="w-full lg:w-1/2 flex items-center justify-center px-4 sm:px-8 py-10"
        style={{ background: BG }}
      >
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4 }}
          className="w-full max-w-md"
        >
          {/* ── Logo banner image (seamlessly on dark bg) ── */}
          <div className="flex justify-center mb-5">
            <img
              src={odsinetLogoBanner}
              alt="ODSINET"
              className="h-14 sm:h-16 w-auto object-contain animate-float"
              style={{ filter: "drop-shadow(0 0 16px rgba(56,189,248,0.45))" }}
            />
          </div>

          {/* Title */}
          <h1 className="text-center text-xl sm:text-2xl font-bold text-white mb-6">
            {mode === "register" ? "Create an ODSINET Account" : "Sign in to ODSINET"}
          </h1>

          {/* Tab switcher */}
          <div
            className="flex rounded-lg p-1 mb-5"
            style={{ background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.08)" }}
          >
            {(["register", "login"] as const).map((m) => (
              <button
                key={m}
                onClick={() => switchMode(m)}
                className="flex-1 py-2 rounded-md text-sm font-semibold transition-all duration-200"
                style={
                  mode === m
                    ? { background: "#f59e0b", color: "#0d1117" }
                    : { background: "transparent", color: "rgba(255,255,255,0.38)" }
                }
              >
                {m === "register" ? "Create account" : "Sign in"}
              </button>
            ))}
          </div>

          {/* ── Forms ── */}
          <AnimatePresence mode="wait">
            {mode === "register" ? (
              <motion.form
                key="register"
                initial={{ opacity: 0, x: 16 }} animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -16 }}   transition={{ duration: 0.2 }}
                onSubmit={handleRegister}
                className="space-y-3"
              >
                {/* First + Last name — stack on xs, side-by-side on sm+ */}
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <IconInput
                    icon={<PersonIcon/>} value={firstName}
                    onChange={(e) => setFirstName(e.target.value)}
                    placeholder="First name"
                    autoComplete="given-name" required
                  />
                  <IconInput
                    icon={<PersonIcon/>} value={lastName}
                    onChange={(e) => setLastName(e.target.value)}
                    placeholder="Last name"
                    autoComplete="family-name" required
                  />
                </div>

                <IconInput
                  icon={<MailIcon/>} type="email" value={regEmail}
                  onChange={(e) => setRegEmail(e.target.value)}
                  placeholder="Professional email"
                  autoComplete="email" required
                />

                <IconInput
                  icon={<LockIcon/>}
                  type={showRegPwd ? "text" : "password"}
                  value={regPwd} onChange={(e) => setRegPwd(e.target.value)}
                  placeholder="New password" autoComplete="new-password" required
                  rightSlot={
                    <button type="button" onClick={() => setShowRegPwd(!showRegPwd)}
                      className="text-slate-400 hover:text-slate-200 transition-colors">
                      {showRegPwd ? <EyeOff className="w-4 h-4"/> : <Eye className="w-4 h-4"/>}
                    </button>
                  }
                />

                <IconInput
                  icon={<LockIcon/>}
                  type={showConfirmPwd ? "text" : "password"}
                  value={confirmPwd} onChange={(e) => setConfirmPwd(e.target.value)}
                  placeholder="Confirm password" autoComplete="new-password" required
                  rightSlot={
                    <button type="button" onClick={() => setShowConfirmPwd(!showConfirmPwd)}
                      className="text-slate-400 hover:text-slate-200 transition-colors">
                      {showConfirmPwd ? <EyeOff className="w-4 h-4"/> : <Eye className="w-4 h-4"/>}
                    </button>
                  }
                />

                {error   && <Feedback type="error">{error}</Feedback>}
                {success && <Feedback type="success">{success}</Feedback>}

                <SubmitBtn loading={loading}>Register on ODSINET</SubmitBtn>
              </motion.form>
            ) : (
              <motion.form
                key="login"
                initial={{ opacity: 0, x: -16 }} animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: 16 }}     transition={{ duration: 0.2 }}
                onSubmit={handleLogin}
                className="space-y-3"
              >
                <IconInput
                  icon={<PersonIcon/>} value={loginUser}
                  onChange={(e) => setLoginUser(e.target.value)}
                  placeholder="Username or email"
                  autoComplete="username" required
                />

                <IconInput
                  icon={<LockIcon/>}
                  type={showLoginPwd ? "text" : "password"}
                  value={loginPwd} onChange={(e) => setLoginPwd(e.target.value)}
                  placeholder="Password" autoComplete="current-password" required
                  rightSlot={
                    <button type="button" onClick={() => setShowLoginPwd(!showLoginPwd)}
                      className="text-slate-400 hover:text-slate-200 transition-colors">
                      {showLoginPwd ? <EyeOff className="w-4 h-4"/> : <Eye className="w-4 h-4"/>}
                    </button>
                  }
                />

                {error   && <Feedback type="error">{error}</Feedback>}
                {success && <Feedback type="success">{success}</Feedback>}

                <SubmitBtn loading={loading}>Sign in to ODSINET</SubmitBtn>
              </motion.form>
            )}
          </AnimatePresence>

          {/* OR divider */}
          <div className="flex items-center gap-3 my-5">
            <div className="flex-1 h-px" style={{ background: "rgba(255,255,255,0.1)" }}/>
            <span className="text-xs" style={{ color: "rgba(255,255,255,0.3)" }}>or</span>
            <div className="flex-1 h-px" style={{ background: "rgba(255,255,255,0.1)" }}/>
          </div>

          {/* Social buttons */}
          <div className="flex gap-2">
            {[
              { icon: <GoogleIcon/>,    label: "Google" },
              { icon: <GitHubIcon/>,    label: "GitHub" },
              { icon: <MicrosoftIcon/>, label: "Microsoft 365" },
            ].map(({ icon, label }) => (
              <button
                key={label} type="button"
                className="flex-1 flex items-center justify-center gap-1.5 py-2.5 rounded-lg text-xs font-medium transition-all duration-200 hover:bg-white/[0.08] hover:scale-[1.03] hover:border-white/25 min-w-0"
                style={{
                  background: "rgba(255,255,255,0.04)",
                  border: "1px solid rgba(255,255,255,0.12)",
                  color: "#cbd5e1",
                }}
              >
                {icon}
                <span className="truncate">{label}</span>
              </button>
            ))}
          </div>

          {/* Terms */}
          <p className="text-center text-xs mt-5" style={{ color: "rgba(255,255,255,0.25)" }}>
            By signing up, you agree to our{" "}
            <span className="underline cursor-pointer hover:opacity-60 transition-opacity">Terms of Use</span>
            {" "}and our{" "}
            <span className="underline cursor-pointer hover:opacity-60 transition-opacity">Privacy Policy</span>.
          </p>
        </motion.div>
      </div>
    </div>
  );
};

export default LoginPage;
