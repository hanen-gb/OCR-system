import { useState } from "react";
import { motion } from "framer-motion";
import { Save, KeyRound, Palette } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  getSession, updateProfile, changePassword, AVATAR_COLORS,
} from "@/lib/auth";
import { useApp } from "@/contexts/AppContext";

const fade = (delay = 0) => ({
  initial: { opacity: 0, y: 14 },
  animate: { opacity: 1, y: 0 },
  transition: { delay, duration: 0.3 },
});

function AvatarPreview({ name, color }: { name: string; color: string }) {
  const initials = name
    .split(" ")
    .map((w) => w[0])
    .slice(0, 2)
    .join("")
    .toUpperCase() || "?";
  return (
    <div
      className="w-16 h-16 rounded-full flex items-center justify-center text-xl font-bold text-white shrink-0"
      style={{ background: color }}
    >
      {initials}
    </div>
  );
}

const ProfilePage = () => {
  const { t } = useApp();
  const session = getSession();

  const [displayName, setDisplayName] = useState(session?.displayName ?? "");
  const [email, setEmail] = useState(session?.email ?? "");
  const [bio, setBio] = useState(session?.bio ?? "");
  const [avatarColor, setAvatarColor] = useState(session?.avatarColor ?? AVATAR_COLORS[0]);
  const [profileSaved, setProfileSaved] = useState(false);
  const [profileError, setProfileError] = useState("");

  const [currentPwd, setCurrentPwd] = useState("");
  const [newPwd, setNewPwd] = useState("");
  const [confirmPwd, setConfirmPwd] = useState("");
  const [pwdSaved, setPwdSaved] = useState(false);
  const [pwdError, setPwdError] = useState("");

  if (!session) return null;

  const handleSaveProfile = () => {
    setProfileError(""); setProfileSaved(false);
    const ok = updateProfile(session.username, { displayName: displayName.trim(), email: email.trim(), bio: bio.trim(), avatarColor });
    if (ok) { setProfileSaved(true); setTimeout(() => setProfileSaved(false), 2500); }
    else { setProfileError("Erreur lors de la sauvegarde."); }
  };

  const handleChangePwd = () => {
    setPwdError(""); setPwdSaved(false);
    if (newPwd !== confirmPwd) { setPwdError(t("prof_pwd_mismatch")); return; }
    if (newPwd.length < 4) { setPwdError("Mot de passe trop court (min. 4 caractères)."); return; }
    const res = changePassword(session.username, currentPwd, newPwd);
    if (!res.ok) {
      setPwdError(res.error === "wrong_password" ? t("prof_wrong_password") : (res.error ?? "Erreur"));
      return;
    }
    setPwdSaved(true);
    setCurrentPwd(""); setNewPwd(""); setConfirmPwd("");
    setTimeout(() => setPwdSaved(false), 2500);
  };

  return (
    <div className="p-6 lg:p-8 space-y-6 max-w-2xl mx-auto">
      <motion.div {...fade(0)}>
        <h1 className="text-xl font-bold text-foreground">{t("prof_title")}</h1>
      </motion.div>

      {/* Carte profil */}
      <motion.div {...fade(0.05)} className="glass-card rounded-xl p-6 space-y-5">
        {/* Avatar + infos basiques */}
        <div className="flex items-center gap-4">
          <AvatarPreview name={displayName || session.username} color={avatarColor} />
          <div>
            <p className="font-semibold text-foreground">{displayName || session.username}</p>
            <p className="text-xs text-muted-foreground">@{session.username}</p>
            <p className="text-xs text-muted-foreground mt-0.5">
              {t("prof_role")} : <span className="font-semibold text-primary">{session.role === "admin" ? t("prof_admin") : t("prof_user")}</span>
            </p>
            <p className="text-xs text-muted-foreground">
              {t("prof_member_since")} : <span className="font-semibold">{session.createdAt}</span>
            </p>
          </div>
        </div>

        <div className="h-px bg-border" />

        {/* Formulaire profil */}
        <div className="space-y-4">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="text-xs font-medium text-muted-foreground mb-1.5 block">
                {t("prof_display_name")}
              </label>
              <input
                type="text"
                value={displayName}
                onChange={(e) => setDisplayName(e.target.value)}
                className="input-base"
              />
            </div>
            <div>
              <label className="text-xs font-medium text-muted-foreground mb-1.5 block">
                {t("prof_email")}
              </label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="input-base"
              />
            </div>
          </div>

          <div>
            <label className="text-xs font-medium text-muted-foreground mb-1.5 block">
              {t("prof_bio")}
            </label>
            <textarea
              value={bio}
              onChange={(e) => setBio(e.target.value)}
              placeholder={t("prof_bio_placeholder")}
              rows={3}
              className="input-base resize-none"
            />
          </div>

          {/* Couleur avatar */}
          <div>
            <label className="text-xs font-medium text-muted-foreground mb-2 flex items-center gap-1.5">
              <Palette className="w-3.5 h-3.5" /> {t("prof_avatar_color")}
            </label>
            <div className="flex flex-wrap gap-2">
              {AVATAR_COLORS.map((color) => (
                <button
                  key={color}
                  type="button"
                  onClick={() => setAvatarColor(color)}
                  className="w-8 h-8 rounded-full transition-transform hover:scale-110"
                  style={{
                    background: color,
                    outline: avatarColor === color ? `3px solid hsl(var(--primary))` : "3px solid transparent",
                    outlineOffset: "2px",
                  }}
                />
              ))}
            </div>
          </div>

          {profileError && (
            <p className="text-xs px-3 py-2 rounded-lg" style={{ background: "hsl(var(--danger-bg))", color: "hsl(var(--danger))" }}>
              {profileError}
            </p>
          )}

          <Button onClick={handleSaveProfile} size="sm">
            <Save className="w-3.5 h-3.5 mr-1.5" />
            {profileSaved ? t("prof_saved") : t("prof_save")}
          </Button>
        </div>
      </motion.div>

      {/* Changer mot de passe */}
      <motion.div {...fade(0.1)} className="glass-card rounded-xl p-6 space-y-4">
        <div className="flex items-center gap-2 mb-1">
          <KeyRound className="w-4 h-4 text-primary" />
          <h2 className="text-sm font-semibold text-foreground">{t("prof_change_password")}</h2>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <div>
            <label className="text-xs font-medium text-muted-foreground mb-1.5 block">
              {t("prof_current_password")}
            </label>
            <input
              type="password"
              value={currentPwd}
              onChange={(e) => setCurrentPwd(e.target.value)}
              placeholder="••••••••"
              className="input-base"
            />
          </div>
          <div>
            <label className="text-xs font-medium text-muted-foreground mb-1.5 block">
              {t("prof_new_password")}
            </label>
            <input
              type="password"
              value={newPwd}
              onChange={(e) => setNewPwd(e.target.value)}
              placeholder="••••••••"
              className="input-base"
            />
          </div>
          <div>
            <label className="text-xs font-medium text-muted-foreground mb-1.5 block">
              {t("prof_confirm_password")}
            </label>
            <input
              type="password"
              value={confirmPwd}
              onChange={(e) => setConfirmPwd(e.target.value)}
              placeholder="••••••••"
              className="input-base"
            />
          </div>
        </div>

        {pwdError && (
          <p className="text-xs px-3 py-2 rounded-lg" style={{ background: "hsl(var(--danger-bg))", color: "hsl(var(--danger))" }}>
            {pwdError}
          </p>
        )}
        {pwdSaved && (
          <p className="text-xs px-3 py-2 rounded-lg" style={{ background: "hsl(var(--success-bg))", color: "hsl(var(--success))" }}>
            {t("prof_saved")}
          </p>
        )}

        <Button onClick={handleChangePwd} size="sm" variant="outline">
          <KeyRound className="w-3.5 h-3.5 mr-1.5" />
          {t("prof_change_password")}
        </Button>
      </motion.div>
    </div>
  );
};

export default ProfilePage;
