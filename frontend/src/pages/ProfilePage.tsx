import { useRef, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  User, KeyRound, Save, Camera, Trash2,
  CheckCircle2, AlertCircle, Shield, Upload,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { getSession, updateProfile, changePassword } from "@/lib/auth";
import { useApp } from "@/contexts/AppContext";

/* ── helpers ─────────────────────────────────────────────────────────────── */

function getInitials(name: string) {
  return (
    name
      .split(" ")
      .map((w) => w[0])
      .slice(0, 2)
      .join("")
      .toUpperCase() || "?"
  );
}

/* ── Inline alert ─────────────────────────────────────────────────────────── */
function Alert({ type, msg }: { type: "success" | "error"; msg: string }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: -6 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -6 }}
      className="flex items-center gap-2 px-3 py-2.5 rounded-lg text-xs font-medium"
      style={{
        background: type === "success" ? "hsl(var(--success-bg))" : "hsl(var(--danger-bg))",
        color:      type === "success" ? "hsl(var(--success))"    : "hsl(var(--danger))",
      }}
    >
      {type === "success"
        ? <CheckCircle2 className="w-3.5 h-3.5 shrink-0" />
        : <AlertCircle  className="w-3.5 h-3.5 shrink-0" />}
      {msg}
    </motion.div>
  );
}

/* ── Label + input wrapper ────────────────────────────────────────────────── */
function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="space-y-1.5">
      <label
        className="text-xs font-semibold block"
        style={{ color: "hsl(var(--muted-foreground))" }}
      >
        {label}
      </label>
      {children}
    </div>
  );
}

type Tab = "account" | "security";

const TABS: { id: Tab; icon: React.ElementType; fr: string; en: string; descFr: string; descEn: string }[] = [
  {
    id: "account",
    icon: User,
    fr: "Informations",
    en: "Account Info",
    descFr: "Nom, email, photo",
    descEn: "Name, email, photo",
  },
  {
    id: "security",
    icon: KeyRound,
    fr: "Sécurité",
    en: "Security",
    descFr: "Mot de passe & accès",
    descEn: "Password & access",
  },
];

/* ══════════════════════════════════════════════════════════════════════════ */

const ProfilePage = () => {
  const { lang } = useApp();
  const session  = getSession();

  const [activeTab, setActiveTab]   = useState<Tab>("account");
  const fileInputRef                = useRef<HTMLInputElement>(null);

  /* ── Account state ── */
  const [displayName, setDisplayName] = useState(session?.displayName ?? "");
  const [email,       setEmail]       = useState(session?.email ?? "");
  const [bio,         setBio]         = useState(session?.bio ?? "");
  const [photo,       setPhoto]       = useState<string | undefined>(session?.photo);
  const [profileMsg,  setProfileMsg]  = useState<{ type: "success" | "error"; text: string } | null>(null);

  /* ── Security state ── */
  const [currentPwd, setCurrentPwd] = useState("");
  const [newPwd,     setNewPwd]     = useState("");
  const [confirmPwd, setConfirmPwd] = useState("");
  const [pwdMsg,     setPwdMsg]     = useState<{ type: "success" | "error"; text: string } | null>(null);

  if (!session) return null;

  const L = (fr: string, en: string) => (lang === "fr" ? fr : en);

  /* ── Photo upload handler ── */
  const handlePhotoChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    if (file.size > 2 * 1024 * 1024) {
      setProfileMsg({ type: "error", text: L("Image trop lourde (max 2 Mo).", "Image too large (max 2 MB).") });
      return;
    }
    if (!file.type.startsWith("image/")) {
      setProfileMsg({ type: "error", text: L("Format non supporté.", "Unsupported format.") });
      return;
    }

    const reader = new FileReader();
    reader.onload = (ev) => {
      const dataUrl = ev.target?.result as string;
      setPhoto(dataUrl);
      setProfileMsg(null);
    };
    reader.readAsDataURL(file);
    // Reset input so the same file can be re-selected
    e.target.value = "";
  };

  const handleRemovePhoto = () => {
    setPhoto(undefined);
  };

  /* ── Save profile ── */
  const handleSaveProfile = () => {
    setProfileMsg(null);
    const ok = updateProfile(session.username, {
      displayName: displayName.trim(),
      email:       email.trim(),
      bio:         bio.trim(),
      photo,
    });
    setProfileMsg(
      ok
        ? { type: "success", text: L("Profil mis à jour avec succès.", "Profile updated successfully.") }
        : { type: "error",   text: L("Erreur lors de la sauvegarde.", "Error saving profile.") }
    );
    setTimeout(() => setProfileMsg(null), 3000);
  };

  /* ── Change password ── */
  const handleChangePwd = () => {
    setPwdMsg(null);
    if (!currentPwd) {
      setPwdMsg({ type: "error", text: L("Saisissez votre mot de passe actuel.", "Enter your current password.") });
      return;
    }
    if (newPwd !== confirmPwd) {
      setPwdMsg({ type: "error", text: L("Les mots de passe ne correspondent pas.", "Passwords do not match.") });
      return;
    }
    if (newPwd.length < 4) {
      setPwdMsg({ type: "error", text: L("Minimum 4 caractères.", "Minimum 4 characters.") });
      return;
    }
    const res = changePassword(session.username, currentPwd, newPwd);
    if (!res.ok) {
      setPwdMsg({ type: "error", text: res.error === "wrong_password"
        ? L("Mot de passe actuel incorrect.", "Wrong current password.")
        : (res.error ?? "Erreur") });
      return;
    }
    setPwdMsg({ type: "success", text: L("Mot de passe modifié avec succès.", "Password changed successfully.") });
    setCurrentPwd(""); setNewPwd(""); setConfirmPwd("");
    setTimeout(() => setPwdMsg(null), 3000);
  };

  /* ── Password strength ── */
  const pwdStrength = newPwd.length === 0 ? 0 : Math.min(4, Math.ceil(newPwd.length / 2.5));
  const pwdStrengthLabel = ["", L("Trop court", "Too short"), L("Faible", "Weak"), L("Moyen", "Medium"), L("Fort", "Strong")];
  const pwdStrengthColor = ["", "#ef4444", "#f97316", "#3b82f6", "#22c55e"];

  const inputCls = `w-full px-3 py-2.5 rounded-lg text-sm outline-none transition-all border
    focus:border-primary/60 focus:ring-2 focus:ring-primary/20 bg-background
    text-foreground placeholder:text-muted-foreground`;
  const bdr = { borderColor: "hsl(var(--border))" };

  /* ══════════════════════════════════════════════════════════════════════ */
  return (
    <div className="p-6 lg:p-8 max-w-5xl mx-auto">

      {/* Page title */}
      <motion.div
        initial={{ opacity: 0, y: -10 }}
        animate={{ opacity: 1, y: 0 }}
        className="mb-6"
      >
        <h1 className="text-2xl font-bold" style={{ color: "hsl(var(--foreground))" }}>
          {L("Mon Profil", "My Profile")}
        </h1>
        <p className="text-sm mt-0.5" style={{ color: "hsl(var(--muted-foreground))" }}>
          {L(
            "Gérez vos informations personnelles et paramètres de sécurité",
            "Manage your personal information and security settings",
          )}
        </p>
      </motion.div>

      {/* 2-column layout */}
      <div className="flex flex-col lg:flex-row gap-6 items-start">

        {/* ══ LEFT — Avatar card + Tabs ══════════════════════════════════ */}
        <motion.div
          initial={{ opacity: 0, x: -16 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.3 }}
          className="lg:w-60 shrink-0 space-y-4"
        >
          {/* Avatar card */}
          <div className="glass-card rounded-2xl p-6 flex flex-col items-center gap-3 text-center">

            {/* Photo or initials */}
            <div className="relative group">
              {photo ? (
                <img
                  src={photo}
                  alt={displayName}
                  className="w-24 h-24 rounded-full object-cover shadow-lg ring-4"
                  style={{ ringColor: "hsl(var(--primary) / 0.3)" }}
                />
              ) : (
                <div
                  className="w-24 h-24 rounded-full flex items-center justify-center text-3xl font-bold text-white shadow-lg"
                  style={{ background: session.avatarColor }}
                >
                  {getInitials(displayName || session.username)}
                </div>
              )}

              {/* Overlay on hover */}
              <button
                onClick={() => fileInputRef.current?.click()}
                className="absolute inset-0 rounded-full flex items-center justify-center
                           bg-black/50 opacity-0 group-hover:opacity-100 transition-opacity cursor-pointer"
                title={L("Changer la photo", "Change photo")}
              >
                <Camera className="w-6 h-6 text-white" />
              </button>
            </div>

            {/* Hidden file input */}
            <input
              ref={fileInputRef}
              type="file"
              accept="image/jpeg,image/png,image/webp,image/gif"
              className="hidden"
              onChange={handlePhotoChange}
            />

            {/* Upload / Remove buttons */}
            <div className="flex gap-2">
              <button
                onClick={() => fileInputRef.current?.click()}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold
                           transition-all hover:opacity-80"
                style={{ background: "hsl(var(--primary) / 0.15)", color: "hsl(var(--primary))" }}
              >
                <Upload className="w-3 h-3" />
                {L("Importer", "Upload")}
              </button>
              {photo && (
                <button
                  onClick={handleRemovePhoto}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold
                             transition-all hover:opacity-80"
                  style={{ background: "hsl(var(--danger-bg))", color: "hsl(var(--danger))" }}
                >
                  <Trash2 className="w-3 h-3" />
                  {L("Retirer", "Remove")}
                </button>
              )}
            </div>

            <div className="w-full h-px" style={{ background: "hsl(var(--border))" }} />

            <div>
              <p className="font-bold text-sm" style={{ color: "hsl(var(--foreground))" }}>
                {displayName || session.username}
              </p>
              <p className="text-xs mt-0.5" style={{ color: "hsl(var(--muted-foreground))" }}>
                @{session.username}
              </p>
              <span
                className="inline-flex items-center gap-1 mt-2 px-2.5 py-0.5 rounded-full text-[10px] font-bold"
                style={{
                  background: session.role === "admin" ? "hsl(var(--primary) / 0.15)" : "hsl(var(--success-bg))",
                  color:      session.role === "admin" ? "hsl(var(--primary))"        : "hsl(var(--success))",
                }}
              >
                <Shield className="w-2.5 h-2.5" />
                {session.role === "admin"
                  ? L("Administrateur", "Administrator")
                  : L("Utilisateur",   "User")}
              </span>
            </div>

          </div>

          {/* Tabs */}
          <div className="glass-card rounded-2xl overflow-hidden">
            {TABS.map((tab, i) => {
              const isActive = activeTab === tab.id;
              return (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  className="w-full flex items-center gap-3 px-4 py-3.5 text-left transition-all relative"
                  style={{
                    background:  isActive ? "hsl(var(--primary) / 0.1)" : "transparent",
                    color:       isActive ? "hsl(var(--primary))"       : "hsl(var(--muted-foreground))",
                    borderBottom: i < TABS.length - 1 ? "1px solid hsl(var(--border))" : undefined,
                  }}
                >
                  {isActive && (
                    <motion.div
                      layoutId="tab-bar"
                      className="absolute left-0 top-1/2 -translate-y-1/2 w-[3px] h-5 rounded-r-full"
                      style={{ background: "hsl(var(--primary))" }}
                    />
                  )}
                  <div
                    className="w-8 h-8 rounded-lg flex items-center justify-center shrink-0"
                    style={{
                      background: isActive
                        ? "hsl(var(--primary) / 0.2)"
                        : "hsl(var(--muted) / 0.4)",
                    }}
                  >
                    <tab.icon className="w-4 h-4" />
                  </div>
                  <div className="min-w-0">
                    <p className="text-xs font-semibold truncate">
                      {lang === "fr" ? tab.fr : tab.en}
                    </p>
                    <p className="text-[10px] truncate opacity-70">
                      {lang === "fr" ? tab.descFr : tab.descEn}
                    </p>
                  </div>
                </button>
              );
            })}
          </div>
        </motion.div>

        {/* ══ RIGHT — Tab content ════════════════════════════════════════ */}
        <motion.div
          initial={{ opacity: 0, x: 16 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.3 }}
          className="flex-1 min-w-0"
        >
          <AnimatePresence mode="wait">

            {/* ── Account Info ── */}
            {activeTab === "account" && (
              <motion.div
                key="account"
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -8 }}
                transition={{ duration: 0.2 }}
                className="glass-card rounded-2xl p-6 space-y-6"
              >
                {/* Header */}
                <div className="flex items-center gap-3 pb-4 border-b" style={bdr}>
                  <div
                    className="w-10 h-10 rounded-xl flex items-center justify-center shrink-0"
                    style={{ background: "hsl(var(--primary) / 0.12)" }}
                  >
                    <User className="w-5 h-5" style={{ color: "hsl(var(--primary))" }} />
                  </div>
                  <div>
                    <h2 className="text-base font-bold" style={{ color: "hsl(var(--foreground))" }}>
                      {L("Informations personnelles", "Personal Information")}
                    </h2>
                    <p className="text-xs" style={{ color: "hsl(var(--muted-foreground))" }}>
                      {L("Mettez à jour votre profil", "Update your profile")}
                    </p>
                  </div>
                </div>

                {/* Photo upload row */}
                <div
                  className="flex items-center gap-4 p-4 rounded-xl border"
                  style={{ background: "hsl(var(--muted) / 0.25)", borderColor: "hsl(var(--border))" }}
                >
                  {/* Preview */}
                  {photo ? (
                    <img
                      src={photo}
                      alt="preview"
                      className="w-16 h-16 rounded-full object-cover shrink-0 shadow ring-2"
                      style={{ ringColor: "hsl(var(--primary) / 0.4)" }}
                    />
                  ) : (
                    <div
                      className="w-16 h-16 rounded-full flex items-center justify-center
                                 text-xl font-bold text-white shrink-0 shadow"
                      style={{ background: session.avatarColor }}
                    >
                      {getInitials(displayName || session.username)}
                    </div>
                  )}

                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-semibold" style={{ color: "hsl(var(--foreground))" }}>
                      {L("Photo de profil", "Profile Photo")}
                    </p>
                    <p className="text-xs mt-0.5" style={{ color: "hsl(var(--muted-foreground))" }}>
                      {L("JPG, PNG ou WebP — max 2 Mo", "JPG, PNG or WebP — max 2 MB")}
                    </p>
                  </div>

                  <div className="flex gap-2 shrink-0">
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => fileInputRef.current?.click()}
                    >
                      <Camera className="w-3.5 h-3.5 mr-1.5" />
                      {L("Importer", "Upload")}
                    </Button>
                    {photo && (
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={handleRemovePhoto}
                        className="text-destructive hover:bg-destructive/10"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </Button>
                    )}
                  </div>

                  <input
                    ref={fileInputRef}
                    type="file"
                    accept="image/jpeg,image/png,image/webp,image/gif"
                    className="hidden"
                    onChange={handlePhotoChange}
                  />
                </div>

                {/* Form */}
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <Field label={L("Nom complet", "Full Name")}>
                    <input
                      type="text"
                      value={displayName}
                      onChange={(e) => setDisplayName(e.target.value)}
                      placeholder={L("Votre nom", "Your name")}
                      className={inputCls}
                      style={bdr}
                    />
                  </Field>

                  <Field label={L("Adresse email", "Email Address")}>
                    <input
                      type="email"
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      placeholder="exemple@domaine.tn"
                      className={inputCls}
                      style={bdr}
                    />
                  </Field>

                  <Field label={L("Nom d'utilisateur", "Username")}>
                    <input
                      type="text"
                      value={session.username}
                      disabled
                      className={inputCls + " opacity-50 cursor-not-allowed"}
                      style={bdr}
                    />
                  </Field>

                  <Field label={L("Rôle", "Role")}>
                    <input
                      type="text"
                      value={session.role === "admin"
                        ? L("Administrateur", "Administrator")
                        : L("Utilisateur", "User")}
                      disabled
                      className={inputCls + " opacity-50 cursor-not-allowed"}
                      style={bdr}
                    />
                  </Field>
                </div>

                <Field label={L("Biographie", "Biography")}>
                  <textarea
                    value={bio}
                    onChange={(e) => setBio(e.target.value)}
                    placeholder={L(
                      "Décrivez-vous en quelques mots…",
                      "Describe yourself in a few words…",
                    )}
                    rows={3}
                    className={inputCls + " resize-none"}
                    style={bdr}
                  />
                </Field>

                <AnimatePresence>
                  {profileMsg && <Alert type={profileMsg.type} msg={profileMsg.text} />}
                </AnimatePresence>

                <div className="flex justify-end pt-1">
                  <Button onClick={handleSaveProfile} className="px-7">
                    <Save className="w-4 h-4 mr-2" />
                    {L("Mettre à jour", "Update Information")}
                  </Button>
                </div>
              </motion.div>
            )}

            {/* ── Security ── */}
            {activeTab === "security" && (
              <motion.div
                key="security"
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -8 }}
                transition={{ duration: 0.2 }}
                className="glass-card rounded-2xl p-6 space-y-6"
              >
                {/* Header */}
                <div className="flex items-center gap-3 pb-4 border-b" style={bdr}>
                  <div
                    className="w-10 h-10 rounded-xl flex items-center justify-center shrink-0"
                    style={{ background: "hsl(var(--danger-bg))" }}
                  >
                    <KeyRound className="w-5 h-5" style={{ color: "hsl(var(--danger))" }} />
                  </div>
                  <div>
                    <h2 className="text-base font-bold" style={{ color: "hsl(var(--foreground))" }}>
                      {L("Mot de passe & Sécurité", "Password & Security")}
                    </h2>
                    <p className="text-xs" style={{ color: "hsl(var(--muted-foreground))" }}>
                      {L("Modifiez votre mot de passe de connexion", "Update your login password")}
                    </p>
                  </div>
                </div>

                {/* Info banner */}
                <div
                  className="flex items-start gap-3 p-4 rounded-xl border"
                  style={{
                    background:   "hsl(var(--primary) / 0.05)",
                    borderColor:  "hsl(var(--primary) / 0.2)",
                  }}
                >
                  <Shield className="w-4 h-4 mt-0.5 shrink-0" style={{ color: "hsl(var(--primary))" }} />
                  <p className="text-xs" style={{ color: "hsl(var(--muted-foreground))" }}>
                    {L(
                      "Utilisez un mot de passe fort d'au moins 8 caractères, mélangeant lettres, chiffres et symboles.",
                      "Use a strong password of at least 8 characters, mixing letters, numbers and symbols.",
                    )}
                  </p>
                </div>

                {/* Fields */}
                <Field label={L("Mot de passe actuel", "Current Password")}>
                  <input
                    type="password"
                    value={currentPwd}
                    onChange={(e) => setCurrentPwd(e.target.value)}
                    placeholder="••••••••"
                    className={inputCls}
                    style={bdr}
                  />
                </Field>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <Field label={L("Nouveau mot de passe", "New Password")}>
                    <input
                      type="password"
                      value={newPwd}
                      onChange={(e) => setNewPwd(e.target.value)}
                      placeholder="••••••••"
                      className={inputCls}
                      style={bdr}
                    />
                  </Field>

                  <Field label={L("Confirmer le mot de passe", "Confirm Password")}>
                    <input
                      type="password"
                      value={confirmPwd}
                      onChange={(e) => setConfirmPwd(e.target.value)}
                      placeholder="••••••••"
                      className={inputCls}
                      style={bdr}
                    />
                  </Field>
                </div>

                {/* Strength indicator */}
                <AnimatePresence>
                  {newPwd.length > 0 && (
                    <motion.div
                      initial={{ opacity: 0, height: 0 }}
                      animate={{ opacity: 1, height: "auto" }}
                      exit={{ opacity: 0, height: 0 }}
                      className="space-y-1.5 overflow-hidden"
                    >
                      <div className="flex gap-1">
                        {[1, 2, 3, 4].map((lvl) => (
                          <div
                            key={lvl}
                            className="h-1.5 flex-1 rounded-full transition-all duration-300"
                            style={{
                              background: lvl <= pwdStrength
                                ? pwdStrengthColor[pwdStrength]
                                : "hsl(var(--border))",
                            }}
                          />
                        ))}
                      </div>
                      <p
                        className="text-[11px] font-medium"
                        style={{ color: pwdStrengthColor[pwdStrength] }}
                      >
                        {pwdStrengthLabel[pwdStrength]}
                      </p>
                    </motion.div>
                  )}
                </AnimatePresence>

                <AnimatePresence>
                  {pwdMsg && <Alert type={pwdMsg.type} msg={pwdMsg.text} />}
                </AnimatePresence>

                <div className="flex justify-end pt-1">
                  <Button onClick={handleChangePwd} className="px-7">
                    <KeyRound className="w-4 h-4 mr-2" />
                    {L("Changer le mot de passe", "Change Password")}
                  </Button>
                </div>
              </motion.div>
            )}

          </AnimatePresence>
        </motion.div>
      </div>
    </div>
  );
};

export default ProfilePage;
